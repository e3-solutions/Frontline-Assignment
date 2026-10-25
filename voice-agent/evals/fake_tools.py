"""In-memory equivalents of the four Room-1 call-helper responses.

The boundary is mocked: no carrier API, Supabase, notification, or call
termination service is invoked.  Response payloads intentionally match the
success/error shapes in call_helpers.py.
"""
from __future__ import annotations

from copy import deepcopy
from evals.fixtures import CARRIER_DIRECTORY, NORMAL_LOAD


class FakeTools:
    def __init__(self, loads=None, directory=None):
        self.loads = loads or {NORMAL_LOAD["id"]: NORMAL_LOAD}
        self.directory = directory or CARRIER_DIRECTORY
        self.calls = []
        self.transfer_happened = False
        self.call_id = "offline-call-001"

    def dispatch(self, name, arguments):
        self.calls.append({"name": name, "arguments": deepcopy(arguments)})
        return getattr(self, name)(**arguments)

    def verify_carrier(self, mc_number=""):
        if mc_number == "error":
            return {"status": "error", "message": "Carrier service unavailable"}
        carrier_name = self.directory.get(str(mc_number))
        if not carrier_name:
            return {"status": "not_found", "message": f"No carrier found with MC number {mc_number}"}
        return {"status": "success", "message": f"Carrier found: {carrier_name}",
                "carrier_name": carrier_name, "mc_number": str(mc_number)}

    def get_load_context(self, load_id=""):
        load = self.loads.get(str(load_id))
        if not load:
            return {"status": "error", "message": f"No load found with ID: {load_id}"}
        return {"status": "success", "message": f"Load {load_id} information retrieved successfully",
                "load_data": deepcopy(load), "call_id": self.call_id}

    def record_agreement(self, agreed_price=None, above_max=False,
                         carrier_contact_name=None, carrier_contact_phone=None):
        if not agreed_price:
            return {"status": "error", "message": "Missing agreed_price or load not loaded"}
        if above_max and (not carrier_contact_name or not carrier_contact_phone):
            return {"status": "error", "message": "above_max requires contact name and phone"}
        try:
            price = float(agreed_price)
        except (TypeError, ValueError):
            return {"status": "error", "message": "Invalid price format"}
        message = (f"Above-max bid stored. We'll contact {carrier_contact_name} if conditions change."
                   if above_max else f"Agreement recorded at ${price}")
        return {"status": "success", "message": message, "negotiation_id": "offline-negotiation-001"}

    def end_call(self, reason=None):
        if self.transfer_happened:
            return {"status": "ignored", "message": "Call already transferred to human. end_call ignored."}
        valid = {"abrupt", "agreement", "no_agreement", "bid_placed", "error", "load_not_found", "mc_not_found"}
        if reason not in valid:
            return {"status": "error", "message": "Invalid reason. Must be one of: " + ", ".join(sorted(valid))}
        return {"status": "success", "message": f"Call ending with reason: {reason}"}
