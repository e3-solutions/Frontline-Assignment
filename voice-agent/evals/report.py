"""Portable report serialization for the offline evaluation runner."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from evals.checks import EvaluationResult

REPORT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = REPORT_DIR.parents[1]


def _commit() -> str:
    result = subprocess.run(["git", "-c", f"safe.directory={WORKSPACE_ROOT}", "rev-parse", "HEAD"], cwd=WORKSPACE_ROOT, check=False, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unavailable"


def _working_tree_changes() -> str:
    result = subprocess.run(["git", "-c", f"safe.directory={WORKSPACE_ROOT}", "status", "--short"], cwd=WORKSPACE_ROOT, check=False, capture_output=True, text=True)
    return result.stdout.strip() or "clean"


def scenario(name: str, expected: str, observed: str, result: EvaluationResult, *, verdict: str | None = None) -> dict:
    return {"name": name, "expected": expected, "observed": observed, "verdict": verdict or ("PASS" if result.passed else "FAIL"), "evidence": list(result.evidence)}


def _summary(items: list[dict], *, allow_unresolved: bool = False) -> dict:
    passed = sum(item["verdict"] == "PASS" for item in items)
    failed = sum(item["verdict"] == "FAIL" for item in items)
    unresolved = sum(item["verdict"] == "UNRESOLVED" for item in items) if allow_unresolved else 0
    denominator = passed + failed
    return {"passed": passed, "failed": failed, "unresolved": unresolved, "denominator": denominator, "pass_percent": round(100 * passed / denominator, 1) if denominator else 0.0, "fail_percent": round(100 * failed / denominator, 1) if denominator else 0.0}


def _table(items: list[dict]) -> str:
    rows = ["| Scenario | Expected outcome | Observed outcome | Verdict | Evidence |", "| --- | --- | --- | --- | --- |"]
    rows.extend(f"| {item['name']} | {item['expected']} | {item['observed']} | {item['verdict']} | {'<br>'.join(item['evidence'])} |" for item in items)
    return "\n".join(rows)


def write_report(*, requested_run_count: int, run_results: list[dict], duration_seconds: float, evaluation_pytest: str, existing_regression: str, real_handlers: list[dict], prompt_contracts: list[dict], calibration: list[dict], errors: list[str]) -> dict:
    """Write JSON and Markdown evidence while preserving category boundaries."""
    real = _summary(real_handlers, allow_unresolved=True)
    prompts = _summary(prompt_contracts)
    synthetic = _summary(calibration)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "evaluated_source_revision": _commit(),
        "working_tree_changes": _working_tree_changes(),
        "requested_run_count": requested_run_count, "completed_run_count": len(run_results),
        "run_results": run_results, "duration_seconds": round(duration_seconds, 3),
        "unique_scenario_count": len(real_handlers) + len(prompt_contracts) + len(calibration),
        "evaluation_pytest": evaluation_pytest, "existing_regression_tests": existing_regression,
        "real_handler_summary": {**real, "errored": len(errors)},
        "prompt_contract_summary": prompts, "synthetic_calibration_summary": synthetic,
        "real_handler_scenarios": real_handlers, "prompt_contracts": prompt_contracts,
        "synthetic_calibration": calibration, "errors": errors,
        "runner_exit_code": int(bool(errors) or real["failed"] > 0 or prompts["failed"] > 0),
    }
    (REPORT_DIR / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    markdown = f"""# Offline evaluation report

- Evaluated source revision: `{report['evaluated_source_revision']}`
- Working-tree changes at evaluation: `{report['working_tree_changes']}`
- Timestamp (UTC): `{report['generated_at']}`
- Completed run count: {report['completed_run_count']}/{requested_run_count}
- Duration: {report['duration_seconds']} seconds
- Unique scenario count: {report['unique_scenario_count']} (handler, prompt-contract, and synthetic-control scenarios; assertions are not counted separately)
- Evaluation-harness pytest: {evaluation_pytest}
- Existing mocked regression pytest: {existing_regression}
- Complete runner exit code: {report['runner_exit_code']}

## Existing regression coverage (pre-existing tests)

`tests/test_phone_carrier_lookup.py` supplies mocked carrier-verification and phone-first persistence coverage. `tests/test_transfer_tool_handler.py` supplies mocked transfer load/routing guard coverage. They are run and reported above as existing regressions, not re-counted as new scenarios.

## Real-handler evaluations

{_table(real_handlers)}

## Prompt contracts

{_table(prompt_contracts)}

## Synthetic behavioral/grader calibration

{_table(calibration)}

## Counts and interpretation

- Real handlers: {real['passed']} passed, {real['failed']} failed, {real['unresolved']} unresolved, {len(errors)} errored; resolved denominator {real['denominator']}: {real['pass_percent']}% pass ({real['passed']}/{real['denominator']}) and {real['fail_percent']}% fail ({real['failed']}/{real['denominator']}).
- Prompt contracts: {prompts['passed']} passed, {prompts['failed']} failed, denominator {prompts['denominator']}: {prompts['pass_percent']}% pass and {prompts['fail_percent']}% fail. Failures are documented findings, not weakened expectations.
- Synthetic calibration: {synthetic['passed']} passed, {synthetic['failed']} failed, denominator {synthetic['denominator']}: {synthetic['pass_percent']}% pass. Deliberately unacceptable traces rejected by the grader are calibration passes, not product failures.
- Transfer identity policy remains unresolved: the direct fixture observes transfer with `carrier_identity_confirmed=False`, while `HIGHWAY_PHONE_LOOKUP_ENABLED` controls whether that state is populated upstream.
- `--run-count` repeats deterministic mocked cases; it tests repeatability, not live-model reliability.

Runner exit is nonzero for failed real-handler/prompt-contract evaluations or any execution error. No network, credentials, live speech, or model calls are used.
"""
    (REPORT_DIR / "report.md").write_text(markdown)
    return report
