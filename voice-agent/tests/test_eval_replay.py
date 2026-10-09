"""Harness contract for shared greeting-to-load-context replay scenarios."""

import pytest

from evals.replay import run_lookup_replay_scenarios


@pytest.mark.asyncio
async def test_lookup_replay_scenarios_pass():
    """Pytest and the CLI execute the same three mocked handler scenarios."""
    report = await run_lookup_replay_scenarios()

    assert report.successful_lookup.passed is True
    assert report.invalid_reference.passed is True
    assert report.missing_load.passed is True
