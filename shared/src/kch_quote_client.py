"""KCH Carrier Quote API client.

POSTs agreed carrier quotes to the KCH endpoint which creates
rtms__CarrierQuote__c records in Salesforce. Uses AWS Cognito
OAuth 2.0 Client Credentials for authentication.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from loguru import logger


class KCHQuoteError(Exception):
    """Base error for KCH carrier quote API failures."""

    def __init__(self, message: str, code: str | None = None, status: int | None = None):
        super().__init__(message)
        self.code = code
        self.status = status


class KCHValidationError(KCHQuoteError):
    """Raised for 400-level validation errors (bad payload)."""


class KCHNotFoundError(KCHQuoteError):
    """Raised for 404 errors (load/carrier/service not found)."""


QUOTE_ENDPOINT = "https://agent.kch-api-services.net/carrier_quote"
COGNITO_TOKEN_URL = "https://kch-m2m.auth.us-east-2.amazoncognito.com/oauth2/token"


class KCHQuoteClient:
    """Client for the KCH carrier quote creation endpoint."""

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        scope: str | None = None,
        use_sandbox: bool | None = None,
        client: httpx.Client | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._client_id = client_id or os.environ["KCH_QUOTE_CLIENT_ID"]
        self._client_secret = client_secret or os.environ["KCH_QUOTE_CLIENT_SECRET"]
        self._scope = scope or os.environ["KCH_QUOTE_SCOPE"]

        sandbox_env = os.environ.get("KCH_QUOTE_USE_SANDBOX", "").strip().lower()
        self._use_sandbox = use_sandbox if use_sandbox is not None else (sandbox_env == "true")

        self._http = client or httpx.Client(timeout=timeout)
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    def _authenticate(self) -> str:
        now = time.monotonic()
        if self._access_token and now < self._token_expires_at:
            return self._access_token

        resp = self._http.post(
            COGNITO_TOKEN_URL,
            data={
                "grant_type": "client_credentials",
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "scope": self._scope,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if resp.status_code != 200:
            raise KCHQuoteError(
                f"Cognito auth failed ({resp.status_code}): {resp.text}",
                code="AUTH_FAILED",
                status=resp.status_code,
            )

        body = resp.json()
        self._access_token = body["access_token"]
        expires_in = body.get("expires_in", 3600)
        self._token_expires_at = now + expires_in - 60
        return self._access_token

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = self._authenticate()
        resp = self._http.post(
            QUOTE_ENDPOINT,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )

        if resp.status_code == 201:
            return resp.json()

        # Parse error body
        try:
            err = resp.json()
        except Exception:
            err = {"code": "UNKNOWN", "message": resp.text}

        code = err.get("code", "UNKNOWN")
        message = err.get("message", resp.text)

        if resp.status_code == 401:
            # Token expired mid-flight — clear cache and retry once
            self._access_token = None
            self._token_expires_at = 0
            token = self._authenticate()
            resp = self._http.post(
                QUOTE_ENDPOINT,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
            )
            if resp.status_code == 201:
                return resp.json()
            try:
                err = resp.json()
            except Exception:
                err = {"code": "UNKNOWN", "message": resp.text}
            code = err.get("code", "UNKNOWN")
            message = err.get("message", resp.text)

        if resp.status_code == 404:
            raise KCHNotFoundError(message, code=code, status=404)
        if 400 <= resp.status_code < 500:
            raise KCHValidationError(message, code=code, status=resp.status_code)

        raise KCHQuoteError(message, code=code, status=resp.status_code)

    def submit_quote(
        self,
        load_name: str,
        amount: float,
        mc_number: str | None = None,
        dot_number: str | None = None,
        source_type: str | None = None,
        carrier_name: str | None = None,
        carrier_email: str | None = None,
        carrier_phone: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Submit a carrier quote to KCH. Returns the SF CarrierQuote Id."""
        if not mc_number and not dot_number:
            raise KCHValidationError(
                "At least one of mc_number or dot_number is required",
                code="MISSING_CARRIER_ID",
            )

        carrier: dict[str, Any] = {}
        if mc_number:
            carrier["mcNumber"] = mc_number
        if dot_number:
            carrier["dotNumber"] = dot_number

        payload: dict[str, Any] = {
            "loadId": load_name,
            "amount": amount,
            "carrier": carrier,
        }

        if self._use_sandbox:
            payload["useSandbox"] = True

        if notes:
            payload["notes"] = notes

        from_party: dict[str, Any] = {}
        if carrier_name:
            from_party["name"] = carrier_name
        if carrier_email:
            from_party["email"] = carrier_email
        if carrier_phone:
            phone_digits = "".join(c for c in carrier_phone if c.isdigit())
            if phone_digits:
                e164 = f"+1{phone_digits}" if len(phone_digits) == 10 else f"+{phone_digits}"
                from_party["phone"] = {"e164Number": e164}

        if source_type or from_party:
            source: dict[str, Any] = {}
            if source_type:
                source["sourceType"] = source_type
            if from_party:
                from_party["partyType"] = "carrier"
                source["fromParty"] = from_party
            payload["source"] = source

        logger.info(f"Submitting carrier quote to KCH: load={load_name}, amount={amount}")
        result = self._post(payload)
        quote_id = result.get("id", "")
        logger.info(f"KCH carrier quote created: {quote_id}")
        return quote_id
