"""Utilities for load context management."""

from src import CarrierLookupResult, normalize_load_record
from voice_prompt import (
    build_full_negotiation_prompt,
    get_initial_greeting_prompt,
    get_known_carrier_greeting_prompt,
)


def normalize_load_data(raw_load: dict) -> dict:
    """Extract load data from database record."""
    return normalize_load_record(raw_load)


def build_negotiation_prompt(load_context: dict) -> str:
    """Build the negotiation system prompt with load context."""
    return build_full_negotiation_prompt(load_context)


def get_initial_system_prompt(
    org_name: str | None = None,
    phone_verification: CarrierLookupResult | None = None,
    *,
    phone_first_enabled: bool = False,
) -> str:
    """Initial system prompt.

    If `phone_verification` indicates a known carrier (only possible when
    `phone_first_enabled=True`), returns the name-first greeting. Otherwise
    returns the standard MC-first greeting. The `phone_first_enabled` flag
    is also threaded into the MC-first greeting so that, when off, the
    prompt keeps backend-owned carrier confirmation pacing while preserving
    exact pre-PR behavior on the unknown-carrier path when the flag is off.
    """
    if (
        phone_first_enabled
        and phone_verification is not None
        and phone_verification.status == "known_carrier"
        and phone_verification.carrier_name
    ):
        return get_known_carrier_greeting_prompt(
            phone_verification.carrier_name, org_name
        )
    return get_initial_greeting_prompt(
        org_name, phone_first_enabled=phone_first_enabled
    )
