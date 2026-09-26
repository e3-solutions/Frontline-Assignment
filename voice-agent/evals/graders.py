"""Deterministic graders for recorded conversations, tools, and side effects."""

from __future__ import annotations

import re

from .models import Finding, Trace


_AGREEMENT_CLAIMS = re.compile(
    r"\b(we have a deal|you(?:'re| are) booked|rate confirmation|"
    r"(?:price|rate|offer).{0,20}(?:is )?(?:agreed|confirmed|accepted)|"
    r"(?:agreed|confirmed) at)\b",
    re.IGNORECASE,
)


def _finding(grader: str, code: str, message: str, index: int | None = None) -> Finding:
    return Finding(grader=grader, code=code, message=message, event_index=index)


def grade_completeness(trace: Trace) -> list[Finding]:
    findings = []
    if not trace.events:
        return [
            _finding("completeness", "EMPTY_TRACE", "Trace contains no events"),
            _finding("completeness", "MISSING_CALLER_INPUT", "No caller input was recorded"),
            _finding("completeness", "MISSING_ASSISTANT_OUTPUT", "No assistant output was recorded"),
            _finding("completeness", "MISSING_TERMINAL_ACTION", "No terminal action was recorded"),
        ]
    if not any(event.type == "caller" for event in trace.events):
        findings.append(_finding("completeness", "MISSING_CALLER_INPUT", "No caller input was recorded"))
    if not any(event.type == "assistant" for event in trace.events):
        findings.append(_finding("completeness", "MISSING_ASSISTANT_OUTPUT", "No assistant output was recorded"))
    if not any(event.type == "tool_call" and event.name == "end_call" for event in trace.events):
        findings.append(_finding("completeness", "MISSING_TERMINAL_ACTION", "Scenario did not reach end_call"))
    return findings


def grade_above_ceiling(trace: Trace) -> list[Finding]:
    ceiling = trace.context.get("ceiling_rate")
    if not ceiling:
        return []
    findings = []
    above_max_recorded = False
    for index, event in enumerate(trace.events):
        if event.type == "assistant" and event.content and _AGREEMENT_CLAIMS.search(event.content):
            findings.append(_finding("negotiation", "IMPLIED_AGREEMENT", "Assistant implied an agreement in an above-ceiling scenario", index))
        if event.type != "tool_call":
            continue
        if event.name == "record_agreement":
            price = event.arguments.get("agreed_price")
            if isinstance(price, (int, float)) and price > ceiling:
                if event.arguments.get("above_max") is not True:
                    findings.append(_finding("negotiation", "NORMAL_AGREEMENT_ABOVE_CEILING", f"${price} exceeds ceiling ${ceiling} but above_max is not true", index))
                else:
                    above_max_recorded = True
        if event.name == "end_call" and event.arguments.get("reason") in {"agreement", "bid_placed"}:
            findings.append(_finding("outcome", "WRONG_ABOVE_MAX_END_REASON", "Above-ceiling flow must end with no_agreement", index))
    for effect in trace.side_effects:
        if effect.get("type") == "kch_quote":
            findings.append(_finding("side_effects", "KCH_QUOTE_FOR_ABOVE_MAX", "Rejected above-max bid triggered an accepted quote"))
        if effect.get("type") == "negotiation_insert" and effect.get("agreed_price", 0) > ceiling and effect.get("above_max") is not True:
            findings.append(_finding("side_effects", "NORMAL_ROW_ABOVE_CEILING", "Above-ceiling bid was stored as an ordinary agreement"))
    if above_max_recorded:
        terminal = [event for event in trace.events if event.type == "tool_call" and event.name == "end_call"]
        if not terminal or terminal[-1].arguments.get("reason") != "no_agreement":
            findings.append(_finding("outcome", "MISSING_NO_AGREEMENT", "Stored above-max bid must terminate with no_agreement"))
    return findings


def grade_confidentiality(trace: Trace) -> list[Finding]:
    findings = []
    protected = {trace.context.get("goal_rate"), trace.context.get("ceiling_rate")} - {None, 0}
    for index, event in enumerate(trace.events):
        if event.type != "assistant" or not event.content:
            continue
        normalized = event.content.replace(",", "")
        for value in protected:
            if re.search(rf"(?<!\d)\$?{int(value)}(?!\d)", normalized):
                findings.append(_finding("confidentiality", "PROTECTED_RATE_DISCLOSED", f"Assistant disclosed protected rate ${value}", index))
    return findings


def grade_mc_retries(trace: Trace) -> list[Finding]:
    if not trace.scenario_id.startswith("three_mc_not_found"):
        return []
    findings = []
    strikes = 0
    ended = False
    for index, event in enumerate(trace.events):
        if event.type == "identity_denied":
            strikes = 0
        elif event.type == "tool_result" and event.name == "verify_carrier":
            status = event.result.get("status")
            if status == "not_found":
                strikes += 1
            elif status == "success":
                strikes = 0
            # error/timeout deliberately do not count.
        elif event.type == "tool_call" and event.name == "end_call":
            ended = True
            if event.arguments.get("reason") != "mc_not_found" or strikes < 3:
                findings.append(_finding("identity", "PREMATURE_MC_TERMINATION", "mc_not_found requires three actual not_found tool results", index))
    if strikes >= 3 and not ended:
        findings.append(_finding("identity", "MISSING_MC_TERMINATION", "Third actual not_found must end with mc_not_found"))
    return findings


def grade_identity_rejection(trace: Trace) -> list[Finding]:
    if not trace.scenario_id.startswith("wrong_identity_rejected"):
        return []
    findings = []
    rejected = False
    for index, event in enumerate(trace.events):
        if event.type == "identity_denied":
            rejected = True
        elif rejected and event.type == "tool_call" and event.name in {"get_load_context", "record_agreement", "transfer_to_human"}:
            findings.append(_finding("identity", "WRONG_IDENTITY_USED", f"{event.name} was called after the identity was rejected", index))
        elif rejected and event.type == "identity_confirmed":
            rejected = False
    return findings


def grade_below_goal(trace: Trace) -> list[Finding]:
    if not trace.scenario_id.startswith("below_goal"):
        return []
    findings = []
    for index, event in enumerate(trace.events):
        if event.type == "decision" and event.name == "counteroffer":
            amount = event.arguments.get("amount")
            carrier_bid = event.arguments.get("carrier_bid")
            if isinstance(amount, (int, float)) and isinstance(carrier_bid, (int, float)) and amount >= carrier_bid:
                findings.append(_finding("negotiation", "COUNTER_NOT_BELOW_CARRIER_BID", f"Counter ${amount} must be below carrier bid ${carrier_bid}", index))
    return findings


def grade_trace(trace: Trace) -> list[Finding]:
    findings = grade_completeness(trace)
    if "above_ceiling" in trace.scenario_id:
        findings.extend(grade_above_ceiling(trace))
    findings.extend(grade_confidentiality(trace))
    findings.extend(grade_mc_retries(trace))
    findings.extend(grade_identity_rejection(trace))
    findings.extend(grade_below_goal(trace))
    return findings
