"""Highway API client for carrier lookups.

Two primary use cases in the voice-agent:
- phone_search: look up a carrier by inbound caller PSTN number (pre-greeting).
- by_identifier (MC): verify a carrier by MC number.

Both methods return a CarrierLookupResult. Transport errors and non-success HTTP
responses are raised as HighwayAPIError; structural "not found" responses are
returned as CarrierLookupResult.unknown(reason="not_found").
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import wraps
from typing import Any, Literal

import httpx


class HighwayAPIError(Exception):
    """Exception raised for Highway API errors."""
    pass


def handle_request_errors(func):
    """Decorator to handle httpx errors uniformly."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except httpx.TimeoutException as e:
            raise HighwayAPIError("Highway API request timed out") from e
        except httpx.RequestError as e:
            raise HighwayAPIError(f"Highway API request failed: {e}") from e
    return wrapper


CarrierLookupStatus = Literal["known_carrier", "unknown"]


@dataclass(frozen=True)
class CarrierLookupResult:
    """Result of a Highway carrier lookup.

    status="known_carrier" — Highway returned an identifiable carrier with an MC.
    status="unknown"       — lookup completed but we don't have a usable carrier
                             (not found, mc missing, malformed input, etc).
    """
    status: CarrierLookupStatus
    carrier_name: str | None = None
    mc_number: str | None = None
    highway_carrier_id: str | None = None
    reason: str | None = None

    @classmethod
    def unknown(cls, reason: str) -> "CarrierLookupResult":
        return cls(status="unknown", reason=reason)


class HighwayAPI:
    """Client for Highway API operations."""

    DEFAULT_BASE_URL = "https://highway.com/core/connect/external_api"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._owns_client = client is None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def close(self):
        if self._owns_client and self._client:
            await self._client.aclose()
            self._client = None

    def _base_url(self) -> str:
        return os.getenv("HIGHWAY_API_BASE_URL", self.DEFAULT_BASE_URL)

    def _auth_headers(self) -> dict[str, str]:
        api_key = os.getenv("HIGHWAY_API_KEY", "")
        return {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        }

    @handle_request_errors
    async def check_carrier_workable(self, email: str, mc_number: str) -> dict[str, Any]:
        """Stub — not wired to anything. Kept for later cleanup."""
        client = await self._get_client()
        url = f"{self.DEFAULT_BASE_URL}/carriers/check"
        response = await client.post(url, json={"email": email, "mc_number": mc_number})
        if response.status_code != 200:
            raise HighwayAPIError(f"Highway API returned status {response.status_code}")
        return response.json()

    @handle_request_errors
    async def lookup_carrier_by_phone(self, phone: str) -> CarrierLookupResult:
        """POST /v1/carriers/phone_search — ALWAYS returns HTTP 200.

        Response envelope contains a `carriers: [...]` array. Multi-carrier
        case picks the first carrier with a usable mc_number — see
        _parse_phone_search_response. Non-200 → HighwayAPIError.
        """
        client = await self._get_client()
        e164 = _normalize_to_e164(phone)
        url = f"{self._base_url()}/v1/carriers/phone_search"
        response = await client.post(
            url,
            json={"phone_e164": e164},
            headers=self._auth_headers(),
        )
        if response.status_code != 200:
            raise HighwayAPIError(
                f"phone_search returned status {response.status_code}"
            )
        return _parse_phone_search_response(response.json())

    @handle_request_errors
    async def lookup_carrier_by_mc(self, mc_number: str) -> CarrierLookupResult:
        """GET /v1/carriers/MC/{mc}/by_identifier.

        Thin wrapper over _lookup_by_identifier("MC", <digits>). Empty or
        non-numeric input short-circuits to unknown(reason="invalid_mc")
        before any HTTP call.
        """
        clean_mc = _digits_only(mc_number)
        if not clean_mc:
            return CarrierLookupResult.unknown(reason="invalid_mc")
        return await self._lookup_by_identifier("MC", clean_mc)

    async def _lookup_by_identifier(self, prefix: str, value: str) -> CarrierLookupResult:
        """GET /v1/carriers/{prefix}/{value}/by_identifier.

        200  → parse Carrier Detail.
        404  → unknown(reason="not_found"). Body is plain text ("identifier not
               found") — do NOT call .json() on it.
        Other non-200 → HighwayAPIError.
        """
        client = await self._get_client()
        url = f"{self._base_url()}/v1/carriers/{prefix}/{value}/by_identifier"
        response = await client.get(url, headers=self._auth_headers())
        if response.status_code == 404:
            return CarrierLookupResult.unknown(reason="not_found")
        if response.status_code != 200:
            raise HighwayAPIError(
                f"by_identifier returned status {response.status_code}"
            )
        return _parse_carrier_detail(response.json())


