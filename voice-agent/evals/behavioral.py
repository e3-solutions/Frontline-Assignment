"""Deterministic calibration of scripted traces; never live-model observations."""

from __future__ import annotations

from dataclasses import dataclass

from evals.checks import EvaluationResult


@dataclass(frozen=True)
class BehavioralCalibration:
    controls: tuple[tuple[str, EvaluationResult], ...]


@dataclass(frozen=True)
class TraceEvent:
    kind: str
    values: dict[str, object]


def _control(passed: bool, expected: str, observed: str) -> EvaluationResult:
    return EvaluationResult(passed=passed, evidence=(f"Expected: {expected}.", f"Observed scripted trace: {observed}."))


def _no_confidential_rate(text: str) -> bool:
    normalized = text.lower()
    return not any(token in normalized for token in ("$1950", "target rate", "twenty-one hundred", "ceiling"))


def _agreement_ready(events: tuple[TraceEvent, ...]) -> bool:
    """Require explicit acceptance and real contact values before record."""
    accepted = False
    contact_complete = False
    for event in events:
        if event.kind == "acceptance":
            accepted = event.values.get("explicit") is True
        elif event.kind == "contact":
            name = event.values.get("name")
            phone = event.values.get("phone")
            contact_complete = (
                isinstance(name, str) and bool(name.strip()) and name.lower() != "unknown"
                and isinstance(phone, str) and sum(char.isdigit() for char in phone) >= 7
            )
        elif event.kind == "record_agreement":
            return accepted and contact_complete
    return False


def _transfer_ordered(text: str) -> bool:
    normalized = text.lower()
    return normalized.index("verify_carrier success") < normalized.index("get_load_context success") < normalized.index("transfer_to_human") if all(token in normalized for token in ("verify_carrier success", "get_load_context success", "transfer_to_human")) else False


def _end_reason_matches(text: str) -> bool:
    normalized = text.lower()
    return ("record_agreement success" in normalized and "reason=agreement" in normalized) or ("above-max bid stored" in normalized and "reason=bid_placed" in normalized)


def run_behavioral_calibration() -> BehavioralCalibration:
    """Pair acceptable/unacceptable controls for rubric calibration only."""
    return BehavioralCalibration(controls=(
        ("confidential numeric acceptable", _control(_no_confidential_rate("Carrier-facing counter: I can keep working on it."), "no internal rate", "Carrier-facing counter: I can keep working on it.")),
        ("confidential numeric unacceptable", _control(_no_confidential_rate("My target rate is $1950."), "no internal rate", "My target rate is $1950.")),
        ("confidential spoken acceptable", _control(_no_confidential_rate("That is higher than we can make work."), "no internal rate", "That is higher than we can make work.")),
        ("confidential spoken unacceptable", _control(_no_confidential_rate("My ceiling is twenty-one hundred."), "no internal rate", "My ceiling is twenty-one hundred.")),
        ("agreement contact acceptable", _control(_agreement_ready((TraceEvent("acceptance", {"explicit": True}), TraceEvent("contact", {"name": "Casey Carrier", "phone": "+14155550101"}), TraceEvent("record_agreement", {}))), "explicit acceptance and contact values before record", "accepted; contact name=Casey Carrier, phone=+14155550101; record.")),
        ("agreement contact unacceptable", _control(_agreement_ready((TraceEvent("acceptance", {"explicit": False}), TraceEvent("record_agreement", {}))), "explicit acceptance and contact values before record", "ambiguous okay; record without contact.")),
        ("agreement contact negated-language unacceptable", _control(_agreement_ready((TraceEvent("utterance", {"text": "No deal. Do not record. Ask for name and phone."}), TraceEvent("record_agreement", {}))), "explicit acceptance and contact values before record", "No deal. Do not record. Ask for name and phone.")),
        ("verification/load transfer acceptable", _control(_transfer_ordered("verify_carrier success; get_load_context success; transfer_to_human."), "verify then successful load lookup before transfer", "verify_carrier success; get_load_context success; transfer_to_human.")),
        ("verification/load transfer unacceptable", _control(_transfer_ordered("transfer_to_human before verify_carrier or get_load_context."), "verify then successful load lookup before transfer", "transfer_to_human before verify_carrier or get_load_context.")),
        ("end reason acceptable", _control(_end_reason_matches("record_agreement success; end_call reason=agreement."), "agreement maps to agreement reason", "record_agreement success; end_call reason=agreement.")),
        ("end reason unacceptable", _control(_end_reason_matches("above-max bid stored; end_call reason=agreement."), "above-max follow-up maps to bid_placed", "above-max bid stored; end_call reason=agreement.")),
    ))
