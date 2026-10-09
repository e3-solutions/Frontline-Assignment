"""Regression coverage for multi-run evidence aggregation."""

from evals.__main__ import _aggregate


def test_aggregate_preserves_each_run_and_fails_if_any_run_fails():
    runs = [
        {"real_handlers": [{"name": "case", "expected": "safe", "observed": "first", "verdict": "FAIL", "evidence": ["first failed"]}]},
        {"real_handlers": [{"name": "case", "expected": "safe", "observed": "second", "verdict": "PASS", "evidence": ["second passed"]}]},
    ]

    aggregate = _aggregate(runs, "real_handlers")

    assert aggregate[0]["verdict"] == "FAIL"
    assert aggregate[0]["evidence"] == ["Run 1: first failed", "Run 2: second passed"]
