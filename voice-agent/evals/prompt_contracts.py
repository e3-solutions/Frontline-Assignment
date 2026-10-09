"""Prompt contracts using the real load normalizer and negotiation builder."""

from __future__ import annotations

from dataclasses import dataclass

from evals.checks import EvaluationResult
from load_context_utils import build_negotiation_prompt, normalize_load_data


def _raw_load(**rates):
    return {
        "load_id": "PROMPT-123", "origin_city": "Atlanta", "origin_state": "GA",
        "destination_city": "Chicago", "destination_state": "IL", "equipment": "Dry van",
        "commodity": "PAPER GOODS", "special_instructions": "CHECK IN",
        **rates,
    }


@dataclass(frozen=True)
class PromptContractReport:
    ordinary_priced: EvaluationResult
    no_rate: EvaluationResult
    formatted_rate: EvaluationResult
    equal_opening_goal: EvaluationResult


def _build(raw):
    normalized = normalize_load_data(raw)
    try:
        return normalized, build_negotiation_prompt(normalized), None
    except Exception as error:
        return normalized, None, f"{type(error).__name__}: {error}"


def run_prompt_contracts() -> PromptContractReport:
    """Keep contradictions visible rather than changing expected contracts."""
    ordinary, ordinary_prompt, ordinary_error = _build(_raw_load(start_rate=1800, book_now_rate=1950, max_rate=2100))
    ordinary_result = EvaluationResult(
        passed=(ordinary_error is None and all(value in ordinary_prompt for value in ("Opening Offer: $1800.0", "Internal Goal: $1950.0", "Internal Ceiling: $2100.0", "record_agreement", "end_call"))),
        evidence=(f"Normalized rates: start={ordinary['startRate']}, goal={ordinary['bookNowRate']}, max={ordinary['maxRate']}.", f"Builder error: {ordinary_error!r}.", "Checked pricing values and agreement/end instructions."),
    )
    no_rate, no_rate_prompt, no_rate_error = _build(_raw_load(start_rate=None, book_now_rate=None, max_rate=None))
    no_rate_result = EvaluationResult(
        passed=(no_rate_error is None and "NO RATE MODE" in no_rate_prompt and "None" not in no_rate_prompt),
        evidence=(f"Normalized no-rate values: {no_rate['startRate']!r}, {no_rate['bookNowRate']!r}, {no_rate['maxRate']!r}.", f"Builder error: {no_rate_error!r}.", "Expected no-rate instruction without literal None pricing values."),
    )
    formatted, formatted_prompt, formatted_error = _build(_raw_load(start_rate="$1,800.50", book_now_rate="1,950", max_rate="$2,100"))
    formatted_result = EvaluationResult(
        passed=(formatted_error is None and (formatted['startRate'], formatted['bookNowRate'], formatted['maxRate']) == (1800.5, 1950.0, 2100.0) and "$1800.5" in formatted_prompt),
        evidence=(f"Normalized formatted rates: start={formatted['startRate']}, goal={formatted['bookNowRate']}, max={formatted['maxRate']}.", f"Builder error: {formatted_error!r}.", "Checked formatted opening rate is rendered."),
    )
    equal, equal_prompt, equal_error = _build(_raw_load(start_rate=1800, book_now_rate=1800, max_rate=2100))
    opening_instruction = 'State your initial offer: "This lane is going for $1800.0"'
    forbidden_opening_amount = "- $1800.0 / $1,800.0"
    equal_contradiction = (
        equal_error is None
        and opening_instruction in equal_prompt
        and forbidden_opening_amount in equal_prompt
    )
    equal_result = EvaluationResult(
        passed=equal_error is None and not equal_contradiction,
        evidence=(f"Normalized equal rates: start={equal['startRate']}, goal={equal['bookNowRate']}, max={equal['maxRate']}.", f"Builder error: {equal_error!r}.", f"Required opening instruction present: {opening_instruction in equal_prompt if equal_prompt else False}.", f"Actual opening amount forbidden: {forbidden_opening_amount in equal_prompt if equal_prompt else False}.", "Finding: opening rate equals internal goal while the prompt both requires saying it and forbids that exact amount." if equal_contradiction else "No opening/goal contradiction observed."),
    )
    return PromptContractReport(ordinary_result, no_rate_result, formatted_result, equal_result)
