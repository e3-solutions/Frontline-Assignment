"""Tests for the deferred phone_carrier_lookup upsert flow.

Behavior under test:
- `verify_carrier` success no longer writes to Supabase. It stages
  context state (caller_mc, carrier_name, caller_dot_number).
- `get_load_context` runs the upsert at the start, regardless of whether
  the load lookup itself succeeds. The LLM only reaches `get_load_context`
  after the carrier was verbally confirmed per the prompt's flow, so
  this is when the (phone, MC, carrier_name) mapping becomes "confirmed".
- The upsert is skipped when any required context attr is missing
  (e.g. verify_carrier returned not_found, so carrier_name was never set).
- A Supabase write failure does not break the LLM tool response.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

# voice-agent modules live alongside this tests/ directory.
_VOICE_AGENT = Path(__file__).resolve().parent.parent
if str(_VOICE_AGENT) not in sys.path:
    sys.path.insert(0, str(_VOICE_AGENT))

import call_helpers  # noqa: E402
from call_helpers import (  # noqa: E402
    confirm_carrier_identity,
    get_load_context,
    persist_confirmed_carrier_identity,
    verify_carrier,
)


CARRIER_PAYLOAD = {
    "data": {
        "dbaName": "ACME TRUCKING",
        "legalName": "ACME TRUCKING INC",
        "mcNumber": "123456",
        "dotNumber": "1380078",
    }
}


def _make_context(**overrides) -> SimpleNamespace:
    """LLMContext-shaped object — we only access attrs via getattr."""
    defaults = {
        "caller_phone": "+14155550100",
        "org_id": "00000000-0000-0000-0000-000000000001",
        "phone_verified": False,
        "caller_mc": None,
        "carrier_name": None,
        "caller_dot_number": None,
        "identity_source": None,
        "carrier_identity_confirmed": False,
        "call_id": None,
        "messages": [{"role": "system", "content": "..."}],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


async def _collect_callback():
    captured: dict[str, object] = {}

    async def cb(payload, *, properties=None):
        captured["payload"] = payload
        captured["properties"] = properties

    return cb, captured


class VerifyCarrierStagesContextTests(unittest.IsolatedAsyncioTestCase):
    """verify_carrier success stages context state — does NOT upsert."""

    async def test_verify_carrier_does_not_upsert(self):
        """Regression: verify_carrier must NOT write to Supabase. The caller
        hasn't confirmed the carrier identity verbally yet."""
        context = _make_context()
        cb, captured = await _collect_callback()
        upsert = MagicMock(return_value=None)
        with (
            patch.object(call_helpers, "fetch_carrier_by_mc",
                         new=AsyncMock(return_value=CARRIER_PAYLOAD)),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await verify_carrier(
                "verify_carrier", "tcid", {"mc_number": "123456"},
                None, context, cb,
            )

        result = json.loads(captured["payload"])
        self.assertEqual(result["status"], "success")
        # No upsert at this stage.
        upsert.assert_not_called()
        # Context staged for the deferred upsert in get_load_context.
        self.assertEqual(context.caller_mc, "123456")
        self.assertEqual(context.carrier_name, "Acme Trucking")
        self.assertEqual(context.caller_dot_number, "1380078")
        self.assertTrue(context.awaiting_carrier_identity_confirmation)


class PersistConfirmedCarrierIdentityTests(unittest.IsolatedAsyncioTestCase):
    """Backend-owned carrier-confirmation persistence."""

    async def test_direct_backend_confirmation_upserts_staged_identity(self):
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
            caller_dot_number="1380078",
            identity_source="verify_carrier",
        )
        upsert = MagicMock(return_value=None)
        with patch.object(
            call_helpers.NegotiationDBService, "upsert_carrier_phone", new=upsert
        ):
            succeeded = await persist_confirmed_carrier_identity(context)

        self.assertTrue(succeeded)
        upsert.assert_called_once()
        self.assertTrue(context.carrier_identity_confirmed)


