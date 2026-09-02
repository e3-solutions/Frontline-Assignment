"""Utilities for normalizing mixed load schemas into one canonical shape."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

# Trucking / freight acronyms that must stay uppercase so TTS pronounces them
# as initialisms rather than lowercasing them into meaningless words.
# Deliberately excludes US state 2-letter codes because many overlap with
# common English words ("IN", "OR", "HI", "OK", "MA", "ME", "PA"); the voice
# prompt already instructs the LLM to speak state abbreviations as full names.
_PRESERVED_ACRONYMS = frozenset({
    "BOL", "POD", "ETA", "ETD", "TMS", "LTL", "FTL", "FSC",
    "MC", "DOT", "USDOT", "PPE", "PO", "ID", "EIN",
    "TL", "FCL", "LCL",
    "HAZMAT", "UN",
    "USA", "ASAP",
})

_ALL_CAPS_WORD_RE = re.compile(r"\b[A-Z]{2,}\b")
_SENTENCE_START_RE = re.compile(r"(^|[.!?\n]\s*)([a-z])")


class LoadLocation(BaseModel):
    """Canonical location shape used by prompts."""

    city: str = ""
    state: str = ""
    country: str | None = None
    timezone: str | None = None


class NormalizedLoad(BaseModel):
    """Canonical load shape consumed by the negotiation agents."""

    id: str = ""
    load_id: str = ""
    origin: LoadLocation = Field(default_factory=LoadLocation)
    destination: LoadLocation = Field(default_factory=LoadLocation)
    pickupTime: str | None = None
    dropoffTime: str | None = None
    equipment: str | None = None
    commodity: str | None = None
    isHazmat: bool | None = None
    specialInstructions: str | None = None
    trackerRequired: bool = False
    startRate: float = 0
    bookNowRate: float = 0
    maxRate: float = 0
    bookedRate: float | None = None
    customerName: str | None = None
    weight: float | None = None
    transfer_call_to: str | None = None
    transfer_country_code: str | None = None


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.strip()
        return cleaned or None
    return str(value)


def _parse_rate(value: object) -> float:
    if value in (None, "", "null"):
        return 0
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).strip().replace("$", "").replace(",", "")
    if not cleaned:
        return 0

    try:
        return float(cleaned)
    except ValueError:
        return 0


def _parse_optional_float(value: object) -> float | None:
    if value in (None, "", "null"):
        return None
    if isinstance(value, (int, float)):
        return float(value)

    cleaned = str(value).strip().replace(",", "")
    if not cleaned:
        return None

    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, "", "null"):
        return False
    if isinstance(value, (int, float)):
        return bool(value)

    cleaned = str(value).strip().lower()
    return cleaned in {"true", "t", "1", "yes", "y"}


def _first_value(*values: object) -> object | None:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _location_from_string(value: object) -> LoadLocation:
    text = _clean_str(value)
    if not text:
        return LoadLocation()

    parts = [part.strip() for part in text.split(",", 1)]
    if len(parts) == 2:
        return LoadLocation(city=parts[0], state=parts[1])
    return LoadLocation(city=text)


def _build_location(record: dict, prefix: str) -> LoadLocation:
    return LoadLocation(
        city=_clean_str(record.get(f"{prefix}_city")) or "",
        state=_clean_str(record.get(f"{prefix}_state")) or "",
        country=_clean_str(record.get(f"{prefix}_country")),
        timezone=_clean_str(record.get(f"{prefix}_timezone")),
    )


def _location_from_value(value: object) -> LoadLocation:
    if isinstance(value, dict):
        address = value.get("address") if isinstance(value.get("address"), dict) else None
        source = address or value
        return LoadLocation(
            city=_clean_str(source.get("city")) or "",
            state=_clean_str(source.get("state")) or "",
            country=_clean_str(source.get("country")),
            timezone=_clean_str(source.get("timezone")),
        )

    return _location_from_string(value)


def _resolve_reference_id(data: dict, fallback_load_id: object | None) -> str:
    # Prefer the indexed top-level loads.load_id so lookup and prompt reference stay aligned
    # even while mixed records still exist in the table.
    for candidate in (fallback_load_id, data.get("id"), data.get("load_id")):
        resolved = _clean_str(candidate)
        if resolved:
            return resolved
    return ""


def _normalize_caps_text(text: str | None) -> str | None:
    """Lowercase non-whitelisted ALL-CAPS runs so TTS reads them as prose.

    Preserves whitelisted trucking acronyms (BOL, POD, ETA, …) and any
    mixed-alphanumeric token (e.g., Salesforce IDs). Idempotent: strings
    without an ALL-CAPS run are returned unchanged.
    """
    if text is None:
        return None
    cleaned = text.strip()
    if not cleaned:
        return None

    non_whitelist_caps = [
        match
        for match in _ALL_CAPS_WORD_RE.findall(cleaned)
        if match not in _PRESERVED_ACRONYMS
    ]
    if not non_whitelist_caps:
        return cleaned

    def _lowercase_if_not_whitelisted(match: re.Match[str]) -> str:
        word = match.group(0)
        return word if word in _PRESERVED_ACRONYMS else word.lower()

    lowered = _ALL_CAPS_WORD_RE.sub(_lowercase_if_not_whitelisted, cleaned)
    return _SENTENCE_START_RE.sub(
        lambda m: m.group(1) + m.group(2).upper(), lowered
    )


def _build_special_instructions(data: dict) -> str | None:
    return _normalize_caps_text(
        _clean_str(_first_value(data.get("specialInstructions"), data.get("requirements")))
    )


def normalize_load_data(
    raw_data: dict | None, fallback_load_id: object | None = None
) -> dict:
    """Normalize load JSON into the canonical prompt shape."""
    data = raw_data or {}
    reference_id = _resolve_reference_id(data, fallback_load_id)

    normalized = NormalizedLoad(
        id=reference_id,
        load_id=reference_id,
        origin=_location_from_value(_first_value(data.get("origin"), data.get("origin_location"))),
        destination=_location_from_value(
            _first_value(data.get("destination"), data.get("destination_location"))
        ),
        pickupTime=_clean_str(
            _first_value(data.get("pickupTime"), data.get("pickup_time"), data.get("pickup_date"))
        ),
        dropoffTime=_clean_str(
            _first_value(
                data.get("dropoffTime"), data.get("delivery_time"), data.get("dropoff_date")
            )
        ),
        equipment=_clean_str(_first_value(data.get("equipment"), data.get("equipment_type"))),
        commodity=_normalize_caps_text(_clean_str(data.get("commodity"))),
        isHazmat=data.get("isHazmat"),
        specialInstructions=_build_special_instructions(data),
        trackerRequired=_parse_bool(
            _first_value(data.get("trackerRequired"), data.get("tracker_required"))
        ),
        startRate=_parse_rate(_first_value(data.get("startRate"), data.get("broker_initial_offer"))),
        bookNowRate=_parse_rate(
            _first_value(data.get("bookNowRate"), data.get("broker_target_rate"))
        ),
        maxRate=_parse_rate(_first_value(data.get("maxRate"), data.get("broker_max_rate"))),
        bookedRate=_parse_optional_float(data.get("bookedRate")),
        customerName=_clean_str(
            _first_value(data.get("customerName"), data.get("customer_name"))
        ),
        weight=_parse_optional_float(data.get("weight")),
        transfer_call_to=_clean_str(data.get("transfer_call_to")),
        transfer_country_code=_clean_str(data.get("transfer_country_code")),
    )

    return normalized.model_dump()


def _is_salesforce_load(record: dict) -> bool:
    """Detect a Salesforce rtms__Load__c record by its SF envelope or tell-tale keys."""
    attrs = record.get("attributes")
    if isinstance(attrs, dict) and attrs.get("type") == "rtms__Load__c":
        return True
    return "rtms__Load_Status__c" in record or "rtms__Origin__c" in record


def _is_kch_load_record(record: dict) -> bool:
    """Detect a KCH `public.loads` row by its primary-key column."""
    return "load_number" in record


def _get_ordered_stops(record: dict) -> list[dict]:
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


def _pick_stop(stops: list[dict], action_key: str, *, reverse: bool = False) -> dict | None:
    ordered = list(reversed(stops)) if reverse else stops
    for stop in ordered:
        if stop.get(action_key) is True:
            return stop
    return ordered[0] if ordered else None


def _location_from_stop(stop: dict | None) -> LoadLocation:
    if not stop:
        return LoadLocation()
    return LoadLocation(
        city=_clean_str(stop.get("stop_city")) or _clean_str(stop.get("city")) or "",
        state=_clean_str(stop.get("state_code")) or "",
        country=_clean_str(stop.get("country_code")),
        timezone=_clean_str(stop.get("location_timezone")),
    )


def _format_stop_window(stop: dict | None) -> str | None:
    if not stop:
        return None

    expected_date = _clean_str(stop.get("expected_date"))
    appointment = _clean_str(stop.get("appointment_time"))
    hours = _clean_str(stop.get("shipping_receiving_hours"))
    time_window = _first_value(appointment, hours)

    if expected_date and time_window:
        return f"{expected_date} {time_window}"
    return _clean_str(_first_value(time_window, expected_date))


def _join_instructions(*values: object) -> str | None:
    seen: set[str] = set()
    parts: list[str] = []
    for value in values:
        cleaned = _clean_str(value)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        parts.append(cleaned)
    return _normalize_caps_text("\n".join(parts)) if parts else None


def _normalize_kch_load_record(record: dict) -> dict:
    """Normalize a KCH `public.loads` row into the canonical NormalizedLoad shape.

    Linked `public.stops` rows are expected under `record["stops"]` when the
    caller selects them via PostgREST/Supabase embedding.
    """
    load_number = _clean_str(record.get("load_number")) or ""
    stops = _get_ordered_stops(record)
    pickup_stop = _pick_stop(stops, "is_pickup")
    dropoff_stop = _pick_stop(stops, "is_dropoff", reverse=True)
    instructions = _join_instructions(
        record.get("special_requirements"),
        record.get("load_posting_description"),
    )

    normalized = NormalizedLoad(
        id=load_number,
        load_id=load_number,
        origin=_location_from_stop(pickup_stop),
        destination=_location_from_stop(dropoff_stop),
        pickupTime=_format_stop_window(pickup_stop),
        dropoffTime=_format_stop_window(dropoff_stop),
        equipment=_clean_str(
            _first_value(record.get("equipment_type_name"), record.get("mode_name"))
        ),
        commodity=_normalize_caps_text(
            _clean_str(
                _first_value(
                    record.get("cargo_summary"),
                    record.get("commodity_description_posting"),
                )
            )
        ),
        isHazmat=(
            _parse_bool(record.get("hazardous_materials"))
            if record.get("hazardous_materials") is not None
            else None
        ),
        specialInstructions=instructions,
        trackerRequired="tracker required" in instructions.casefold() if instructions else False,
        startRate=_parse_rate(record.get("offer_rate")),
        bookNowRate=_parse_rate(record.get("offer_rate")),
        maxRate=_parse_rate(record.get("max_pay_amount")),
        bookedRate=_parse_optional_float(record.get("carrier_only_quote_total")),
        customerName=_clean_str(record.get("customer_name")),
        weight=_parse_optional_float(record.get("total_weight")),
        transfer_call_to=_clean_str(record.get("carrier_sales_rep_phone")),
    )

    return normalized.model_dump()


def _normalize_salesforce_load(record: dict) -> dict:
    """Normalize an rtms__Load__c record into the canonical NormalizedLoad shape."""
    sf_id = _clean_str(record.get("Id")) or ""
    name = _clean_str(record.get("Name")) or ""

    pickup = _first_value(
        record.get("Pickup_Date_Time__c"), record.get("rtms__Expected_Ship_Date2__c")
    )
    dropoff = _first_value(
        record.get("Delivery_Date_Time__c"),
        record.get("rtms__Expected_Delivery_Date2__c"),
    )

    normalized = NormalizedLoad(
        id=name or sf_id,
        load_id=name or sf_id,
        origin=_location_from_string(record.get("rtms__Origin__c")),
        destination=_location_from_string(record.get("rtms__Destination__c")),
        pickupTime=_clean_str(pickup),
        dropoffTime=_clean_str(dropoff),
        equipment=_clean_str(record.get("KCH_Equipment_Type_Name__c")),
        commodity=_normalize_caps_text(_clean_str(record.get("rtms__Cargo_Summary__c"))),
        isHazmat=record.get("rtms__Hazardous_Materials__c"),
        specialInstructions=_normalize_caps_text(
            _clean_str(record.get("Carrier_Ratecon_Comments__c"))
        ),
        trackerRequired=_parse_bool(record.get("After_Hour_Tracking_Required__c")),
        startRate=_parse_rate(record.get("rtms__Offer_Rate__c")),
        bookNowRate=_parse_rate(record.get("Greenscreens_Target_Buy_Rate__c")),
        maxRate=_parse_rate(record.get("rtms__Max_Pay_Amount__c")),
        bookedRate=_parse_optional_float(record.get("rtms__Carrier_Quote_Total__c")),
        customerName=_clean_str(record.get("First_Stop_Location_Name__c")),
        weight=_parse_optional_float(record.get("rtms__Total_Weight__c")),
        transfer_call_to=_clean_str(record.get("Dispatch_Phone__c")),
    )

    return normalized.model_dump()


def normalize_load_record(raw_load: dict | None) -> dict:
    """Normalize a load record from Salesforce, KCH `loads`, or the legacy Supabase table."""
    record = raw_load or {}
    if _is_salesforce_load(record):
        return _normalize_salesforce_load(record)
    if _is_kch_load_record(record):
        return _normalize_kch_load_record(record)

    reference_id = _clean_str(record.get("load_id")) or ""

    normalized = NormalizedLoad(
        id=reference_id,
        load_id=reference_id,
        origin=_build_location(record, "origin"),
        destination=_build_location(record, "destination"),
        pickupTime=_clean_str(record.get("pickup_time")),
        dropoffTime=_clean_str(record.get("dropoff_time")),
        equipment=_clean_str(record.get("equipment")),
        commodity=_normalize_caps_text(_clean_str(record.get("commodity"))),
        specialInstructions=_normalize_caps_text(_clean_str(record.get("special_instructions"))),
        trackerRequired=_parse_bool(record.get("tracker_required")),
        startRate=_parse_rate(record.get("start_rate")),
        bookNowRate=_parse_rate(record.get("book_now_rate")),
        maxRate=_parse_rate(record.get("max_rate")),
        bookedRate=_parse_optional_float(record.get("booked_rate")),
        customerName=_clean_str(record.get("customer_name")),
        weight=_parse_optional_float(record.get("weight")),
        transfer_call_to=_clean_str(record.get("transfer_call_to")),
        transfer_country_code=_clean_str(record.get("transfer_country_code")),
    )

    return normalized.model_dump()
