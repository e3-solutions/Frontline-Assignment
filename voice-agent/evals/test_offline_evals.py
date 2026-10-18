"""Runnable golden-trace tests for the offline evaluation harness."""

import pytest

from evals.evaluator import evaluate_trace
from evals.golden_traces import GOLDEN_TRACES, UNSAFE_TRACES


@pytest.mark.parametrize("trace", GOLDEN_TRACES, ids=lambda trace: trace["id"])
def test_golden_trace_passes_all_safety_gates(trace):
    result = evaluate_trace(trace)
    assert result.passed_gates, result.gate_failures
    assert result.quality_score == 1.0, result.observations


@pytest.mark.parametrize("trace", UNSAFE_TRACES, ids=lambda trace: trace["id"])
def test_intentionally_unsafe_traces_fail_their_target_gate(trace):
    result = evaluate_trace(trace)
    assert not result.passed_gates
    assert trace["expected_gate"] in result.gate_failures


def test_unsafe_trace_corpus_covers_distinct_safety_invariants():
    target_gates = {trace["expected_gate"] for trace in UNSAFE_TRACES}
    assert len(target_gates) == len(UNSAFE_TRACES)
