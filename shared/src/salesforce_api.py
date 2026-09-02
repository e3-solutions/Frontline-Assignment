"""Salesforce REST API client for the KCH TMS (Revenova rtms__ package).

Uses OAuth 2.0 Client Credentials flow and caches access tokens in-process.
Only wraps the read paths needed by the negotiation bots (load lookup by
reference / SF Id / lane). Sync httpx matches the existing DB call style.
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from loguru import logger


class SalesforceAPIError(Exception):
    """Raised for any Salesforce REST API failure."""


BIDDABLE_STATUSES: tuple[str, ...] = (
    "Unassigned",
    "Quotes Requested",
    "Quotes Received",
    "Tendered",
)


def _escape_soql_string(value: str) -> str:
    """Escape single quotes and backslashes in SOQL string literals."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


class SalesforceAPI:
    """Thin client for rtms__Load__c reads over the Salesforce REST API."""

    API_VERSION = "v61.0"
    # Salesforce access tokens typically last ~2h; refresh conservatively.
    TOKEN_LIFETIME_SECONDS = 60 * 90

    def __init__(
        self,
        token_url: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        client: httpx.Client | None = None,
        timeout: float = 15.0,
    ) -> None:
        self._token_url = token_url or os.environ["SALESFORCE_TOKEN_URL"]
        self._client_id = client_id or os.environ["SALESFORCE_CLIENT_ID"]
        self._client_secret = client_secret or os.environ["SALESFORCE_CLIENT_SECRET"]
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._access_token: str | None = None
        self._instance_url: str | None = None
        self._token_expires_at: float = 0.0

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()

    # ── Auth ──────────────────────────────────────────────────────

    def _authenticate(self) -> None:
        try:
            res = self._client.post(
                self._token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.TimeoutException as e:
            raise SalesforceAPIError("Salesforce auth timed out") from e
        except httpx.RequestError as e:
            raise SalesforceAPIError(f"Salesforce auth failed: {e}") from e

        if res.status_code != 200:
            try:
                payload = res.json()
                msg = payload.get("error_description") or payload.get("error") or res.text
            except Exception:
                msg = res.text
            raise SalesforceAPIError(f"Salesforce auth failed: {msg}")

        data = res.json()
        self._access_token = data["access_token"]
        self._instance_url = data["instance_url"]
        self._token_expires_at = time.time() + self.TOKEN_LIFETIME_SECONDS
        logger.info(f"Salesforce authenticated; instance={self._instance_url}")

    def _ensure_auth(self) -> None:
        if not self._access_token or time.time() >= self._token_expires_at:
            self._authenticate()

    # ── Query ─────────────────────────────────────────────────────

    def query(self, soql: str) -> list[dict[str, Any]]:
        """Run a SOQL query and return the records list."""
        self._ensure_auth()
        records = self._query_once(soql)
        return records

    def _query_once(self, soql: str, _retry_on_401: bool = True) -> list[dict[str, Any]]:
        url = f"{self._instance_url}/services/data/{self.API_VERSION}/query"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        try:
            res = self._client.get(url, params={"q": soql}, headers=headers)
        except httpx.TimeoutException as e:
            raise SalesforceAPIError("Salesforce query timed out") from e
        except httpx.RequestError as e:
            raise SalesforceAPIError(f"Salesforce query failed: {e}") from e

        if res.status_code == 401 and _retry_on_401:
            # Token invalidated server-side — re-auth once and retry.
            self._authenticate()
            return self._query_once(soql, _retry_on_401=False)

        if res.status_code != 200:
            try:
                payload = res.json()
                if isinstance(payload, list):
                    msg = "; ".join(
                        f"{e.get('errorCode')}: {e.get('message')}" for e in payload
                    )
                else:
                    msg = str(payload)
            except Exception:
                msg = res.text
            raise SalesforceAPIError(f"SOQL failed: {msg}")

        return res.json().get("records", [])

    # ── Load helpers ──────────────────────────────────────────────

    def get_load_by_id(self, sf_id: str) -> dict[str, Any] | None:
        """Fetch a load by Salesforce 18-char Id."""
        sf_id = _escape_soql_string(sf_id)
        soql = (
            f"SELECT FIELDS(ALL) FROM rtms__Load__c "
            f"WHERE Id = '{sf_id}' LIMIT 1"
        )
        records = self.query(soql)
        return records[0] if records else None

    def get_load_by_name(self, name: str) -> dict[str, Any] | None:
        """Fetch a load by business reference (rtms__Load__c.Name)."""
        name = _escape_soql_string(name)
        soql = (
            f"SELECT FIELDS(ALL) FROM rtms__Load__c "
            f"WHERE Name = '{name}' LIMIT 1"
        )
        records = self.query(soql)
        return records[0] if records else None

    def search_loads_by_lane(
        self,
        origin_city: str | None = None,
        origin_state: str | None = None,
        destination_city: str | None = None,
        destination_state: str | None = None,
        biddable_only: bool = True,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search loads by origin/destination city/state.

        Origin/destination live in `rtms__Origin__c` / `rtms__Destination__c`
        as "City, State" strings, so each filter becomes a SOQL LIKE.
        """
        if not any((origin_city, origin_state, destination_city, destination_state)):
            return []

        where: list[str] = []
        if origin_city:
            where.append(f"rtms__Origin__c LIKE '%{_escape_soql_string(origin_city)}%'")
        if origin_state:
            where.append(f"rtms__Origin__c LIKE '%{_escape_soql_string(origin_state)}%'")
        if destination_city:
            where.append(f"rtms__Destination__c LIKE '%{_escape_soql_string(destination_city)}%'")
        if destination_state:
            where.append(f"rtms__Destination__c LIKE '%{_escape_soql_string(destination_state)}%'")
        if biddable_only:
            statuses = ", ".join(f"'{s}'" for s in BIDDABLE_STATUSES)
            where.append(f"rtms__Load_Status__c IN ({statuses})")

        soql = (
            f"SELECT FIELDS(ALL) FROM rtms__Load__c "
            f"WHERE {' AND '.join(where)} LIMIT {int(limit)}"
        )
        return self.query(soql)
