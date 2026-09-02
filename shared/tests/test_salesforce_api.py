"""Unit tests for SalesforceAPI using a mocked httpx transport."""

from __future__ import annotations

import json
import unittest
from urllib.parse import parse_qs

import httpx

from src.salesforce_api import (
    BIDDABLE_STATUSES,
    SalesforceAPI,
    SalesforceAPIError,
    _escape_soql_string,
)


TOKEN_URL = "https://kchtransportation.my.salesforce.com/services/oauth2/token"
INSTANCE_URL = "https://kchtransportation.my.salesforce.com"


def _token_response():
    return httpx.Response(
        200,
        json={
            "access_token": "TOKEN",
            "instance_url": INSTANCE_URL,
            "token_type": "Bearer",
            "scope": "api",
            "issued_at": "1000",
        },
    )


class SalesforceAPIClientTests(unittest.TestCase):
    def _make_client(self, handler):
        transport = httpx.MockTransport(handler)
        http_client = httpx.Client(transport=transport)
        return SalesforceAPI(
            token_url=TOKEN_URL,
            client_id="cid",
            client_secret="secret",
            client=http_client,
        )

    def test_authenticate_on_first_query_and_caches_token(self):
        auth_calls = 0
        query_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal auth_calls, query_calls
            if request.url.path == "/services/oauth2/token":
                auth_calls += 1
                form = parse_qs(request.content.decode())
                self.assertEqual(form["grant_type"], ["client_credentials"])
                self.assertEqual(form["client_id"], ["cid"])
                self.assertEqual(form["client_secret"], ["secret"])
                return _token_response()
            if request.url.path.endswith("/query"):
                query_calls += 1
                self.assertEqual(
                    request.headers["Authorization"], "Bearer TOKEN"
                )
                return httpx.Response(200, json={"records": [{"Name": "42"}]})
            return httpx.Response(404)

        sf = self._make_client(handler)
        sf.query("SELECT Id FROM rtms__Load__c LIMIT 1")
        sf.query("SELECT Id FROM rtms__Load__c LIMIT 1")

        self.assertEqual(auth_calls, 1)  # cached across queries
        self.assertEqual(query_calls, 2)

    def test_401_triggers_reauth_and_retry(self):
        auth_calls = 0
        query_calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal auth_calls, query_calls
            if request.url.path == "/services/oauth2/token":
                auth_calls += 1
                return _token_response()
            if request.url.path.endswith("/query"):
                query_calls += 1
                if query_calls == 1:
                    return httpx.Response(401, json={"error": "INVALID_SESSION_ID"})
                return httpx.Response(200, json={"records": [{"Name": "42"}]})
            return httpx.Response(404)

        sf = self._make_client(handler)
        records = sf.query("SELECT Id FROM rtms__Load__c LIMIT 1")

        self.assertEqual(records, [{"Name": "42"}])
        self.assertEqual(auth_calls, 2)
        self.assertEqual(query_calls, 2)

    def test_soql_error_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/services/oauth2/token":
                return _token_response()
            return httpx.Response(
                400,
                json=[{"errorCode": "MALFORMED_QUERY", "message": "bad SOQL"}],
            )

        sf = self._make_client(handler)
        with self.assertRaises(SalesforceAPIError) as ctx:
            sf.query("SELECT bogus")
        self.assertIn("MALFORMED_QUERY", str(ctx.exception))

    def test_auth_error_raises(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                400,
                json={"error": "invalid_client", "error_description": "bad creds"},
            )

        sf = self._make_client(handler)
        with self.assertRaises(SalesforceAPIError) as ctx:
            sf.query("SELECT Id FROM rtms__Load__c LIMIT 1")
        self.assertIn("bad creds", str(ctx.exception))

    def test_get_load_by_name_builds_expected_soql(self):
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/services/oauth2/token":
                return _token_response()
            captured["q"] = request.url.params["q"]
            return httpx.Response(
                200,
                json={
                    "records": [
                        {
                            "attributes": {"type": "rtms__Load__c"},
                            "Id": "a1GTQ000008EiIE2A0",
                            "Name": "9391159",
                        }
                    ]
                },
            )

        sf = self._make_client(handler)
        record = sf.get_load_by_name("9391159")

        self.assertEqual(record["Name"], "9391159")
        self.assertIn("rtms__Load__c", captured["q"])
        self.assertIn("Name = '9391159'", captured["q"])

    def test_search_loads_by_lane_filters_biddable_statuses(self):
        captured: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/services/oauth2/token":
                return _token_response()
            captured["q"] = request.url.params["q"]
            return httpx.Response(200, json={"records": []})

        sf = self._make_client(handler)
        sf.search_loads_by_lane(origin_city="Laredo", destination_state="TN")

        for status in BIDDABLE_STATUSES:
            self.assertIn(status, captured["q"])
        self.assertIn("LIKE '%Laredo%'", captured["q"])
        self.assertIn("LIKE '%TN%'", captured["q"])

    def test_search_loads_by_lane_with_no_filters_returns_empty(self):
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(500)

        sf = self._make_client(handler)
        self.assertEqual(sf.search_loads_by_lane(), [])
        self.assertEqual(call_count, 0)

    def test_escape_soql_string(self):
        self.assertEqual(_escape_soql_string("O'Brien"), "O\\'Brien")
        self.assertEqual(_escape_soql_string("a\\b"), "a\\\\b")


if __name__ == "__main__":
    unittest.main()
