"""Dependency-free safety rules shared by production handlers and evaluations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GuardrailViolation:
    code: str
    message: str


def identity_is_blocked(context: Any) -> bool:
    return bool(
        getattr(context, "awaiting_carrier_identity_confirmation", False)
        or getattr(context, "carrier_identity_rejected", False)
    )


def validate_price_outcome(
    price: float, *, above_max: bool, raw_max_rate: Any
) -> GuardrailViolation | None:
    if price <= 0:
        return GuardrailViolation("INVALID_PRICE", "Price must be positive")
    try:
        max_rate = float(raw_max_rate) if raw_max_rate not in (None, "") else None
    except (TypeError, ValueError):
        return GuardrailViolation(
            "INVALID_LOAD_PRICING",
            "Load ceiling is invalid; the outcome cannot be recorded safely",
        )

    # A zero ceiling is the documented no-rate mode.
    has_ceiling = max_rate is not None and max_rate > 0
    if has_ceiling and price > max_rate and not above_max:
        return GuardrailViolation(
            "PRICE_ABOVE_CEILING",
            "This price cannot be recorded as an agreement. Continue negotiating "
            "or record it as an above-max bid and end with no_agreement.",
        )
    if above_max and has_ceiling and price <= max_rate:
        return GuardrailViolation(
            "PRICE_NOT_ABOVE_CEILING",
            "A bid at or below the ceiling must not be stored as above-max",
        )
    return None


def validate_agreement_end(*, agreement_recorded: bool) -> GuardrailViolation | None:
    if not agreement_recorded:
        return GuardrailViolation(
            "AGREEMENT_NOT_RECORDED",
            "Cannot end as agreement before an agreement is successfully recorded",
        )
    return None
