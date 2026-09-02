"""Unit tests for HighwayAPI using httpx.MockTransport."""

from __future__ import annotations

import json
import os
import unittest
from unittest.mock import patch

import httpx

from src.highway_api import (
    CarrierLookupResult,
    HighwayAPI,
    HighwayAPIError,
    _digits_only,
    _normalize_to_e164,
    humanize_carrier_name,
)


CARRIER_DETAIL = {
    "id": 40,
    "legal_name": "ACME TRUCKING INC",
    "dba_name": "ACME TRUCKING",
    "mc_number": 123456,
    "dot_number": 1380078,
    "connection": {"status": "onboarded"},
    "identifiers": [{"is_type": "MC", "value": "123456"}],
}


def _phone_search_hit(
    category: str = "phone_of_carrier",
    *,
    carriers: list[dict] | None = None,
) -> dict:
    """Build a phone_search response envelope with the real production shape.

    Real shape (verified via probe-highway.py against +17708764159):
        {"phone_search_result_category": <enum>, "carriers": [<carrier>, ...]}
    """
    if carriers is None:
        carriers = [dict(CARRIER_DETAIL)]
    return {"phone_search_result_category": category, "carriers": carriers}


class HighwayAPIClientTests(unittest.IsolatedAsyncioTestCase):
    def _make_api(self, handler) -> HighwayAPI:
        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport)
        return HighwayAPI(client=client)

    # ----- phone_search -----------------------------------------------------

    async def test_phone_search_known_carrier(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "POST")
            self.assertTrue(request.url.path.endswith("/v1/carriers/phone_search"))
            return httpx.Response(200, json=_phone_search_hit("phone_of_carrier"))

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_phone("+14155550100")

        self.assertEqual(result.status, "known_carrier")
        # DBA preferred AND humanized for verbal output.
        self.assertEqual(result.carrier_name, "Acme Trucking")
        self.assertEqual(result.mc_number, "123456")
        self.assertEqual(result.highway_carrier_id, "40")

    async def test_phone_search_not_found(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"phone_search_result_category": "phone_number_not_known"},
            )

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_phone("+14155550100")

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "not_found")
        self.assertIsNone(result.carrier_name)
        self.assertIsNone(result.mc_number)

    async def test_phone_search_identity_alert(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json=_phone_search_hit("found_phone_of_carrier_with_identity_alert"),
            )

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_phone("+14155550100")

        self.assertEqual(result.status, "known_carrier")
        self.assertEqual(result.mc_number, "123456")

    async def test_phone_search_no_mc_in_any_carrier(self):
        body = _phone_search_hit(
            "phone_of_carrier",
            carriers=[{**CARRIER_DETAIL, "mc_number": None}],
        )

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=body)

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_phone("+14155550100")

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "no_mc_in_any_carrier")

    async def test_phone_search_ambiguous_multiple_mcs(self):
        # Two carriers, BOTH have MCs — refuse to guess, fall back to MC flow.
        # Replaces the previous "first wins" policy after PR review surfaced
        # the auth-confusion risk on shared/ambiguous phones.
        first = {**CARRIER_DETAIL, "id": 100, "mc_number": 1040141, "dba_name": "WALLIN"}
        second = {**CARRIER_DETAIL, "id": 200, "mc_number": 222222, "dba_name": "OTHER"}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_phone_search_hit(
                "found_phone_associated_with_multiple_carriers",
                carriers=[first, second],
            ))

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_phone("+17708764159")

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "ambiguous_multiple_mcs")
        self.assertIsNone(result.carrier_name)
        self.assertIsNone(result.mc_number)

    async def test_phone_search_multi_carriers_single_mc(self):
        # Multiple carriers in the response but only ONE has an MC — that's
        # an unambiguous match (the no-MC entries are typically census-level
        # placeholders). Use it; tag with reason="multi_carriers_single_mc"
        # for observability.
        first = {**CARRIER_DETAIL, "id": 100, "mc_number": None}
        second = {**CARRIER_DETAIL, "id": 200, "mc_number": 222222, "dba_name": "PICKED"}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_phone_search_hit(
                "found_phone_associated_with_multiple_carriers",
                carriers=[first, second],
            ))

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_phone("+17708764159")

        self.assertEqual(result.status, "known_carrier")
        self.assertEqual(result.mc_number, "222222")
        self.assertEqual(result.carrier_name, "Picked")  # humanized
        self.assertEqual(result.highway_carrier_id, "200")
        self.assertEqual(result.reason, "multi_carriers_single_mc")

    async def test_phone_search_single_carrier_no_reason(self):
        # Single carrier with an MC — happy path, reason should be None.
        only = {**CARRIER_DETAIL, "id": 40, "mc_number": 123456}

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_phone_search_hit(
                "phone_of_carrier", carriers=[only],
            ))

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_phone("+14155550100")

        self.assertEqual(result.status, "known_carrier")
        self.assertEqual(result.mc_number, "123456")
        self.assertIsNone(result.reason)

    async def test_phone_search_multi_match_none_has_mc(self):
        # Multiple carriers, none have MC — fall back to MC flow.
        carriers = [
            {**CARRIER_DETAIL, "id": 100, "mc_number": None},
            {**CARRIER_DETAIL, "id": 200, "mc_number": None},
        ]

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_phone_search_hit(
                "found_phone_associated_with_multiple_carriers",
                carriers=carriers,
            ))

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_phone("+17708764159")

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "no_mc_in_any_carrier")

    async def test_phone_search_5xx_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, text="upstream error")

        api = self._make_api(handler)
        with self.assertRaises(HighwayAPIError) as ctx:
            await api.lookup_carrier_by_phone("+14155550100")
        self.assertIn("503", str(ctx.exception))

    async def test_phone_search_timeout_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("simulated timeout", request=request)

        api = self._make_api(handler)
        with self.assertRaises(HighwayAPIError) as ctx:
            await api.lookup_carrier_by_phone("+14155550100")
        self.assertIn("timed out", str(ctx.exception).lower())

    # ----- by_identifier (MC) -----------------------------------------------

    async def test_by_identifier_mc_known_carrier(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.assertEqual(request.method, "GET")
            self.assertIn(
                "/v1/carriers/MC/123456/by_identifier", str(request.url)
            )
            return httpx.Response(200, json=CARRIER_DETAIL)

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_mc("123456")

        self.assertEqual(result.status, "known_carrier")
        self.assertEqual(result.carrier_name, "Acme Trucking")
        self.assertEqual(result.mc_number, "123456")

    async def test_by_identifier_mc_not_found_plain_text(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="identifier not found")

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_mc("99999999")

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "not_found")

    async def test_by_identifier_mc_invalid_input(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(200, json=CARRIER_DETAIL)

        api = self._make_api(handler)
        result = await api.lookup_carrier_by_mc("abc")

        self.assertEqual(result.status, "unknown")
        self.assertEqual(result.reason, "invalid_mc")
        self.assertEqual(call_count, 0)

    async def test_by_identifier_mc_5xx_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        api = self._make_api(handler)
        with self.assertRaises(HighwayAPIError):
            await api.lookup_carrier_by_mc("123456")

    # ----- cross-cutting ----------------------------------------------------

    async def test_phone_normalized_to_e164(self):
        captured: dict[str, dict] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content.decode())
            return httpx.Response(
                200,
                json={"phone_search_result_category": "phone_number_not_known"},
            )

        api = self._make_api(handler)
        await api.lookup_carrier_by_phone("(415) 555-0100")

        self.assertEqual(captured["body"], {"phone_e164": "+4155550100"})

    async def test_auth_header_present(self):
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["auth"] = request.headers.get("Authorization", "")
            return httpx.Response(
                200,
                json={"phone_search_result_category": "phone_number_not_known"},
            )

        api = self._make_api(handler)
        with patch.dict(os.environ, {"HIGHWAY_API_KEY": "test-key-xyz"}):
            await api.lookup_carrier_by_phone("+14155550100")

        self.assertEqual(captured["auth"], "Bearer test-key-xyz")


