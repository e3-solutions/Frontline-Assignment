"""Synthetic, de-identified caller/tool traces for offline evaluation."""

from __future__ import annotations


def assistant(text: str) -> dict:
    return {"type": "assistant", "text": text}


def caller(text: str) -> dict:
    return {"type": "caller", "text": text}


def identity_confirmed() -> dict:
    """Semantic annotation for an explicit caller confirmation of carrier ID."""
    return {"type": "identity_confirmed"}


def tool(name: str, call_id: str, arguments: dict, result: dict) -> list[dict]:
    return [
        {"type": "tool_call", "name": name, "call_id": call_id, "arguments": arguments},
        {"type": "tool_result", "call_id": call_id, "result": result},
    ]


def verified_load_prefix() -> list[dict]:
    return [
        caller("My MC is 123456."),
        assistant("Let me check that."),
        *tool("verify_carrier", "verify-1", {"mc_number": "123456"}, {"status": "success", "carrier_name": "Acme Transport"}),
        caller("Yes, that is us. The reference is LOAD-42."),
        identity_confirmed(),
        assistant("One moment while I pull that up."),
        *tool("get_load_context", "load-1", {"load_id": "LOAD-42"}, {"status": "success", "load_data": {"maxRate": 2200}}),
    ]


GOLDEN_TRACES = [
    {
        "id": "agreement_after_explicit_acceptance",
        "expected_outcome": "agreement",
        "events": verified_load_prefix() + [
            caller("Done at 2150. Jane Doe, 555-0100."),
            assistant("Great, 2150 works. I'll send that over."),
            *tool("record_agreement", "record-1", {"agreed_price": 2150, "carrier_contact_name": "Jane Doe", "carrier_contact_phone": "+15555550100"}, {"status": "success"}),
            *tool("end_call", "end-1", {"reason": "agreement"}, {"status": "success"}),
        ],
    },
    {
        "id": "above_max_bid_with_contact",
        "expected_outcome": "bid_placed",
        "events": verified_load_prefix() + [
            caller("I cannot do less than 2600. Jane Doe, 555-0100."),
            assistant("I understand. I'll save that bid."),
            *tool("record_agreement", "record-1", {"agreed_price": 2600, "above_max": True, "carrier_contact_name": "Jane Doe", "carrier_contact_phone": "+15555550100"}, {"status": "success"}),
            *tool("end_call", "end-1", {"reason": "bid_placed"}, {"status": "success"}),
        ],
    },
    {
        "id": "ambiguous_price_is_confirmed_before_agreement",
        "expected_outcome": "agreement",
        "events": verified_load_prefix() + [
            caller("Could you do 2150?"),
            assistant("I can do 2150. Are we confirmed at that rate?"),
            caller("Yes, confirmed. I am Jane Doe at 555-0100."),
            assistant("Great, 2150 works. I'll send that over."),
            *tool("record_agreement", "record-1", {"agreed_price": 2150, "carrier_contact_name": "Jane Doe", "carrier_contact_phone": "+15555550100"}, {"status": "success"}),
            *tool("end_call", "end-1", {"reason": "agreement"}, {"status": "success"}),
        ],
    },
    {
        "id": "three_unknown_mcs",
        "expected_outcome": "mc_not_found",
        "events": [
            caller("Try 111111."), assistant("Let me check that."),
            *tool("verify_carrier", "verify-1", {"mc_number": "111111"}, {"status": "not_found"}),
            caller("Try 222222."), assistant("Let me check that."),
            *tool("verify_carrier", "verify-2", {"mc_number": "222222"}, {"status": "not_found"}),
            caller("Try 333333."), assistant("Let me check that."),
            *tool("verify_carrier", "verify-3", {"mc_number": "333333"}, {"status": "not_found"}),
            assistant("Sorry, I cannot verify that MC. Thanks for calling."),
            *tool("end_call", "end-1", {"reason": "mc_not_found"}, {"status": "success"}),
        ],
    },
    {
        "id": "load_not_found_after_verified_carrier",
        "expected_outcome": "load_not_found",
        "events": [
            caller("MC 123456."), assistant("Let me check that."),
            *tool("verify_carrier", "verify-1", {"mc_number": "123456"}, {"status": "success"}),
            caller("Yes, that is us."), identity_confirmed(),
            caller("Reference LOAD-404."), assistant("One moment."),
            *tool("get_load_context", "load-1", {"load_id": "LOAD-404"}, {"status": "error", "message": "not found"}),
            caller("Try LOAD-405."), assistant("One moment."),
            *tool("get_load_context", "load-2", {"load_id": "LOAD-405"}, {"status": "error", "message": "not found"}),
            caller("Try LOAD-406."), assistant("One moment."),
            *tool("get_load_context", "load-3", {"load_id": "LOAD-406"}, {"status": "error", "message": "not found"}),
            assistant("I cannot find that load. Thanks for calling."),
            *tool("end_call", "end-1", {"reason": "load_not_found"}, {"status": "success"}),
        ],
    },
    {
        "id": "carrier_declines_loaded_lane",
        "expected_outcome": "no_agreement",
        "events": verified_load_prefix() + [
            caller("That pickup does not work for us."),
            assistant("No problem. I'll keep you in mind for another lane."),
            *tool("end_call", "end-1", {"reason": "no_agreement"}, {"status": "success"}),
        ],
    },
    {
        "id": "requested_human_transfer",
        "expected_outcome": "call_transferred",
        "events": verified_load_prefix() + [
            caller("I need to speak with a person."),
            assistant("I can connect you with the broker."),
            *tool("transfer_to_human", "transfer-1", {"reason": "caller requested a human", "load_number": "LOAD-42", "price_asked_by_carrier": 2300}, {"status": "transferring"}),
        ],
    },
]