class GetLoadContextUpsertTests(unittest.IsolatedAsyncioTestCase):
    """get_load_context fires the upsert at start, after verbal confirmation.

    The defense-in-depth persistence path is gated by
    HIGHWAY_PHONE_LOOKUP_ENABLED, so all tests in this class set the flag
    via setUp / tearDown. Tests that explicitly need flag=false still
    cover the gated-off case via test_skip_when_phone_first_disabled
    below.
    """

    def setUp(self):
        # Gating: get_load_context's persistence fallback only runs when
        # the phone-first feature is enabled. Tests in this class verify
        # the persistence behavior, so we enable the flag.
        self._env_patch = patch.dict(
            os.environ, {"HIGHWAY_PHONE_LOOKUP_ENABLED": "true"}
        )
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    def _patch_load_lookup(self, raw_load):
        # raw_load=None triggers DatabaseOperationError ("No load found"),
        # which is caught and returned to the LLM as status=error. That's
        # fine for these tests — the upsert runs BEFORE the load lookup.
        return patch.object(
            call_helpers.NegotiationDBService,
            "get_load_by_reference",
            new=MagicMock(return_value=raw_load),
        )

    async def test_defense_in_depth_upsert_when_confirm_was_skipped(self):
        # LLM forgot (or hadn't yet) to call confirm_carrier_identity →
        # carrier_identity_confirmed is False → defense-in-depth fires.
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
            caller_dot_number="1380078",
            carrier_identity_confirmed=False,
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(return_value=None)

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "REF-1234"},
                None, context, cb,
            )

        upsert.assert_called_once()
        kwargs = upsert.call_args.kwargs
        self.assertEqual(kwargs["phone_e164"], "+14155550100")
        self.assertEqual(kwargs["mc_number"], "123456")
        self.assertEqual(kwargs["carrier_name"], "Acme Trucking")
        self.assertEqual(kwargs["dot_number"], "1380078")
        self.assertEqual(kwargs["org_id"], "00000000-0000-0000-0000-000000000001")
        # Flag now set so subsequent get_load_context calls don't re-write.
        self.assertTrue(context.carrier_identity_confirmed)

    async def test_rejects_empty_load_id(self):
        """LLM compliance regression: when the LLM calls get_load_context
        prematurely (e.g. parallel with confirm_carrier_identity, before
        the caller has given a reference), reject with an error and skip
        the upsert + the SF lookup."""
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb, captured = await _collect_callback()
        upsert = MagicMock(return_value=None)
        sf_lookup = MagicMock(return_value=None)
        with (
            patch.object(call_helpers.NegotiationDBService,
                         "get_load_by_reference", new=sf_lookup),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": ""},
                None, context, cb,
            )

        # Neither the upsert nor the Salesforce lookup should fire.
        upsert.assert_not_called()
        sf_lookup.assert_not_called()
        # LLM gets an instructive error so it asks the caller for the reference.
        result = json.loads(captured["payload"])
        self.assertEqual(result["status"], "error")
        self.assertIn("reference number", result["message"].lower())

    async def test_rejects_bogus_load_id_with_spaces(self):
        """Regression for the production trace where the LLM emitted
        get_load_context(load_id='Noted down') in parallel with
        confirm_carrier_identity — pulling 'Noted down' from the caller's
        earlier MC turn ('Yeah. Noted down. One two three four five six.').
        The bogus value must be rejected before it hits Salesforce."""
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb, captured = await _collect_callback()
        upsert = MagicMock(return_value=None)
        sf_lookup = MagicMock(return_value=None)
        with (
            patch.object(call_helpers.NegotiationDBService,
                         "get_load_by_reference", new=sf_lookup),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "Noted down"},
                None, context, cb,
            )

        # No SF lookup — the bogus value should never reach the DB.
        sf_lookup.assert_not_called()
        # No defense-in-depth upsert either; we treat this as a misfire.
        upsert.assert_not_called()
        result = json.loads(captured["payload"])
        self.assertEqual(result["status"], "error")
        self.assertIn("reference number", result["message"].lower())

    async def test_rejects_load_id_without_digits(self):
        """All-letters load_id ('your load', 'reference') is hallucinated
        prose. Real references always include digits."""
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb, captured = await _collect_callback()
        sf_lookup = MagicMock(return_value=None)
        with (
            patch.object(call_helpers.NegotiationDBService,
                         "get_load_by_reference", new=sf_lookup),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=MagicMock()),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "reference"},
                None, context, cb,
            )

        sf_lookup.assert_not_called()
        result = json.loads(captured["payload"])
        self.assertEqual(result["status"], "error")

    async def test_skip_when_phone_first_disabled(self):
        """Gating regression: with HIGHWAY_PHONE_LOOKUP_ENABLED=false the
        defense-in-depth must not run — preserves zero behavior change vs.
        pre-PR baseline on the unknown-carrier path."""
        # Override the class-level setUp that turned the flag on.
        with patch.dict(os.environ, {"HIGHWAY_PHONE_LOOKUP_ENABLED": "false"}):
            context = _make_context(
                caller_mc="123456",
                carrier_name="Acme Trucking",
                carrier_identity_confirmed=False,
            )
            cb, _ = await _collect_callback()
            upsert = MagicMock(return_value=None)

            with (
                self._patch_load_lookup(None),
                patch.object(
                    call_helpers.NegotiationDBService,
                    "upsert_carrier_phone",
                    new=upsert,
                ),
            ):
                await get_load_context(
                    "get_load_context", "tcid", {"load_id": "REF-1234"},
                    None, context, cb,
                )

        upsert.assert_not_called()

    async def test_skip_when_already_confirmed_via_tool(self):
        # confirm_carrier_identity already ran in this call →
        # get_load_context should NOT re-write the row.
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
            carrier_identity_confirmed=True,
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(return_value=None)

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "REF-1234"},
                None, context, cb,
            )

        upsert.assert_not_called()

    async def test_upsert_runs_even_when_load_not_found(self):
        """Carrier confirmation is settled before get_load_context fires.
        Load lookup failure shouldn't cancel the cache write."""
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb, captured = await _collect_callback()
        upsert = MagicMock(return_value=None)

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "BAD-001"},
                None, context, cb,
            )

        upsert.assert_called_once()
        # And the LLM still got an error response for the missing load.
        result = json.loads(captured["payload"])
        self.assertEqual(result["status"], "error")

    async def test_skip_when_carrier_name_missing(self):
        """verify_carrier returned not_found → carrier_name never set →
        we don't have a confirmed identity to cache."""
        context = _make_context(
            caller_mc="999999",
            carrier_name=None,
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(return_value=None)

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "REF-1234"},
                None, context, cb,
            )

        upsert.assert_not_called()

    async def test_skip_when_caller_mc_missing(self):
        context = _make_context(
            caller_mc=None,
            carrier_name="Acme Trucking",
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(return_value=None)

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "REF-1234"},
                None, context, cb,
            )

        upsert.assert_not_called()

    async def test_skip_when_caller_phone_missing(self):
        context = _make_context(
            caller_phone=None,
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(return_value=None)

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "REF-1234"},
                None, context, cb,
            )

        upsert.assert_not_called()

    async def test_skip_when_org_id_missing(self):
        context = _make_context(
            org_id=None,
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(return_value=None)

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "REF-1234"},
                None, context, cb,
            )

        upsert.assert_not_called()

    async def test_upsert_failure_doesnt_break_get_load_context(self):
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb, captured = await _collect_callback()
        upsert = MagicMock(side_effect=RuntimeError("DB down"))

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "REF-1234"},
                None, context, cb,
            )

        upsert.assert_called_once()
        # Tool response still completes; cache failure was logged + swallowed.
        self.assertIn("payload", captured)

    async def test_flag_reverted_when_upsert_fails(self):
        """Retry-safety: a transient Supabase error inside get_load_context
        must not pin `carrier_identity_confirmed` to True. Otherwise a
        follow-up tool call (e.g., a second get_load_context after the
        caller corrects the reference number) would skip its retry."""
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(side_effect=RuntimeError("DB down"))

        with (
            self._patch_load_lookup(None),
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
        ):
            await get_load_context(
                "get_load_context", "tcid", {"load_id": "REF-1234"},
                None, context, cb,
            )

        self.assertFalse(context.carrier_identity_confirmed)


