"""Stable load and carrier fixtures; no services or credentials are used."""
from __future__ import annotations

import sys
import types
from pathlib import Path

# shared/src/__init__.py eagerly imports HTTP clients not needed for prompt
# rendering.  Supply a namespace package only in this offline evaluation so
# voice_prompt can import its pure src.negotiation_prompt module.
if "src" not in sys.modules:
    src = types.ModuleType("src")
    src.__path__ = [str(Path(__file__).resolve().parents[2] / "shared" / "src")]
    sys.modules["src"] = src

from voice_prompt import build_full_negotiation_prompt, get_initial_greeting_prompt

NORMAL_LOAD = {
    "id": "LOAD-001", "load_id": "LOAD-001",
    "origin": {"city": "Dallas", "state": "TX"},
    "destination": {"city": "Houston", "state": "TX"},
    "pickupTime": "Monday 8 AM", "dropoffTime": "Tuesday 5 PM",
    "equipment": "Dry van", "commodity": "Freight", "isHazmat": False,
    "specialInstructions": "Driver must call ahead", "trackerRequired": False,
    "startRate": 1400, "bookNowRate": 1600, "maxRate": 1800,
    "bookedRate": None, "customerName": "Fixture Customer", "weight": 42000,
    "transfer_call_to": None, "transfer_country_code": None,
}
NO_RATE_LOAD = {**NORMAL_LOAD, "id": "LOAD-NORATE", "load_id": "LOAD-NORATE",
                "startRate": 0, "bookNowRate": 0, "maxRate": 0}
CARRIER_DIRECTORY = {"123456": "ABC Trucking LLC"}


def build_system_prompt(load: dict | None = None) -> str:
    return build_full_negotiation_prompt(load) if load else get_initial_greeting_prompt("KCH")
