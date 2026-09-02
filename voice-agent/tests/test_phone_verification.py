"""Unit tests for resolve_caller_identity.

Mocks both the `phone_verification.HighwayAPI` and
`phone_verification.NegotiationDBService` boundaries via unittest.mock — the
HTTP-layer behavior is covered by shared/tests/test_highway_api.py and the
Supabase row shape is covered by call-site tests, so here we only verify the
parallel-lookup orchestration and never-raise contract.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# voice-agent modules live alongside this tests/ directory.
_VOICE_AGENT = Path(__file__).resolve().parent.parent
if str(_VOICE_AGENT) not in sys.path:
    sys.path.insert(0, str(_VOICE_AGENT))

from src.highway_api import CarrierLookupResult, HighwayAPIError  # noqa: E402

import phone_verification  # noqa: E402
from phone_verification import resolve_caller_identity  # noqa: E402


FLAG_ON = {"HIGHWAY_PHONE_LOOKUP_ENABLED": "true"}
ORG = "00000000-0000-0000-0000-000000000001"
PHONE = "+14155550100"


def _mock_highway(lookup_return=None, lookup_side_effect=None):
    """Patch HighwayAPI; returns the patcher + instance for assertions."""
    instance = AsyncMock()
    if lookup_side_effect is not None:
        instance.lookup_carrier_by_phone.side_effect = lookup_side_effect
    else:
        instance.lookup_carrier_by_phone.return_value = (
            lookup_return
            if lookup_return is not None
            else CarrierLookupResult.unknown(reason="not_found")
        )
    instance.close.return_value = None
    return patch.object(phone_verification, "HighwayAPI", return_value=instance), instance


def _mock_supabase(row_return=None, side_effect=None):
    """Patch NegotiationDBService.get_carrier_by_phone."""
    mock = MagicMock()
    if side_effect is not None:
        mock.side_effect = side_effect
    else:
        mock.return_value = row_return
    return patch.object(
        phone_verification.NegotiationDBService,
        "get_carrier_by_phone",
        new=mock,
    ), mock


class ResolveCallerIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def test_feature_flag_off(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("HIGHWAY_PHONE_LOOKUP_ENABLED", None)
            highway_p, highway = _mock_highway()
            sb_p, sb = _mock_supabase()
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, ORG)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "feature_disabled")
        highway.lookup_carrier_by_phone.assert_not_called()
        sb.assert_not_called()

    async def test_empty_phone(self):
        with patch.dict(os.environ, FLAG_ON):
            highway_p, highway = _mock_highway()
            sb_p, sb = _mock_supabase()
            with highway_p, sb_p:
                result = await resolve_caller_identity("", ORG)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "empty_or_malformed_phone")
        highway.lookup_carrier_by_phone.assert_not_called()
        sb.assert_not_called()

    async def test_malformed_phone(self):
        with patch.dict(os.environ, FLAG_ON):
            highway_p, highway = _mock_highway()
            sb_p, sb = _mock_supabase()
            with highway_p, sb_p:
                result = await resolve_caller_identity("not-a-phone", ORG)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "empty_or_malformed_phone")
        highway.lookup_carrier_by_phone.assert_not_called()
        sb.assert_not_called()

    async def test_supabase_only_hit(self):
        # Highway misses, Supabase has the row.
        with patch.dict(os.environ, FLAG_ON):
            highway_p, _ = _mock_highway(
                lookup_return=CarrierLookupResult.unknown(reason="not_found"),
            )
            sb_p, _ = _mock_supabase(row_return={
                "phone_e164": PHONE,
                "mc_number": "999999",
                "carrier_name": "STORED CARRIER",
                "dot_number": "12345",
                "last_verified_at": "2026-01-01T00:00:00Z",
            })
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, ORG)
        self.assertEqual(result.status, "known_carrier")
        # Defensive humanize on legacy ALL-CAPS rows.
        self.assertEqual(result.carrier_name, "Stored Carrier")
        self.assertEqual(result.mc_number, "999999")
        self.assertEqual(result.reason, "from_supabase_lookup")

    async def test_highway_only_hit(self):
        # Supabase misses, Highway has it.
        highway_result = CarrierLookupResult(
            status="known_carrier",
            carrier_name="HIGHWAY CARRIER",
            mc_number="111111",
            highway_carrier_id="40",
        )
        with patch.dict(os.environ, FLAG_ON):
            highway_p, _ = _mock_highway(lookup_return=highway_result)
            sb_p, _ = _mock_supabase(row_return=None)
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, ORG)
        self.assertEqual(result, highway_result)

    async def test_both_hit_supabase_precedence(self):
        # Both sources return known with DIFFERENT MCs — Supabase wins.
        highway_result = CarrierLookupResult(
            status="known_carrier",
            carrier_name="HIGHWAY NAME",
            mc_number="111111",
        )
        with patch.dict(os.environ, FLAG_ON):
            highway_p, _ = _mock_highway(lookup_return=highway_result)
            sb_p, _ = _mock_supabase(row_return={
                "phone_e164": PHONE,
                "mc_number": "999999",
                "carrier_name": "SUPABASE NAME",
                "dot_number": None,
                "last_verified_at": "2026-01-01T00:00:00Z",
            })
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, ORG)
        self.assertEqual(result.status, "known_carrier")
        self.assertEqual(result.mc_number, "999999")
        self.assertEqual(result.carrier_name, "Supabase Name")  # humanized

    async def test_both_miss(self):
        with patch.dict(os.environ, FLAG_ON):
            highway_p, _ = _mock_highway(
                lookup_return=CarrierLookupResult.unknown(reason="not_found"),
            )
            sb_p, _ = _mock_supabase(row_return=None)
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, ORG)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "not_found")

    async def test_supabase_db_error_blocks_highway_and_forces_mc_first(self):
        """Unsafe-open protection: when the Supabase lookup raises, we
        cannot honor the Supabase-precedence invariant. Falling through
        to Highway here would let stale Highway identity skip MC
        verification, so we force MC-first by returning unknown(db_error)
        even when Highway has a hit."""
        highway_result = CarrierLookupResult(
            status="known_carrier",
            carrier_name="HIGHWAY CARRIER",
            mc_number="111111",
        )
        with patch.dict(os.environ, FLAG_ON):
            highway_p, _ = _mock_highway(lookup_return=highway_result)
            sb_p, _ = _mock_supabase(side_effect=RuntimeError("db down"))
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, ORG)
        # Highway is suppressed; bot falls back to MC-first greeting.
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "db_error")

    async def test_no_org_id_skips_supabase(self):
        highway_result = CarrierLookupResult(
            status="known_carrier",
            carrier_name="HIGHWAY CARRIER",
            mc_number="111111",
        )
        with patch.dict(os.environ, FLAG_ON):
            highway_p, _ = _mock_highway(lookup_return=highway_result)
            sb_p, sb = _mock_supabase(row_return={"mc_number": "should-not-be-used"})
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, None)
        self.assertEqual(result, highway_result)
        sb.assert_not_called()

    async def test_timeout(self):
        async def slow_lookup(_phone):
            await asyncio.sleep(5.0)
            return CarrierLookupResult(status="known_carrier")

        env = {**FLAG_ON, "HIGHWAY_PHONE_LOOKUP_TIMEOUT_S": "0.05"}
        with patch.dict(os.environ, env):
            highway_p, highway = _mock_highway(lookup_side_effect=slow_lookup)
            sb_p, _ = _mock_supabase(row_return=None)
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, ORG)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "timeout")
        highway.close.assert_awaited()

    async def test_api_error(self):
        with patch.dict(os.environ, FLAG_ON):
            highway_p, highway = _mock_highway(
                lookup_side_effect=HighwayAPIError("boom"),
            )
            sb_p, _ = _mock_supabase(row_return=None)
            with highway_p, sb_p:
                result = await resolve_caller_identity(PHONE, ORG)
        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "api_error")
        highway.close.assert_awaited()


if __name__ == "__main__":
    unittest.main()
