"""Real normalizer/prompt-builder contract harness."""

from evals.prompt_contracts import run_prompt_contracts
from unittest.mock import patch


def test_prompt_contracts_surface_findings_without_masking_them():
    report = run_prompt_contracts()
    assert report.ordinary_priced.passed is True
    assert report.formatted_rate.passed is True
    assert report.no_rate.passed is True
    # The equal-rate contradiction is intentionally represented in the CLI,
    # not asserted away as passing behavior here.
    assert report.equal_opening_goal.passed is False


def test_equal_rate_builder_exception_is_a_failed_contract():
    with patch("evals.prompt_contracts.build_negotiation_prompt", side_effect=RuntimeError("fixture failure")):
        report = run_prompt_contracts()
    assert report.equal_opening_goal.passed is False
