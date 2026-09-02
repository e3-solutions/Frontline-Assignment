"""Negotiation domain services.

Load reads (`get_load`, `get_load_by_reference`, `search_loads_by_location`)
are backed by KCH Supabase `public.loads` plus linked `public.stops`. Internal negotiation records
(agreements, carrier contact info) continue to live in Supabase. Method
signatures preserve compatibility with historical negotiation records.

`SalesforceAPI` is no longer used for load reads but is retained elsewhere
for KCH quote submission (`notify_carrier_quote`).
"""

from datetime import datetime, timezone

from loguru import logger

from src.kch_quote_client import KCHQuoteClient, KCHQuoteError
from src.supabase_service import SupabaseService


# Use the explicit FK constraint name (`stops_load_number_fkey`) instead of
# letting PostgREST auto-discover the relationship. Auto-discovery relies on
# Supabase's API-worker schema cache, which has been observed to lag after
# DDL changes even after `NOTIFY pgrst, 'reload schema'`. The explicit hint
# bypasses the cache lookup entirely.
LOAD_SELECT = "*, stops!stops_load_number_fkey(*)"

# Bound lane-search fetches independently of the PostgREST default page size.
LANE_SEARCH_CANDIDATE_LIMIT = 200


def _decorate_load_record(record: dict | None) -> dict | None:
    """Add `id` / `load_id` aliases pointing at `load_number`.

    Voice callers (call_helpers.py) read `load["id"]` and
    `load["load_id"]`. Aliasing here keeps the call sites unchanged.
    """
    if not record:
        return record
    load_number = record.get("load_number")
    if load_number is not None:
        record.setdefault("id", load_number)
        record.setdefault("load_id", load_number)
    return record


def _normalize_match_text(value: object | None) -> str:
    return str(value or "").strip().casefold()


def _ordered_stops(record: dict) -> list[dict]:
    stops = record.get("stops")
    if isinstance(stops, dict):
        stops = [stops]
    if not isinstance(stops, list):
        return []
    return sorted(
        [stop for stop in stops if isinstance(stop, dict)],
        key=lambda stop: (
            stop.get("stop_number") is None,
            stop.get("stop_number") or 0,
        ),
    )


def _find_lane_stop(record: dict, action_key: str, *, reverse: bool = False) -> dict | None:
    stops = _ordered_stops(record)
    ordered = list(reversed(stops)) if reverse else stops
    for stop in ordered:
        if stop.get(action_key) is True:
            return stop
    return ordered[0] if ordered else None


def _stop_matches(stop: dict | None, *, city: str | None, state: str | None) -> bool:
    if not city and not state:
        return True
    if not stop:
        return False

    stop_city = _normalize_match_text(stop.get("stop_city") or stop.get("city"))
    stop_state = _normalize_match_text(stop.get("state_code"))
    wanted_city = _normalize_match_text(city)
    wanted_state = _normalize_match_text(state)

    if wanted_city and wanted_city not in stop_city:
        return False
    if wanted_state and wanted_state != stop_state:
        return False
    return True


def _load_matches_lane(
    record: dict,
    *,
    origin_city: str | None,
    origin_state: str | None,
    destination_city: str | None,
    destination_state: str | None,
) -> bool:
    pickup_stop = _find_lane_stop(record, "is_pickup")
    dropoff_stop = _find_lane_stop(record, "is_dropoff", reverse=True)
    return _stop_matches(pickup_stop, city=origin_city, state=origin_state) and _stop_matches(
        dropoff_stop,
        city=destination_city,
        state=destination_state,
    )


