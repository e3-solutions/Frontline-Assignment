"""Canonical scenario specifications used by offline and optional live runs."""

SCENARIOS = {
    "valid_carrier_and_load": {
        "caller": ["My MC is one two three four five six.", "Yes, that's us.", "Reference LOAD-1234."],
        "mock_tools": {"verify_carrier": {"status": "success", "carrier_name": "Acme Transport LLC", "mc_number": "123456"}, "get_load_context": {"status": "success"}},
        "required": ["verify_carrier", "get_load_context"],
        "forbidden": ["record_agreement", "transfer_to_human"],
    },
    "three_mc_not_found": {
        "caller": ["Try 111111.", "Try 222222.", "Try 333333."],
        "mock_tools": {"verify_carrier": {"status": "not_found"}},
        "required": ["three verify_carrier calls", "end_call:mc_not_found"],
        "forbidden": ["count identity denial or service error as a strike", "get_load_context"],
    },
    "wrong_identity_rejected": {
        "caller": ["My MC is 123456.", "No, that is not us."],
        "mock_tools": {"verify_carrier": {"status": "success", "carrier_name": "Wrong Carrier LLC"}},
        "required": ["clear staged identity", "request corrected MC"],
        "forbidden": ["get_load_context", "record_agreement", "transfer_to_human"],
    },
    "below_goal": {
        "caller": ["I can do fifteen hundred.", "Fifteen hundred is firm."],
        "context": {"start_rate": 1400, "goal_rate": 1600, "ceiling_rate": 1800},
        "required": ["counter below 1500 or accept firm 1500"],
        "forbidden": ["counter at or above 1500", "reveal goal or ceiling"],
    },
    "above_ceiling_spontaneous_acceptance": {
        "caller": ["I can do it for twenty-two hundred."],
        "context": {"start_rate": 1400, "goal_rate": 1600, "ceiling_rate": 1800},
        "required": ["reject ordinary agreement", "continue negotiating or capture above-max bid"],
        "forbidden": ["agreement language", "above_max:false", "KCH quote", "end_call:agreement"],
    },
    "above_ceiling_no_agreement": {
        "caller": ["I need twenty-two hundred.", "No, twenty-two is firm.", "Sam Jones, 555-0100."],
        "context": {"start_rate": 1400, "goal_rate": 1600, "ceiling_rate": 1800},
        "required": ["above_max:true", "end_call:no_agreement"],
        "forbidden": ["KCH quote", "agreement language", "end_call:agreement", "end_call:bid_placed"],
    },
}