class ConfirmCarrierIdentityTests(unittest.IsolatedAsyncioTestCase):
    """confirm_carrier_identity tool: primary write path on caller's 'yes'."""

    async def test_upsert_when_identity_came_from_verify_carrier(self):
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
            caller_dot_number="1380078",
            identity_source="verify_carrier",
        )
        cb, captured = await _collect_callback()
        upsert = MagicMock(return_value=None)
        with patch.object(
            call_helpers.NegotiationDBService, "upsert_carrier_phone", new=upsert
        ):
            await confirm_carrier_identity(
                "confirm_carrier_identity", "tcid", {}, None, context, cb,
            )
        upsert.assert_called_once()
        kwargs = upsert.call_args.kwargs
        self.assertEqual(kwargs["phone_e164"], "+14155550100")
        self.assertEqual(kwargs["mc_number"], "123456")
        self.assertEqual(kwargs["carrier_name"], "Acme Trucking")
        self.assertTrue(context.carrier_identity_confirmed)
        # Tool returns a clean ok response so the LLM moves on.
        self.assertEqual(json.loads(captured["payload"]), {"status": "ok"})
        self.assertIs(captured["properties"].run_llm, False)

    async def test_upsert_when_identity_came_from_highway(self):
        # Highway hit on phone-first lookup → row not yet in Supabase → write.
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
            identity_source="highway",
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(return_value=None)
        with patch.object(
            call_helpers.NegotiationDBService, "upsert_carrier_phone", new=upsert
        ):
            await confirm_carrier_identity(
                "confirm_carrier_identity", "tcid", {}, None, context, cb,
            )
        upsert.assert_called_once()
        self.assertTrue(context.carrier_identity_confirmed)

    async def test_skip_when_already_confirmed_by_parallel_call(self):
        """Race regression: if get_load_context's defense-in-depth already
        set the flag (parallel tool calls in the same LLM turn), confirm
        must bail without a redundant write."""
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
            identity_source="verify_carrier",
            carrier_identity_confirmed=True,  # set by a concurrent caller
        )
        cb, captured = await _collect_callback()
        upsert = MagicMock(return_value=None)
        with patch.object(
            call_helpers.NegotiationDBService, "upsert_carrier_phone", new=upsert
        ):
            await confirm_carrier_identity(
                "confirm_carrier_identity", "tcid", {}, None, context, cb,
            )
        upsert.assert_not_called()
        self.assertEqual(json.loads(captured["payload"]), {"status": "ok"})

    async def test_skip_when_identity_from_supabase(self):
        # Phone-first hit on Supabase → row already up-to-date → skip write.
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
            identity_source="supabase",
        )
        cb, captured = await _collect_callback()
        upsert = MagicMock(return_value=None)
        with patch.object(
            call_helpers.NegotiationDBService, "upsert_carrier_phone", new=upsert
        ):
            await confirm_carrier_identity(
                "confirm_carrier_identity", "tcid", {}, None, context, cb,
            )
        upsert.assert_not_called()
        # Still flagged as confirmed so the get_load_context fallback doesn't write.
        self.assertTrue(context.carrier_identity_confirmed)
        self.assertEqual(json.loads(captured["payload"]), {"status": "ok"})

    async def test_skip_when_state_incomplete(self):
        # No carrier_name on context (e.g. tool was called by mistake before
        # verify_carrier completed). _persist_phone_carrier_mapping skips
        # cleanly; tool still returns ok.
        context = _make_context(caller_mc="123456", carrier_name=None)
        cb, captured = await _collect_callback()
        upsert = MagicMock(return_value=None)
        with patch.object(
            call_helpers.NegotiationDBService, "upsert_carrier_phone", new=upsert
        ):
            await confirm_carrier_identity(
                "confirm_carrier_identity", "tcid", {}, None, context, cb,
            )
        upsert.assert_not_called()
        self.assertEqual(json.loads(captured["payload"]), {"status": "ok"})

    async def test_upsert_failure_doesnt_break_response(self):
        context = _make_context(
            caller_mc="123456", carrier_name="Acme Trucking",
        )
        cb, captured = await _collect_callback()
        upsert = MagicMock(side_effect=RuntimeError("DB down"))
        with patch.object(
            call_helpers.NegotiationDBService, "upsert_carrier_phone", new=upsert
        ):
            await confirm_carrier_identity(
                "confirm_carrier_identity", "tcid", {}, None, context, cb,
            )
        upsert.assert_called_once()
        # Tool still returns ok — the LLM should not block on a cache failure.
        self.assertEqual(json.loads(captured["payload"]), {"status": "ok"})

    async def test_flag_reverted_when_upsert_fails(self):
        """Retry-safety regression: a transient Supabase failure must NOT
        leave `carrier_identity_confirmed` set, otherwise the
        get_load_context defense-in-depth path would silently skip its
        retry and the cache would never populate for this call."""
        context = _make_context(
            caller_mc="123456", carrier_name="Acme Trucking",
        )
        cb, _ = await _collect_callback()
        upsert = MagicMock(side_effect=RuntimeError("DB down"))
        with patch.object(
            call_helpers.NegotiationDBService, "upsert_carrier_phone", new=upsert
        ):
            await confirm_carrier_identity(
                "confirm_carrier_identity", "tcid", {}, None, context, cb,
            )
        self.assertFalse(context.carrier_identity_confirmed)

    async def test_retry_after_failed_confirm_via_get_load_context(self):
        """End-to-end retry: confirm_carrier_identity hits a transient DB
        error, then get_load_context (the same call session, later turn)
        successfully writes the row. Asserts the defense-in-depth path
        actually retries instead of being shut out by a stale flag."""
        context = _make_context(
            caller_mc="123456", carrier_name="Acme Trucking",
        )
        cb, _ = await _collect_callback()

        upsert = MagicMock(side_effect=[RuntimeError("DB blip"), None])

        env = patch.dict(os.environ, {"HIGHWAY_PHONE_LOOKUP_ENABLED": "true"})
        env.start()
        try:
            with (
                patch.object(call_helpers.NegotiationDBService,
                             "upsert_carrier_phone", new=upsert),
                patch.object(call_helpers.NegotiationDBService,
                             "get_load_by_reference",
                             new=MagicMock(return_value=None)),
            ):
                # First attempt — confirm_carrier_identity, hits DB error.
                await confirm_carrier_identity(
                    "confirm_carrier_identity", "tcid", {}, None, context, cb,
                )
                self.assertFalse(context.carrier_identity_confirmed)

                # Subsequent turn — get_load_context, retries and succeeds.
                await get_load_context(
                    "get_load_context", "tcid", {"load_id": "REF-1234"},
                    None, context, cb,
                )
        finally:
            env.stop()

        # Both attempts ran (failure then success), and the flag is set
        # only after the successful retry.
        self.assertEqual(upsert.call_count, 2)
        self.assertTrue(context.carrier_identity_confirmed)


