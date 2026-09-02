"""Tests for the CARRIER_MC_BACKEND env-var router in carrier_service.

`fetch_carrier_by_mc` dispatches to either the legacy Carrier API on Railway
(`carrier_api`, the default) or the Highway by_identifier endpoint
(`highway`) based on the env var. Both backends must produce the same dict
shape so `call_helpers.verify_carrier` and `get_carrier_name` see identical
output regardless of which backend is active.

These tests mock at the carrier_service module boundary
(`_fetch_carrier_record` for the carrier_api path, `HighwayAPI` for the
highway path) so no real HTTP traffic happens.
"""

from __future__ import annotations

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

import carrier_service  # noqa: E402
from carrier_service import (  # noqa: E402
    CarrierServiceError,
    fetch_carrier_by_mc,
    get_carrier_name,
)


# A minimal Carrier API response (matches what _fetch_carrier_record returns
# from the Railway endpoint).
_CARRIER_API_RESPONSE = {
    "success": True,
    "data": {
        "dbaName": "Acme Trucking",
        "legalName": "Acme Trucking LLC",
        "mcNumber": "123456",
        "dotNumber": "1380078",
    },
}


def _highway_known_result() -> CarrierLookupResult:
    return CarrierLookupResult(
        status="known_carrier",
        carrier_name="Acme Trucking",
        mc_number="123456",
        highway_carrier_id="40",
    )


def _patch_highway(*, lookup_return=None, lookup_side_effect=None):
    """Return a patch that swaps HighwayAPI() with an AsyncMock.

    Mirrors the production class shape: instances expose
    `lookup_carrier_by_mc` (async) and `close` (async).
    """
    instance = AsyncMock()
    if lookup_side_effect is not None:
        instance.lookup_carrier_by_mc.side_effect = lookup_side_effect
    else:
        instance.lookup_carrier_by_mc.return_value = lookup_return
    instance.close.return_value = None
    return patch.object(carrier_service, "HighwayAPI", return_value=instance), instance


class CarrierServiceBackendTests(unittest.IsolatedAsyncioTestCase):
    # ----- carrier_api backend (default) -------------------------------------

    async def test_known_carrier_carrier_api(self):
        with (
            patch.dict(os.environ, {"CARRIER_MC_BACKEND": "carrier_api"}),
            patch.object(
                carrier_service,
                "_fetch_carrier_record",
                new=AsyncMock(return_value=_CARRIER_API_RESPONSE),
            ),
        ):
            result = await fetch_carrier_by_mc("123456")
        self.assertIsNotNone(result)
        # get_carrier_name should resolve via the dbaName path.
        self.assertEqual(get_carrier_name(result), "Acme Trucking")

    async def test_not_found_carrier_api(self):
        # _fetch_carrier_record returns None on 404.
        with (
            patch.dict(os.environ, {"CARRIER_MC_BACKEND": "carrier_api"}),
            patch.object(
                carrier_service,
                "_fetch_carrier_record",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await fetch_carrier_by_mc("999999")
        self.assertIsNone(result)

    async def test_5xx_raises_carrier_api(self):
        with (
            patch.dict(os.environ, {"CARRIER_MC_BACKEND": "carrier_api"}),
            patch.object(
                carrier_service,
                "_fetch_carrier_record",
                new=AsyncMock(side_effect=CarrierServiceError("Carrier API 503")),
            ),
        ):
            with self.assertRaises(CarrierServiceError):
                await fetch_carrier_by_mc("123456")

    # ----- highway backend ---------------------------------------------------

    async def test_known_carrier_highway(self):
        patcher, _ = _patch_highway(lookup_return=_highway_known_result())
        with (
            patch.dict(os.environ, {"CARRIER_MC_BACKEND": "highway"}),
            patcher,
        ):
            result = await fetch_carrier_by_mc("123456")
        self.assertIsNotNone(result)
        # Same get_carrier_name resolution as the carrier_api path.
        self.assertEqual(get_carrier_name(result), "Acme Trucking")
        # Translation should preserve the MC under the carrier_api shape.
        data = result.get("data", {})
        self.assertEqual(data.get("mcNumber"), "123456")

    async def test_not_found_highway(self):
        patcher, _ = _patch_highway(
            lookup_return=CarrierLookupResult.unknown(reason="not_found"),
        )
        with (
            patch.dict(os.environ, {"CARRIER_MC_BACKEND": "highway"}),
            patcher,
        ):
            result = await fetch_carrier_by_mc("999999")
        self.assertIsNone(result)

    async def test_5xx_raises_highway(self):
        # HighwayAPIError from the client must surface as CarrierServiceError
        # so call_helpers.verify_carrier's existing except block catches it.
        patcher, _ = _patch_highway(lookup_side_effect=HighwayAPIError("503"))
        with (
            patch.dict(os.environ, {"CARRIER_MC_BACKEND": "highway"}),
            patcher,
        ):
            with self.assertRaises(CarrierServiceError):
                await fetch_carrier_by_mc("123456")

    # ----- shared / cross-cutting -------------------------------------------

    async def test_invalid_mc_raises_before_dispatch(self):
        # Empty / non-numeric MC must reject before either backend is called.
        with (
            patch.dict(os.environ, {"CARRIER_MC_BACKEND": "highway"}),
            _patch_highway()[0] as _highway_p,
            patch.object(
                carrier_service,
                "_fetch_carrier_record",
                new=AsyncMock(),
            ) as carrier_api_mock,
        ):
            with self.assertRaises(CarrierServiceError):
                await fetch_carrier_by_mc("abc")  # no digits
            with self.assertRaises(CarrierServiceError):
                await fetch_carrier_by_mc("")
        carrier_api_mock.assert_not_called()

    async def test_unknown_backend_falls_back_to_carrier_api(self):
        # Misspelled or empty value → log a warning and dispatch to carrier_api.
        carrier_api_mock = AsyncMock(return_value=_CARRIER_API_RESPONSE)
        highway_patcher, highway_instance = _patch_highway(
            lookup_return=_highway_known_result(),
        )
        with (
            patch.dict(os.environ, {"CARRIER_MC_BACKEND": "garbage"}),
            patch.object(
                carrier_service, "_fetch_carrier_record", new=carrier_api_mock
            ),
            highway_patcher,
        ):
            result = await fetch_carrier_by_mc("123456")
        self.assertIsNotNone(result)
        carrier_api_mock.assert_awaited_once()
        highway_instance.lookup_carrier_by_mc.assert_not_called()


if __name__ == "__main__":
    unittest.main()
