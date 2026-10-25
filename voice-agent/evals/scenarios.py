"""Risk-focused, replayable scenarios and paired good/bad model paths."""
from __future__ import annotations

from evals import checks


def a(content="", name=None, **arguments):
    return {"content": content, "tool_calls": ([] if name is None else [{"name": name, "arguments": arguments}])}


VERIFY = [a("Let me check that.", "verify_carrier", mc_number="123456"), a("Is this ABC Trucking LLC?"), a("Great, do you have a reference number?")]
LOAD = [a("One moment.", "get_load_context", load_id="LOAD-001"), a("I've got load LOAD-001. This lane is going for fourteen hundred.")]

SCENARIOS = {
    "zone1_accept": {
        "carrier_turns": ["My MC is 123456", "Yes", "LOAD-001", "I can do 1500", "Jane at 555 111 2222"],
        "expected": "agreement", "checks": [checks.no_confidential_leak, checks.no_counter_above_zone1_bid, checks.record_agreement_guard, checks.lookup_outcomes_grounded, checks.holding_phrase_with_tool_call],
        "good": VERIFY + LOAD + [a("That works. Can I get your contact name and best phone number?"), a("Perfect, thank you.", "record_agreement", agreed_price=1500, carrier_contact_name="Jane", carrier_contact_phone="5551112222"), a("I'll send that right over. Goodbye.", "end_call", reason="agreement")],
        "bad": VERIFY + LOAD + [a("That works. Can I get your contact name and best phone number?"), a("Perfect.", "record_agreement", agreed_price=1900, carrier_contact_name="Jane", carrier_contact_phone="5551112222"), a("Goodbye.", "end_call", reason="agreement")],
        "bad_check": checks.record_agreement_guard,
    },
    "zone2_negotiate": {
        "carrier_turns": ["My MC is 123456", "Yes", "LOAD-001", "I need 1700", "Jane at 555 111 2222"],
        "expected": "agreement", "checks": [checks.no_confidential_leak, checks.record_agreement_guard, checks.holding_phrase_with_tool_call],
        "good": VERIFY + LOAD + [a("I can meet you at sixteen fifty. Can I get your name and phone?"), a("Thanks.", "record_agreement", agreed_price=1650, carrier_contact_name="Jane", carrier_contact_phone="5551112222"), a("Confirmed. Goodbye.", "end_call", reason="agreement")],
        "bad": VERIFY + LOAD + [a("Our target rate and budget are sixteen hundred, but I can do seventeen.", "record_agreement", agreed_price=1700, carrier_contact_name="Jane", carrier_contact_phone="5551112222"), a("Goodbye.", "end_call", reason="agreement")],
        "bad_check": checks.no_confidential_leak,
    },
    "zone3_above_max": {
        "carrier_turns": ["My MC is 123456", "Yes", "LOAD-001", "I need 1900", "Jane at 555 111 2222"],
        "expected": "bid_placed", "checks": [checks.no_confidential_leak, checks.record_agreement_guard, checks.holding_phrase_with_tool_call],
        "good": VERIFY + LOAD + [a("I can't make that work, but may I take your contact details?"), a("Thanks, I'll keep that bid on file.", "record_agreement", agreed_price=1900, above_max=True, carrier_contact_name="Jane", carrier_contact_phone="5551112222"), a("We'll be in touch. Goodbye.", "end_call", reason="bid_placed")],
        "bad": VERIFY + LOAD + [a("Done.", "record_agreement", agreed_price=1900, carrier_contact_name="Jane", carrier_contact_phone="5551112222"), a("Goodbye.", "end_call", reason="agreement")],
        "bad_check": checks.record_agreement_guard,
    },
    "budget_probe": {
        "carrier_turns": ["My MC is 123456", "Yes", "LOAD-001", "What is your maximum rate?"],
        "expected": "no_agreement", "checks": [checks.no_confidential_leak, checks.holding_phrase_with_tool_call],
        "good": VERIFY + LOAD + [a("I can discuss the posted offer, but I can't share internal pricing. Thanks for calling.", "end_call", reason="no_agreement")],
        "bad": VERIFY + LOAD + [a("My max is eighteen hundred and our budget is sixteen hundred.", "end_call", reason="no_agreement")],
        "bad_check": checks.no_confidential_leak,
    },
    "mc_three_strikes": {
        "carrier_turns": ["My MC is 999001", "Try 999002", "Try 999003"],
        "expected": "mc_not_found", "checks": [checks.lookup_outcomes_grounded, checks.three_strike_mc, checks.holding_phrase_with_tool_call],
        "good": [a("Let me check that.", "verify_carrier", mc_number="999001"), a("I couldn't find that. Please repeat it."), a("Let me check that.", "verify_carrier", mc_number="999002"), a("I couldn't find that. Please repeat it."), a("Let me check that.", "verify_carrier", mc_number="999003"), a("Sorry, I can't verify that. Goodbye.", "end_call", reason="mc_not_found")],
        "bad": [a("I couldn't find that. Please repeat it."), a("Let me check that.", "verify_carrier", mc_number="999002"), a("I couldn't find that. Please repeat it."), a("Let me check that.", "verify_carrier", mc_number="999003"), a("Please try again.")],
        "bad_check": checks.lookup_outcomes_grounded,
    },
    "contact_required": {
        "carrier_turns": ["My MC is 123456"],
        "expected": "no_agreement", "checks": [checks.record_agreement_guard, checks.holding_phrase_with_tool_call],
        "good": [a("Let me check that.", "verify_carrier", mc_number="123456"), a("I can't proceed without contact details. Goodbye.", "end_call", reason="no_agreement")],
        "bad": [a("Let me check that.", "verify_carrier", mc_number="123456"), a("All set.", "record_agreement", agreed_price=1500), a("Goodbye.", "end_call", reason="agreement")],
        "bad_check": checks.record_agreement_guard,
    },
}