_BUSINESS_SUFFIXES = frozenset({
    "LLC", "L.L.C.", "INC", "INC.", "CORP", "CORP.", "CO", "CO.",
    "LTD", "LTD.", "LP", "LP.", "LLP", "LLP.", "PLLC", "PC", "USA",
})


def humanize_carrier_name(name: str | None) -> str | None:
    """Convert ALL-CAPS carrier names to natural Title Case for verbal output.

    Highway and the Carrier API often return names like 'WALLIN TRANSPORT LLC',
    which TTS engines and LLMs tend to read letter-by-letter. This converts
    ALL-CAPS words (4+ chars) to Title Case while preserving:
      - Common business suffixes (LLC, INC, CORP, ...)
      - Short tokens (1-3 chars — likely acronyms like JB, ABC)
      - Already-mixed-case words ('McDonald's', 'FedEx') — left untouched.

    Returns input unchanged when None or empty.
    """
    if not name:
        return name
    out: list[str] = []
    for word in name.split():
        if word.upper() in _BUSINESS_SUFFIXES:
            out.append(word.upper())
        elif word.isupper() and len(word) >= 4:
            out.append(word.capitalize())
        else:
            out.append(word)
    return " ".join(out)


def _normalize_to_e164(phone: str) -> str:
    """Light-touch cleanup so common shapes reach Highway as E.164.

    Full validation lives in the voice-agent wrapper (B2). This strips
    formatting characters and ensures a leading '+'. It does NOT add a
    country code if one is missing.
    """
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        return ""
    return "+" + digits


def _digits_only(value: str) -> str:
    return "".join(c for c in value if c.isdigit())


def _parse_carrier_detail(body: dict[str, Any]) -> CarrierLookupResult:
    """Extract carrier_name (DBA preferred, legal fallback), MC, highway id.

    Used for the by_identifier endpoint, which returns the Carrier Detail
    schema directly. Returns unknown(reason="mc_missing") if MC is absent.
    """
    data = body.get("data", body)
    carrier_name = data.get("dba_name") or data.get("legal_name")
    mc_value = data.get("mc_number")
    if mc_value is None:
        return CarrierLookupResult.unknown(reason="mc_missing")
    highway_id = data.get("id")
    return CarrierLookupResult(
        status="known_carrier",
        carrier_name=humanize_carrier_name(carrier_name),
        mc_number=str(mc_value),
        highway_carrier_id=str(highway_id) if highway_id is not None else None,
    )


def _parse_phone_search_response(body: dict[str, Any]) -> CarrierLookupResult:
    """Parse the phone_search response envelope.

    Real shape (verified via probe-highway.py):
        { "phone_search_result_category": <enum>,
          "carriers": [{"id", "legal_name", "dba_name", "mc_number", ...}, ...],
          ...other top-level metadata... }

    Multi-carrier policy (refined post-review of #110):
      - Exactly one carrier in the response has a non-null mc_number → use it
        (other entries are typically census-level placeholders without an MC).
      - More than one carrier has an mc_number → don't guess; return
        unknown(reason="ambiguous_multiple_mcs") and let the bot fall back to
        the MC-first flow. The caller's verbal MC is the disambiguation
        signal. (The Supabase phone_carrier_lookup row written after a
        successful MC verification then takes over on subsequent calls via
        Supabase precedence in resolve_caller_identity.)
      - None of the returned carriers has an MC → unknown(reason="no_mc_in_any_carrier").
    """
    category = body.get("phone_search_result_category")
    if category == "phone_number_not_known":
        return CarrierLookupResult.unknown(reason="not_found")

    carriers = body.get("carriers") or []
    if not carriers:
        return CarrierLookupResult.unknown(reason="no_carriers_in_response")

    mc_carriers = [c for c in carriers if c.get("mc_number") is not None]
    if not mc_carriers:
        return CarrierLookupResult.unknown(reason="no_mc_in_any_carrier")
    if len(mc_carriers) > 1:
        # Multiple operating carriers share this phone — refuse to guess.
        return CarrierLookupResult.unknown(reason="ambiguous_multiple_mcs")

    carrier = mc_carriers[0]
    name = carrier.get("dba_name") or carrier.get("legal_name")
    carrier_id = carrier.get("id")
    multi = len(carriers) > 1  # multiple carriers but only one has an MC
    return CarrierLookupResult(
        status="known_carrier",
        carrier_name=humanize_carrier_name(name),
        mc_number=str(carrier["mc_number"]),
        highway_carrier_id=str(carrier_id) if carrier_id is not None else None,
        reason="multi_carriers_single_mc" if multi else None,
    )
