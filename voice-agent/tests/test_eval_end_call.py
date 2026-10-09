"""Harness checks for shared production end_call probes."""

import pytest

from evals.end_call import run_end_call_scenarios


@pytest.mark.asyncio
async def test_end_call_scenarios_pass():
    report = await run_end_call_scenarios()
    assert report.valid_reason.passed is True
    assert report.invalid_reason.passed is True
