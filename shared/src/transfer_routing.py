"""Helpers for load-scoped transfer routing phone numbers."""

from __future__ import annotations

import re

_E164_RE = re.compile(r"^\+\d{8,15}$")


def sanitize_phone_digits(value: object | None) -> str:
    """Return only the digits from a phone-like value."""
    if value is None:
        return ""
    return "".join(char for char in str(value) if char.isdigit())


def build_transfer_phone_number(
    transfer_country_code: object | None, transfer_call_to: object | None
) -> str | None:
    """Build a dialable transfer number from stored country code and local digits."""
    country_code = str(transfer_country_code or "").strip()
    digits_only = sanitize_phone_digits(transfer_call_to)

    if not country_code or not digits_only:
        return None

    return f"{country_code}{digits_only}"


def coerce_e164_transfer_number(value: object | None) -> str | None:
    """Normalize a full E.164 phone string (e.g., from `carrier_sales_rep_phone`).

    Strips whitespace, ensures a `+` prefix, and validates the result is a
    plausible E.164 number (8-15 digits after the plus). Returns the canonical
    string or None if the input is empty or malformed.
    """
    if value is None:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    if not cleaned.startswith("+"):
        cleaned = f"+{cleaned}"
    if not _E164_RE.match(cleaned):
        return None
    return cleaned
