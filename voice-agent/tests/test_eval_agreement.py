"""Offline evaluation of the above-max agreement recording boundary."""

from __future__ import annotations

import pytest

from evals.agreement import run_above_max_agreement_scenario


@pytest.mark.asyncio
async def test_evaluator_flags_normal_above_max_agreement_and_accepts_follow_up():
    """The evaluator passes by detecting the first path's product failure."""
    report = await run_above_max_agreement_scenario()

    assert report.normal_evaluation.passed == (
        not report.normal_save_calls and not report.normal_quote_calls
    )
    assert report.follow_up_evaluation.passed == (
        bool(report.follow_up_save_calls) and not report.follow_up_quote_calls
    )
    assert all(call[3] is False for call in report.normal_save_calls)
    assert all(call[3] is True for call in report.follow_up_save_calls)
    assert report.follow_up_payload_evaluation.passed is True
    assert report.below_ceiling_evaluation.passed is True
    assert report.save_failure_evaluation.passed is True
    assert report.below_ceiling_save_calls[0] == (
        "00000000-0000-0000-0000-000000000123",
        2000.0,
        "00000000-0000-0000-0000-000000000099",
        False,
        "Jordan Carrier",
        "+14155550102",
    )
    assert report.below_ceiling_quote_calls == (
        {
            "load_name": "REF-1234",
            "agreed_price": 2000.0,
            "mc_number": "123456",
            "source_type": "call",
            "carrier_name": "Jordan Carrier",
            "carrier_phone": "+14155550102",
        },
    )
    assert report.save_failure_result == {
        "status": "error",
        "message": "Failed to record in database",
    }
    assert report.save_failure_quote_calls == ()
