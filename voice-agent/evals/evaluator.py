"""Deterministic trace evaluator for the voice-agent's high-risk workflow.

This module intentionally does not import the application or invoke an LLM.
It replays a captured or synthetic event trace against fake tool responses, so
the evaluation is safe to run with no provider credentials or side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


TOOL_NAMES = {
    "verify_carrier",
    "get_load_context",
    "record_agreement",
    "end_call",
    "transfer_to_human",
    "transfer_human_to_carrier",
}
HOLDING_PHRASES = ("let me", "one moment", "one second", "i'll check")
END_REASONS = {
    "abrupt",
    "agreement",
    "no_agreement",
    "bid_placed",
    "error",
    "load_not_found",
    "mc_not_found",
}


@dataclass(frozen=True)
class EvaluationResult:
    """Gate failures and non-blocking quality observations for one trace."""

    scenario_id: str
    gate_failures: tuple[str, ...]
    quality_checks: int
    quality_passes: int
    observations: tuple[str, ...]

    @property
    def passed_gates(self) -> bool:
        return not self.gate_failures

    @property
    def quality_score(self) -> float:
        return self.quality_passes / self.quality_checks if self.quality_checks else 1.0


def _tool_results(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        event["call_id"]: event["result"]
        for event in events
        if event["type"] == "tool_result"
    }


def _prior_assistant_text(events: list[dict[str, Any]], index: int) -> str:
    """Return speech immediately preceding a tool call in the same model turn."""
    if index and events[index - 1]["type"] == "assistant":
        return events[index - 1].get("text", "").lower()
    return ""


def evaluate_trace(trace: dict[str, Any]) -> EvaluationResult:
    """Replay a trace and evaluate safety gates separately from quality.

    Trace event types are ``caller``, ``assistant``, ``identity_confirmed``,
    ``tool_call``, and ``tool_result``. ``identity_confirmed`` is an evaluator
    annotation for an explicit caller confirmation after a successful carrier
    lookup; it prevents a lookup result alone from authorizing load access.
    Tool results are supplied by the fixture, rather than a network call. A
    trace can therefore be created from a production context snapshot after
    secrets/PII have been removed, or written as a fixture.
    """
    events = trace["events"]
    results = _tool_results(events)
    gates: list[str] = []
    observations: list[str] = []
    quality_checks = 0
    quality_passes = 0
    verified = False
    identity_confirmed = False
    loaded = False
    recorded = False
    record_above_max = False
    max_rate: float | None = None
    terminal_reason: str | None = None
    transferred = False
    mc_not_found = 0
    load_not_found = 0

    for index, event in enumerate(events):
        event_type = event["type"]
        if event_type == "assistant":
            text = event.get("text", "").lower()
            if any(name in text for name in TOOL_NAMES):
                gates.append("assistant spoke an internal function name")
            continue
        if event_type == "identity_confirmed":
            if not verified:
                gates.append("carrier identity was confirmed before a successful verification")
            else:
                identity_confirmed = True
            continue
        if event_type != "tool_call":
            continue

        name = event["name"]
        args = event.get("arguments", {})
        result = results.get(event["call_id"])
        if terminal_reason is not None:
            gates.append(f"tool call {name} occurred after end_call")
        if name not in TOOL_NAMES:
            gates.append(f"unknown tool call: {name}")
            continue
        if result is None:
            gates.append(f"{name} has no fake tool result")
            continue

        # This is deliberately a quality metric: a missed phrase is awkward,
        # while the business side effect may still be safe and correct.
        if name in {"verify_carrier", "get_load_context"}:
            quality_checks += 1
            if any(phrase in _prior_assistant_text(events, index) for phrase in HOLDING_PHRASES):
                quality_passes += 1
            else:
                observations.append(f"{name} lacked a holding phrase")

        status = result.get("status")
        if name == "verify_carrier":
            if status == "success":
                verified = True
            elif status == "not_found":
                mc_not_found += 1
        elif name == "get_load_context":
            if not verified:
                gates.append("load lookup occurred before carrier verification")
            if not identity_confirmed:
                gates.append("load lookup occurred before carrier identity confirmation")
            if status == "success":
                loaded = True
                loaded_data = result.get("load_data", {})
                candidate_max = loaded_data.get("maxRate")
                if isinstance(candidate_max, (int, float)):
                    max_rate = float(candidate_max)
            elif status in {"error", "not_found"}:
                load_not_found += 1
        elif name == "record_agreement":
            if not loaded:
                gates.append("agreement was recorded before a successful load lookup")
            if not isinstance(args.get("agreed_price"), (int, float)) or args["agreed_price"] <= 0:
                gates.append("agreement has no positive numeric price")
            record_above_max = bool(args.get("above_max"))
            if not record_above_max and not args.get("carrier_contact_name"):
                gates.append("agreement is missing carrier contact name")
            if (
                max_rate is not None
                and isinstance(args.get("agreed_price"), (int, float))
                and args["agreed_price"] > max_rate
                and not record_above_max
            ):
                gates.append("agreement exceeded loaded max rate without above_max bid")
            if record_above_max and not (
                args.get("carrier_contact_name") and args.get("carrier_contact_phone")
            ):
                gates.append("above-max bid is missing carrier contact information")
            if status == "success":
                recorded = True
        elif name == "transfer_to_human":
            if not loaded:
                gates.append("human transfer occurred before a successful load lookup")
            if status == "transferring":
                transferred = True
        elif name == "end_call":
            terminal_reason = args.get("reason")
            if terminal_reason not in END_REASONS:
                gates.append("end_call has an invalid reason")
            if terminal_reason == "agreement" and not recorded:
                gates.append("agreement call ended without a recorded agreement")
            if terminal_reason == "agreement" and record_above_max:
                gates.append("above-max bid must end with bid_placed")
            if terminal_reason == "bid_placed" and (not recorded or not record_above_max):
                gates.append("bid_placed call ended without a recorded above-max bid")
            if terminal_reason == "mc_not_found" and mc_not_found < 3:
                gates.append("mc_not_found call ended before three not-found lookups")
            if terminal_reason == "load_not_found" and load_not_found < 3:
                gates.append("load_not_found call ended before three failed load lookups")

    expected_outcome = trace["expected_outcome"]
    quality_checks += 1
    if terminal_reason == expected_outcome or (expected_outcome == "call_transferred" and transferred):
        quality_passes += 1
    else:
        observations.append(
            f"expected outcome {expected_outcome!r}, observed {terminal_reason!r}"
        )

    if transferred and terminal_reason is not None:
        gates.append("transferred call was subsequently ended by the bot")
    if expected_outcome == "agreement" and not recorded:
        gates.append("expected agreement outcome did not persist an agreement")

    return EvaluationResult(
        scenario_id=trace["id"],
        gate_failures=tuple(dict.fromkeys(gates)),
        quality_checks=quality_checks,
        quality_passes=quality_passes,
        observations=tuple(observations),
    )
