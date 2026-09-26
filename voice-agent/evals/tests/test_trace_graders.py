import json
from pathlib import Path

import pytest

from evals.graders import grade_trace
from evals.models import Trace
from evals.runner import evaluate_file


FIXTURES = Path(__file__).parents[1] / "fixtures" / "traces"


def test_correct_above_ceiling_trace_passes():
    result = evaluate_file(FIXTURES / "above_ceiling_pass.json")
    assert result.passed, [finding.code for finding in result.findings]


def test_broken_above_ceiling_trace_fails_with_specific_diagnostics():
    result = evaluate_file(FIXTURES / "above_ceiling_false_agreement.json")
    codes = {finding.code for finding in result.findings}
    assert not result.passed
    assert "IMPLIED_AGREEMENT" in codes
    assert "NORMAL_AGREEMENT_ABOVE_CEILING" in codes
    assert "WRONG_ABOVE_MAX_END_REASON" in codes
    assert "KCH_QUOTE_FOR_ABOVE_MAX" in codes


@pytest.mark.parametrize("fixture", ["empty.json", "incomplete.json"])
def test_empty_and_incomplete_traces_cannot_pass(fixture):
    result = evaluate_file(FIXTURES / fixture)
    assert not result.passed
    assert any(finding.code == "MISSING_TERMINAL_ACTION" for finding in result.findings)


def test_mutation_of_passing_trace_is_detected():
    data = json.loads((FIXTURES / "above_ceiling_pass.json").read_text())
    data["events"][5]["arguments"]["above_max"] = False
    findings = grade_trace(Trace.from_dict(data))
    assert "NORMAL_AGREEMENT_ABOVE_CEILING" in {finding.code for finding in findings}


@pytest.mark.parametrize(
    "fixture, code",
    [
        ("mc_rejection_is_not_strike.json", "PREMATURE_MC_TERMINATION"),
        ("wrong_identity_used.json", "WRONG_IDENTITY_USED"),
        ("below_goal_bad_counter.json", "COUNTER_NOT_BELOW_CARRIER_BID"),
    ],
)
def test_policy_breakages_are_diagnosed(fixture, code):
    result = evaluate_file(FIXTURES / fixture)
    assert not result.passed
    assert code in {finding.code for finding in result.findings}