class IsPlausibleLoadReferenceTests(unittest.TestCase):
    """Unit tests for the structural load_id validator that screens out
    hallucinated/transcript-junk references before they hit Salesforce."""

    def test_real_references_pass(self):
        for ref in ["TEST-001", "REF1234", "L_2026_001", "abc-99", "K1"]:
            with self.subTest(ref=ref):
                self.assertTrue(call_helpers._is_plausible_load_reference(ref))

    def test_empty_or_whitespace_rejected(self):
        for ref in ["", " ", "   "]:
            with self.subTest(ref=ref):
                # The caller strips before passing in; empty after strip
                # collapses to "", which the helper rejects.
                self.assertFalse(
                    call_helpers._is_plausible_load_reference(ref.strip())
                )

    def test_contains_space_rejected(self):
        # Production hallucination case: the LLM pulled "Noted down" from
        # an earlier turn and submitted it as a load_id.
        for ref in ["Noted down", "your load", "load 123"]:
            with self.subTest(ref=ref):
                self.assertFalse(
                    call_helpers._is_plausible_load_reference(ref)
                )

    def test_no_digits_rejected(self):
        # All-letter strings are prose, not references.
        for ref in ["reference", "abc", "TEST"]:
            with self.subTest(ref=ref):
                self.assertFalse(
                    call_helpers._is_plausible_load_reference(ref)
                )

    def test_unusual_punctuation_rejected(self):
        # Periods, slashes, parentheses appear in transcribed speech, not
        # in real reference IDs.
        for ref in ["TEST.001", "REF/123", "(123)"]:
            with self.subTest(ref=ref):
                self.assertFalse(
                    call_helpers._is_plausible_load_reference(ref)
                )


