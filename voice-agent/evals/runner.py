"""CLI for deterministic evaluation of stored traces."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .graders import grade_trace
from .models import EvaluationResult, Trace


def evaluate_file(path: Path) -> EvaluationResult:
    trace = Trace.from_dict(json.loads(path.read_text()))
    findings = grade_trace(trace)
    return EvaluationResult(trace.scenario_id, not findings, findings)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, default=Path(__file__).parent / "fixtures" / "traces")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--critic", action="store_true", help="Run optional credential-gated model critic")
    args = parser.parse_args()
    paths = sorted(args.traces.glob("*.json"))
    evaluated = [(path, evaluate_file(path)) for path in paths]
    results = [result for _, result in evaluated]
    payload = {"results": [result.to_dict() for result in results]}
    if args.critic:
        from .critic import critique

        critic_runs = max(1, int(os.getenv("EVAL_CRITIC_RUNS", "3")))
        critic_results = []
        for path, _ in evaluated:
            trace = Trace.from_dict(json.loads(path.read_text()))
            runs = [critique(trace) for _ in range(critic_runs)]
            critic_results.append({"scenario_id": trace.scenario_id, "runs": runs})
        payload["critic"] = critic_results
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2) + "\n")
    for path, result in evaluated:
        expectation = Trace.from_dict(json.loads(path.read_text())).expected_pass
        matched = expectation is None or result.passed == expectation
        print(f"{'PASS' if matched else 'FAIL'} {result.scenario_id}: grader_pass={result.passed}, findings={len(result.findings)}")
        for finding in result.findings:
            print(f"  {finding.code}: {finding.message}")
    return 0 if all(
        Trace.from_dict(json.loads(path.read_text())).expected_pass in (None, result.passed)
        for path, result in evaluated
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