class NegotiationDBService:
    """Shared DB operations for the negotiation domain."""

    _kch: KCHQuoteClient | None = None

    @classmethod
    def _kch_client(cls) -> KCHQuoteClient:
        if cls._kch is None:
            cls._kch = KCHQuoteClient()
        return cls._kch

    @classmethod
    def _db(cls):
        return SupabaseService.get_client()

    # ── Load reads (KCH Supabase `public.loads`) ─────────────────

    @classmethod
    def _query_load(cls, column: str, value: str) -> dict | None:
        """Look up a single `loads` row by an indexed column."""
        result = (
            cls._db()
            .table("loads")
            .select(LOAD_SELECT)
            .eq(column, value)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    @classmethod
    def get_load(cls, load_id: str) -> dict | None:
        """Get a load from `public.loads` by `load_number`, falling back to `salesforce_load_id`."""
        if not load_id:
            return None
        record = cls._query_load("load_number", load_id)
        if record is None:
            record = cls._query_load("salesforce_load_id", load_id)
        return _decorate_load_record(record)

    @classmethod
    def get_load_by_reference(cls, load_id: str, org_id: str | None = None) -> dict | None:
        """Get a load by reference. Behaves like `get_load`.

        `org_id` is accepted for signature compatibility; KCH's current load
        schema does not carry tenant ownership on load rows.
        """
        return cls.get_load(load_id)

    @classmethod
    def search_loads_by_location(
        cls,
        origin_city: str | None = None,
        origin_state: str | None = None,
        destination_city: str | None = None,
        destination_state: str | None = None,
        org_id: str | None = None,
    ) -> list[dict]:
        """Search KCH loads by pickup/dropoff stop city and state.

        Restricted server-side to biddable loads (`ready_to_cover = TRUE`,
        which the customer schema documents as "load is ready to be covered
        by a carrier; expect to receive calls if true") to exclude loads
        that are already covered or not yet released. Capped at ``LANE_SEARCH_CANDIDATE_LIMIT`` rows to keep
        the candidate fetch deterministic instead of relying on PostgREST's
        default page size.

        Two-stop city/state matching is still applied in Python because
        `is_pickup` / `is_dropoff` live on the embedded `stops` rows and
        PostgREST cannot express "the pickup stop matches X AND the dropoff
        stop matches Y" through the embedded filter syntax.
        """
        if not any((origin_city, origin_state, destination_city, destination_state)):
            return []

        result = (
            cls._db()
            .table("loads")
            .select(LOAD_SELECT)
            .eq("ready_to_cover", True)
            .limit(LANE_SEARCH_CANDIDATE_LIMIT)
            .execute()
        )
        return [
            _decorate_load_record(record)
            for record in (result.data or [])
            if _load_matches_lane(
                record,
                origin_city=origin_city,
                origin_state=origin_state,
                destination_city=destination_city,
                destination_state=destination_state,
            )
        ]

    # ── Negotiation writes (Supabase) ────────────────────────────

    @classmethod
    def create_negotiation(
        cls,
        load_id: str,
        agreed_price: float,
        agent_type: str = "voice",
        above_max: bool = False,
        carrier_contact_name: str | None = None,
        carrier_contact_phone: str | None = None,
        carrier_contact_email: str | None = None,
        call_id: str | None = None,
        thread_id: str | None = None,
    ) -> dict:
        """Create a negotiation record in Supabase."""
        data = {
            "load_id": load_id,
            "agreed_price": agreed_price,
            "above_max": above_max,
            "agent_type": agent_type,
        }

        if call_id:
            data["call_id"] = call_id
        if thread_id:
            data["thread_id"] = thread_id
        if carrier_contact_name:
            data["carrier_contact_name"] = carrier_contact_name
        if carrier_contact_phone:
            data["carrier_contact_phone"] = carrier_contact_phone
        if carrier_contact_email:
            data["carrier_contact_email"] = carrier_contact_email

        result = cls._db().table("negotiations").insert(data).execute()
        return result.data[0] if result.data else {}


    # ── Phone-carrier lookup (Supabase) ──────────────────────────

    @classmethod
    def get_carrier_by_phone(
        cls, phone_e164: str, org_id: str,
    ) -> dict | None:
        """Look up a verified (phone, MC) entry in `phone_carrier_lookup`.

        Returns the row dict (with phone_e164, mc_number, carrier_name,
        dot_number, last_verified_at) or None if no entry exists for the
        given (org_id, phone_e164) pair.

        Database errors are NOT swallowed — they propagate to the caller
        so the voice-agent's phone_verification layer can distinguish a
        legitimate "row missing" (return None) from a Supabase outage
        (raise) and apply the correct precedence rule. Without this
        distinction, a Supabase blip would silently degrade to "no entry"
        and let stale Highway data through, violating the
        Supabase-precedence invariant.
        """
        if not phone_e164 or not org_id:
            return None
        result = (
            cls._db()
            .table("phone_carrier_lookup")
            .select(
                "phone_e164, mc_number, carrier_name, dot_number, last_verified_at"
            )
            .eq("org_id", org_id)
            .eq("phone_e164", phone_e164)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    @classmethod
    def upsert_carrier_phone(
        cls,
        *,
        phone_e164: str,
        mc_number: str,
        carrier_name: str | None,
        dot_number: str | None,
        org_id: str,
    ) -> None:
        """Idempotent upsert keyed on (org_id, phone_e164). Bumps last_verified_at.

        Self-correcting on retries: each call overwrites the prior row, so the
        lookup table always reflects the most recently verified MC for that
        phone+org. Silent no-op if any required field is missing.
        """
        if not phone_e164 or not mc_number or not org_id:
            return
        now = datetime.now(timezone.utc).isoformat()
        cls._db().table("phone_carrier_lookup").upsert(
            {
                "org_id": org_id,
                "phone_e164": phone_e164,
                "mc_number": mc_number,
                "carrier_name": carrier_name,
                "dot_number": dot_number,
                "last_verified_at": now,
                "updated_at": now,
            },
            on_conflict="org_id,phone_e164",
        ).execute()

    # ── KCH carrier quote notification ──────────────────────────

    @classmethod
    def notify_carrier_quote(
        cls,
        load_name: str,
        agreed_price: float,
        mc_number: str | None = None,
        dot_number: str | None = None,
        source_type: str | None = None,
        carrier_name: str | None = None,
        carrier_email: str | None = None,
        carrier_phone: str | None = None,
    ) -> str | None:
        """POST an accepted quote to KCH. Returns the SF quote ID or None on failure.

        Skips the call (with a warning) if neither MC nor DOT number is available.
        Never raises — errors are logged so the caller's reply flow is not blocked.
        """
        if not mc_number and not dot_number:
            logger.warning(
                f"Skipping KCH quote notification for load {load_name}: "
                "no MC or DOT number available"
            )
            return None

        try:
            return cls._kch_client().submit_quote(
                load_name=load_name,
                amount=agreed_price,
                mc_number=mc_number,
                dot_number=dot_number,
                source_type=source_type,
                carrier_name=carrier_name,
                carrier_email=carrier_email,
                carrier_phone=carrier_phone,
            )
        except KCHQuoteError as e:
            logger.error(
                f"KCH quote notification failed for load {load_name}: "
                f"[{e.code}] {e}"
            )
            return None
        except Exception as e:
            logger.error(f"Unexpected error notifying KCH for load {load_name}: {e}")
            return None