class ConcurrentPersistenceTests(unittest.IsolatedAsyncioTestCase):
    """Race regression for the parallel-emit + first-attempt-failure case.

    The LLM may emit confirm_carrier_identity AND get_load_context as
    parallel tool calls in the same turn ('yes, the reference is X').
    If confirm's upsert hits a transient Supabase error, the second
    coroutine must still retry the write — otherwise a single DB blip
    silently drops the phone-carrier mapping for the rest of the call.

    The serializing asyncio.Lock + 'set flag only on success' rule is
    what closes that gap; these tests pin that behavior.
    """

    def setUp(self):
        self._env_patch = patch.dict(
            os.environ, {"HIGHWAY_PHONE_LOOKUP_ENABLED": "true"}
        )
        self._env_patch.start()

    def tearDown(self):
        self._env_patch.stop()

    async def test_concurrent_first_fails_second_succeeds(self):
        """confirm fails, get_load_context (concurrent) successfully retries.

        Both coroutines run via asyncio.gather. The lock forces the second
        to observe the post-failure flag (False), so it retries instead of
        skipping on a stale True from the early-set pattern.
        """
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb1, _ = await _collect_callback()
        cb2, _ = await _collect_callback()

        # First call (confirm) raises; second call (get_load_context retry)
        # succeeds. side_effect order matches the lock's serial execution.
        upsert = MagicMock(side_effect=[RuntimeError("DB blip"), None])

        with (
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
            patch.object(call_helpers.NegotiationDBService,
                         "get_load_by_reference",
                         new=MagicMock(return_value=None)),
        ):
            await asyncio.gather(
                confirm_carrier_identity(
                    "confirm_carrier_identity", "tcid1", {},
                    None, context, cb1,
                ),
                get_load_context(
                    "get_load_context", "tcid2", {"load_id": "REF-1234"},
                    None, context, cb2,
                ),
            )

        self.assertEqual(upsert.call_count, 2)
        self.assertTrue(context.carrier_identity_confirmed)

    async def test_concurrent_both_succeed_writes_once(self):
        """Happy parallel-emit: only one upsert runs.

        Without the lock + late-set rule, both paths would hit the DB
        because neither would observe the flag in time. With them, the
        second path acquires the lock after the first has set the flag
        and bails cleanly.
        """
        context = _make_context(
            caller_mc="123456",
            carrier_name="Acme Trucking",
        )
        cb1, _ = await _collect_callback()
        cb2, _ = await _collect_callback()

        upsert = MagicMock(return_value=None)

        with (
            patch.object(call_helpers.NegotiationDBService,
                         "upsert_carrier_phone", new=upsert),
            patch.object(call_helpers.NegotiationDBService,
                         "get_load_by_reference",
                         new=MagicMock(return_value=None)),
        ):
            await asyncio.gather(
                confirm_carrier_identity(
                    "confirm_carrier_identity", "tcid1", {},
                    None, context, cb1,
                ),
                get_load_context(
                    "get_load_context", "tcid2", {"load_id": "REF-1234"},
                    None, context, cb2,
                ),
            )

        self.assertEqual(upsert.call_count, 1)
        self.assertTrue(context.carrier_identity_confirmed)


if __name__ == "__main__":
    unittest.main()