class NormalizationHelperTests(unittest.TestCase):
    def test_normalize_to_e164_formatted(self):
        self.assertEqual(_normalize_to_e164("(415) 555-0100"), "+4155550100")

    def test_normalize_to_e164_already_e164(self):
        self.assertEqual(_normalize_to_e164("+14155550100"), "+14155550100")

    def test_normalize_to_e164_empty(self):
        self.assertEqual(_normalize_to_e164(""), "")

    def test_digits_only(self):
        self.assertEqual(_digits_only("MC-123 456"), "123456")
        self.assertEqual(_digits_only("abc"), "")


class HumanizeCarrierNameTests(unittest.TestCase):
    def test_basic_all_caps_to_title(self):
        self.assertEqual(
            humanize_carrier_name("WALLIN TRANSPORT LLC"),
            "Wallin Transport LLC",
        )

    def test_preserves_already_mixed_case(self):
        self.assertEqual(
            humanize_carrier_name("McDonald's Trucking LLC"),
            "McDonald's Trucking LLC",
        )

    def test_preserves_short_acronyms(self):
        # 2-3 letter all-caps tokens stay uppercase (likely acronyms).
        self.assertEqual(humanize_carrier_name("JB HUNT"), "JB Hunt")
        self.assertEqual(
            humanize_carrier_name("ABC TRANSPORTATION INC"),
            "ABC Transportation INC",
        )

    def test_preserves_business_suffixes(self):
        for suffix in ("LLC", "INC", "CORP", "LTD", "LP", "USA"):
            self.assertEqual(
                humanize_carrier_name(f"BIGRIG {suffix}"),
                f"Bigrig {suffix}",
            )

    def test_none_and_empty_passthrough(self):
        self.assertIsNone(humanize_carrier_name(None))
        self.assertEqual(humanize_carrier_name(""), "")


if __name__ == "__main__":
    unittest.main()
