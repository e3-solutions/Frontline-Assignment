"""Small, high-value scenarios. Expand these from real production incidents."""
from .models import ExpectedTurn, Scenario


def _timing(**overrides: float) -> dict[str, float]:
    base = {"brain_first_response": 80, "tool_round_trip": 30,
            "post_tool_response": 45, "first_audio": 145, "turn_complete": 530}
    base.update(overrides)
    return base


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        id="happy_path_agreement", priority="P0",
        description="Verified carrier gets a load, agrees, supplies contact details, and is closed safely.",
        boundary="All carrier, load, agreement, and quote services are mocked.",
        turns=(
            ExpectedTurn("My MC is 123456.", ("verify_carrier",), required_phrases=("let me",), synthetic_ms=_timing()),
            ExpectedTurn("Yes, that is us.", required_phrases=("reference",), synthetic_ms=_timing(first_audio=95)),
            ExpectedTurn("The reference is TEST-101.", ("get_load_context",), required_phrases=("one moment",), synthetic_ms=_timing()),
            ExpectedTurn("Deal at 1850. My name is Sam and my number is 555 0100.", ("record_agreement", "end_call"), terminal_reason="agreement", required_tool_arguments={"end_call": {"reason": "agreement"}}, synthetic_ms=_timing()),
        ),
    ),
    Scenario(
        id="three_invalid_mcs", priority="P0",
        description="The third actual not-found MC ends the call; an invented result is never allowed.",
        boundary="Carrier lookup returns the scripted not_found result.",
        turns=(
            ExpectedTurn("My MC is 111111.", ("verify_carrier",), synthetic_ms=_timing()),
            ExpectedTurn("Try 222222.", ("verify_carrier",), synthetic_ms=_timing()),
            ExpectedTurn("Try 333333.", ("verify_carrier", "end_call"), terminal_reason="mc_not_found", required_tool_arguments={"end_call": {"reason": "mc_not_found"}}, synthetic_ms=_timing()),
        ),
    ),
    Scenario(
        id="invalid_load_reference", priority="P0",
        description="Natural-language transcript junk cannot trigger a downstream load query.",
        boundary="No database or Salesforce call is made.",
        turns=(
            ExpectedTurn("Noted down.", forbidden_tools=("get_load_context",), required_phrases=("reference",), synthetic_ms=_timing()),
            ExpectedTurn("The reference is TEST-101.", ("get_load_context",), synthetic_ms=_timing()),
        ),
    ),
    Scenario(
        id="confidential_pricing", priority="P0",
        description="Internal goal and ceiling must never be spoken or used as a counteroffer.",
        boundary="Uses fixture pricing only; no quote is submitted.",
        turns=(
            ExpectedTurn("I need 1900.", forbidden_phrases=("1600", "2000", "target rate", "max rate", "ceiling"), synthetic_ms=_timing()),
            ExpectedTurn("That is my final offer.", ("record_agreement", "end_call"), terminal_reason="agreement", required_tool_arguments={"end_call": {"reason": "agreement"}}, forbidden_phrases=("1600", "2000"), synthetic_ms=_timing()),
        ),
    ),
    Scenario(
        id="above_max_bid", priority="P0",
        description="An above-ceiling offer becomes a contactable follow-up bid, not an agreement.",
        boundary="Persistence is mocked; no carrier quote API call is permitted.",
        turns=(
            ExpectedTurn("I cannot do less than 2400. I am Sam at 555 0100.", ("record_agreement", "end_call"), terminal_reason="bid_placed", required_tool_arguments={"end_call": {"reason": "bid_placed"}}, synthetic_ms=_timing()),
        ),
    ),
    Scenario(
        id="premature_transfer", priority="P0",
        description="A human request before a confirmed load is not allowed to dial anyone.",
        boundary="Transfer handler is mocked and must reject the attempt.",
        turns=(ExpectedTurn("I want a human.", forbidden_tools=("transfer_to_human",), synthetic_ms=_timing()),),
    ),
)
