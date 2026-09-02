"""Tests for KCH carrier quote API client."""

from __future__ import annotations

import json
import unittest

import httpx

from src.kch_quote_client import (
    COGNITO_TOKEN_URL,
    QUOTE_ENDPOINT,
    KCHNotFoundError,
    KCHQuoteClient,
    KCHQuoteError,
    KCHValidationError,
)


def _token_response(expires_in: int = 3600) -> dict:
    return {
        "access_token": "test-token-abc",
        "expires_in": expires_in,
        "token_type": "Bearer",
    }


def _build_transport(responses: list[httpx.Response]) -> httpx.MockTransport:
    """Return a mock transport that yields responses in order."""
    call_index = {"i": 0}
    call_log: list[httpx.Request] = []

    def handler(request: httpx.Request):
        call_log.append(request)
        idx = call_index["i"]
        call_index["i"] += 1
        if idx < len(responses):
            return responses[idx]
        return httpx.Response(500, json={"code": "UNEXPECTED", "message": "No more mocked responses"})

    transport = httpx.MockTransport(handler)
    transport.call_log = call_log  # type: ignore[attr-defined]
    return transport


class TestCognitoAuth(unittest.TestCase):
    def test_authenticates_and_caches_token(self):
        transport = _build_transport([
            httpx.Response(200, json=_token_response()),
            httpx.Response(201, json={"id": "quote-1"}),
            httpx.Response(201, json={"id": "quote-2"}),
        ])
        client = KCHQuoteClient(
            client_id="test-id",
            client_secret="test-secret",
            scope="test/scope",
            client=httpx.Client(transport=transport),
        )

        client.submit_quote("LOAD-1", 1500, mc_number="123456")
        client.submit_quote("LOAD-2", 2000, mc_number="789012")

        # Only 3 requests total: 1 auth + 2 quotes (token was cached)
        self.assertEqual(len(transport.call_log), 3)
        self.assertIn("oauth2/token", str(transport.call_log[0].url))
        self.assertIn("carrier_quote", str(transport.call_log[1].url))
        self.assertIn("carrier_quote", str(transport.call_log[2].url))

    def test_retries_on_401(self):
        transport = _build_transport([
            httpx.Response(200, json=_token_response()),
            httpx.Response(401, json={"code": "UNAUTHORIZED", "message": "expired"}),
            httpx.Response(200, json=_token_response()),
            httpx.Response(201, json={"id": "quote-after-retry"}),
        ])
        client = KCHQuoteClient(
            client_id="test-id",
            client_secret="test-secret",
            scope="test/scope",
            client=httpx.Client(transport=transport),
        )

        result = client.submit_quote("LOAD-1", 1500, mc_number="123456")
        self.assertEqual(result, "quote-after-retry")

    def test_auth_failure_raises(self):
        transport = _build_transport([
            httpx.Response(400, json={"error": "invalid_client"}),
        ])
        client = KCHQuoteClient(
            client_id="bad-id",
            client_secret="bad-secret",
            scope="test/scope",
            client=httpx.Client(transport=transport),
        )

        with self.assertRaises(KCHQuoteError) as ctx:
            client.submit_quote("LOAD-1", 1500, mc_number="123456")
        self.assertEqual(ctx.exception.code, "AUTH_FAILED")


