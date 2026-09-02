"""Backend phone-first carrier verification.

`resolve_caller_identity` is called at the start of every inbound call, before
the LLM generates its greeting. It looks up the caller's PSTN number against
TWO sources concurrently:

1. **Highway API** (`POST /v1/carriers/phone_search`) — third-party identity
   data fingerprinted from census + dispatch sources.
2. **Supabase `phone_carrier_lookup`** — KCH-owned lookup table of (phone, MC)
   pairs verified during prior bot conversations. Scoped per-org (the bot
   phone's org).

If EITHER source returns a known carrier, the bot uses it and skips the
MC-collection step. On conflict, Supabase wins (KCH-curated truth trumps
Highway's general data). If both miss, the bot falls back to the MC-first
greeting.

This function NEVER raises. Any failure mode collapses to
`CarrierLookupResult.unknown(reason=<cause>)`.
"""

from __future__ import annotations

import asyncio
import os

from loguru import logger

from src import (
    CarrierLookupResult,
    HighwayAPI,
    HighwayAPIError,
    NegotiationDBService,
    humanize_carrier_name,
)


_DEFAULT_TIMEOUT_S = 1.5


def _is_well_formed_e164(value: str) -> bool:
    """Loose E.164 sanity: leading '+', 7-15 digits, nothing else."""
    if not value.startswith("+"):
        return False
    rest = value[1:]
    return rest.isdigit() and 7 <= len(rest) <= 15


def _flag_enabled() -> bool:
    return os.getenv("HIGHWAY_PHONE_LOOKUP_ENABLED", "false").lower() == "true"


def _timeout_seconds() -> float:
    try:
        return float(os.getenv("HIGHWAY_PHONE_LOOKUP_TIMEOUT_S", str(_DEFAULT_TIMEOUT_S)))
    except ValueError:
        return _DEFAULT_TIMEOUT_S


async def _highway_lookup(caller_phone: str) -> CarrierLookupResult:
    """Highway phone_search wrapped in timeout + exception-to-unknown collapse."""
    api = HighwayAPI()
    try:
        return await asyncio.wait_for(
            api.lookup_carrier_by_phone(caller_phone),
            timeout=_timeout_seconds(),
        )
    except asyncio.TimeoutError:
        logger.warning(f"Highway phone lookup timed out for {caller_phone}")
        return CarrierLookupResult.unknown(reason="timeout")
    except HighwayAPIError as exc:
        logger.warning(f"Highway phone lookup failed: {exc}")
        return CarrierLookupResult.unknown(reason="api_error")
    except Exception:
        logger.exception("Unexpected Highway phone lookup error")
        return CarrierLookupResult.unknown(reason="unexpected_error")
    finally:
        await api.close()


async def _supabase_lookup(
    caller_phone: str, org_id: str | None,
) -> CarrierLookupResult:
    """Read from `phone_carrier_lookup` via the sync helper. Never raises."""
    if not org_id:
        return CarrierLookupResult.unknown(reason="no_org_id")
    try:
        row = await asyncio.to_thread(
            NegotiationDBService.get_carrier_by_phone, caller_phone, org_id,
        )
    except Exception:
        logger.exception("Supabase phone_carrier_lookup read failed")
        return CarrierLookupResult.unknown(reason="db_error")
    if not row:
        return CarrierLookupResult.unknown(reason="not_found")
    return CarrierLookupResult(
        status="known_carrier",
        # Defensive humanize: legacy rows written before the rename pass
        # may still be stored as ALL-CAPS.
        carrier_name=humanize_carrier_name(row.get("carrier_name")),
        mc_number=row.get("mc_number"),
        # Supabase doesn't store highway_carrier_id; leave None.
        reason="from_supabase_lookup",
    )


async def resolve_caller_identity(
    caller_phone: str | None, org_id: str | None,
) -> CarrierLookupResult:
    """Look up the caller's phone against Highway and Supabase in parallel.

    Resolution rules:
      1. Supabase known       → use Supabase (KCH-curated truth).
      2. Supabase db_error    → force MC-first (return unknown). Cannot
         honor Supabase precedence when the lookup table is unreachable;
         trusting Highway here would let stale Highway identity through
         and skip MC verification. Unsafe-open default = MC-first.
      3. Highway known        → use Highway (Supabase missed cleanly,
         Highway has a hit).
      4. Both unknown         → return unknown with the more-informative
         reason.

    Never raises.
    """
    if not _flag_enabled():
        return CarrierLookupResult.unknown(reason="feature_disabled")

    if not caller_phone or not _is_well_formed_e164(caller_phone):
        return CarrierLookupResult.unknown(reason="empty_or_malformed_phone")

    highway_result, supabase_result = await asyncio.gather(
        _highway_lookup(caller_phone),
        _supabase_lookup(caller_phone, org_id),
    )

    # 1. Supabase has the row → use it.
    if supabase_result.status == "known_carrier":
        return supabase_result

    # 2. Supabase outage → unsafe-open protection. We cannot verify the
    #    Supabase-precedence invariant; falling through to Highway risks
    #    greeting the caller with a stale identity that Supabase would
    #    have overruled. Force MC-first by returning unknown.
    if supabase_result.reason == "db_error":
        logger.warning(
            "Supabase phone_carrier_lookup unavailable; refusing to "
            "trust Highway and forcing MC-first verification"
        )
        return supabase_result

    # 3. Supabase cleanly missed (not_found / no_org_id) → fall through
    #    to Highway when it has a hit.
    if highway_result.status == "known_carrier":
        return highway_result

    # 4. Both unknown — surface Highway's reason if Supabase was just
    #    "not in the lookup table", since Highway's reason is usually
    #    more informative.
    if supabase_result.reason in ("not_found", "no_org_id"):
        return highway_result
    return supabase_result
