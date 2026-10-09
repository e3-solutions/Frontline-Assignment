"""Offline evaluation of the transfer identity-confirmation boundary."""

import pytest

from evals.transfer import run_unconfirmed_transfer_probe


@pytest.mark.asyncio
async def test_evaluator_reports_transfer_started_for_unconfirmed_carrier():
    """The test passes because it detects the real missing identity guard."""
    report = await run_unconfirmed_transfer_probe()

    assert report.evaluation.passed is (
        report.orchestration_started and report.transfer_scheduled
    )
    assert report.policy_verdict == "UNRESOLVED"
    assert "Context had load_uuid and carrier_identity_confirmed=False." in report.evaluation.evidence
    assert (
        "Observed handler behavior: it does not inspect the false identity flag before transfer."
        in report.evaluation.evidence
    )