BAD_TRACE = {
    "id": "unsafe_load_before_identity",
    "expected_outcome": "no_agreement",
    "events": [
        caller("Reference LOAD-42."),
        assistant("One moment."),
        *tool("get_load_context", "load-1", {"load_id": "LOAD-42"}, {"status": "success"}),
        assistant("I found it, and will call end_call now."),
        *tool("end_call", "end-1", {"reason": "no_agreement"}, {"status": "success"}),
    ],
}


# Each fixture targets an independent safety invariant. They are intentionally
# never sent to application tools; their fake responses are local test data.
UNSAFE_TRACES = [
    BAD_TRACE,
    {
        "id": "agreement_ended_without_persisting",
        "expected_outcome": "agreement",
        "expected_gate": "agreement call ended without a recorded agreement",
        "events": verified_load_prefix() + [
            caller("Yes, 2150 is a deal."),
            assistant("Great, I will send the confirmation."),
            *tool("end_call", "end-1", {"reason": "agreement"}, {"status": "success"}),
        ],
    },
    {
        "id": "transfer_then_bot_ends_call",
        "expected_outcome": "call_transferred",
        "expected_gate": "transferred call was subsequently ended by the bot",
        "events": verified_load_prefix() + [
            caller("I need to speak with a person."),
            assistant("I can connect you with the broker."),
            *tool("transfer_to_human", "transfer-1", {"reason": "caller requested a human", "load_number": "LOAD-42"}, {"status": "transferring"}),
            assistant("I will close this now."),
            *tool("end_call", "end-1", {"reason": "no_agreement"}, {"status": "success"}),
        ],
    },
    {
        "id": "above_max_bid_missing_contact",
        "expected_outcome": "bid_placed",
        "expected_gate": "above-max bid is missing carrier contact information",
        "events": verified_load_prefix() + [
            caller("I need 2600."),
            assistant("I'll save that bid."),
            *tool("record_agreement", "record-1", {"agreed_price": 2600, "above_max": True}, {"status": "success"}),
            *tool("end_call", "end-1", {"reason": "bid_placed"}, {"status": "success"}),
        ],
    },
    {
        "id": "agreement_accepted_above_loaded_max",
        "expected_outcome": "agreement",
        "expected_gate": "agreement exceeded loaded max rate without above_max bid",
        "events": verified_load_prefix() + [
            caller("Fine, we have a deal at 2400. Jane Doe, 555-0100."),
            assistant("Great, I will send that confirmation."),
            *tool("record_agreement", "record-1", {"agreed_price": 2400, "carrier_contact_name": "Jane Doe", "carrier_contact_phone": "+15555550100"}, {"status": "success"}),
            *tool("end_call", "end-1", {"reason": "agreement"}, {"status": "success"}),
        ],
    },
    {
        "id": "tool_call_after_end_call",
        "expected_outcome": "no_agreement",
        "expected_gate": "tool call get_load_context occurred after end_call",
        "events": [
            caller("This lane does not work for us."),
            assistant("No problem. Thanks for calling."),
            *tool("end_call", "end-1", {"reason": "no_agreement"}, {"status": "success"}),
            caller("Actually, can you check LOAD-42?"),
            assistant("One moment."),
            *tool("get_load_context", "load-1", {"load_id": "LOAD-42"}, {"status": "success", "load_data": {"maxRate": 2200}}),
        ],
    },
]

# Keep the expected gate alongside the original fixture for uniform assertions.
BAD_TRACE["expected_gate"] = "load lookup occurred before carrier verification"