class TestSubmitQuote(unittest.TestCase):
    def _make_client(self, responses: list[httpx.Response]) -> tuple[KCHQuoteClient, httpx.MockTransport]:
        all_responses = [httpx.Response(200, json=_token_response())] + responses
        transport = _build_transport(all_responses)
        client = KCHQuoteClient(
            client_id="test-id",
            client_secret="test-secret",
            scope="test/scope",
            client=httpx.Client(transport=transport),
        )
        return client, transport

    def test_minimal_payload(self):
        client, transport = self._make_client([
            httpx.Response(201, json={"id": "q-123"}),
        ])

        result = client.submit_quote("9391159", 1500, mc_number="123456")

        self.assertEqual(result, "q-123")
        # Check the payload sent
        req = transport.call_log[1]
        body = json.loads(req.content)
        self.assertEqual(body["loadId"], "9391159")
        self.assertEqual(body["amount"], 1500)
        self.assertEqual(body["carrier"], {"mcNumber": "123456"})
        self.assertNotIn("source", body)

    def test_full_payload_with_source(self):
        client, transport = self._make_client([
            httpx.Response(201, json={"id": "q-456"}),
        ])

        result = client.submit_quote(
            "9391159",
            2000,
            mc_number="123456",
            dot_number="789012",
            source_type="email",
            carrier_name="Test Carrier",
            carrier_email="carrier@example.com",
            carrier_phone="5551234567",
        )

        self.assertEqual(result, "q-456")
        body = json.loads(transport.call_log[1].content)
        self.assertEqual(body["source"]["sourceType"], "email")
        self.assertEqual(body["source"]["fromParty"]["name"], "Test Carrier")
        self.assertEqual(body["source"]["fromParty"]["email"], "carrier@example.com")
        self.assertEqual(body["source"]["fromParty"]["partyType"], "carrier")
        self.assertIn("phone", body["source"]["fromParty"])
        self.assertEqual(body["carrier"]["mcNumber"], "123456")
        self.assertEqual(body["carrier"]["dotNumber"], "789012")

    def test_dot_number_only(self):
        client, transport = self._make_client([
            httpx.Response(201, json={"id": "q-dot"}),
        ])

        result = client.submit_quote("LOAD-1", 1000, dot_number="999888")
        self.assertEqual(result, "q-dot")
        body = json.loads(transport.call_log[1].content)
        self.assertEqual(body["carrier"], {"dotNumber": "999888"})

    def test_requires_mc_or_dot(self):
        client, _ = self._make_client([])

        with self.assertRaises(KCHValidationError):
            client.submit_quote("LOAD-1", 1500)

    def test_sandbox_flag(self):
        all_responses = [
            httpx.Response(200, json=_token_response()),
            httpx.Response(201, json={"id": "q-sb"}),
        ]
        transport = _build_transport(all_responses)
        client = KCHQuoteClient(
            client_id="test-id",
            client_secret="test-secret",
            scope="test/scope",
            use_sandbox=True,
            client=httpx.Client(transport=transport),
        )

        client.submit_quote("LOAD-1", 1500, mc_number="123")
        body = json.loads(transport.call_log[1].content)
        self.assertTrue(body["useSandbox"])

    def test_load_not_found_raises_not_found_error(self):
        client, _ = self._make_client([
            httpx.Response(404, json={"code": "LOAD_NOT_FOUND", "message": "Load not found"}),
        ])

        with self.assertRaises(KCHNotFoundError) as ctx:
            client.submit_quote("BAD-LOAD", 1500, mc_number="123")
        self.assertEqual(ctx.exception.code, "LOAD_NOT_FOUND")

    def test_validation_error_raises(self):
        client, _ = self._make_client([
            httpx.Response(400, json={"code": "VALIDATION_ERROR", "message": "Missing amount"}),
        ])

        with self.assertRaises(KCHValidationError) as ctx:
            client.submit_quote("LOAD-1", 0, mc_number="123")
        self.assertEqual(ctx.exception.code, "VALIDATION_ERROR")

    def test_server_error_raises_base_error(self):
        client, _ = self._make_client([
            httpx.Response(500, json={"code": "CREATE_FAILED", "message": "SF rejected insert"}),
        ])

        with self.assertRaises(KCHQuoteError) as ctx:
            client.submit_quote("LOAD-1", 1500, mc_number="123")
        self.assertEqual(ctx.exception.code, "CREATE_FAILED")
        self.assertEqual(ctx.exception.status, 500)


if __name__ == "__main__":
    unittest.main()
