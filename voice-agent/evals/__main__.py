"""Run complete mocked evaluations and write categorized durable evidence."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
import time

from evals.agreement import run_above_max_agreement_scenario
from evals.behavioral import run_behavioral_calibration
from evals.calibration import run_room1_grader_calibration
from evals.end_call import run_end_call_scenarios
from evals.checks import EvaluationResult
from evals.prompt_contracts import run_prompt_contracts
from evals.replay import run_lookup_replay_scenarios
from evals.report import scenario, write_report
from evals.transfer import run_unconfirmed_transfer_probe

EVAL_TESTS = ["tests/test_eval_replay.py", "tests/test_eval_agreement.py", "tests/test_eval_transfer.py", "tests/test_eval_prompt_grading.py", "tests/test_eval_end_call.py", "tests/test_eval_prompt_contracts.py", "tests/test_eval_behavioral.py", "tests/test_eval_runner.py"]
EXISTING_REGRESSION_TESTS = ["tests/test_phone_carrier_lookup.py", "tests/test_transfer_tool_handler.py"]


def _pytest(paths: list[str]) -> tuple[str, bool]:
    result = subprocess.run([sys.executable, "-m", "pytest", *paths, "-q"], capture_output=True, text=True)
    return f"exit {result.returncode}: {result.stdout.strip()}", result.returncode == 0


def _row(name: str, expected: str, result, verdict: str | None = None) -> dict:
    """Use handler/grader evidence itself as the reported observation."""
    observed = " ".join(result.evidence)
    return scenario(name, expected, observed, result, verdict=verdict)


def _merged_result(*results: EvaluationResult) -> EvaluationResult:
    """Retain every captured sub-check as evidence for one parent scenario."""
    return EvaluationResult(
        passed=all(result.passed for result in results),
        evidence=tuple(item for result in results for item in result.evidence),
    )


def _capture_rows(lookup, agreement, transfer, end_call, prompts, room1, behavioral) -> dict[str, list[dict]]:
    follow_up = _merged_result(
        agreement.follow_up_evaluation, agreement.follow_up_payload_evaluation
    )
    transfer_observation = EvaluationResult(
        passed=transfer.evaluation.passed,
        evidence=(
            f"Captured transfer callback result: {transfer.result!r}.",
            f"Captured transfer metadata call: {transfer.orchestration_started}.",
            f"Captured transfer scheduling call: {transfer.transfer_scheduled}.",
            *transfer.evaluation.evidence,
        ),
    )
    calibration = [
        _row("Room1 good disclosure control", "accept safe text", room1.good_control),
        _row("Room1 planted disclosure control", "reject internal target/ceiling", room1.planted_bad_control, "PASS" if not room1.planted_bad_control.passed else "FAIL"),
        *[_row(name, "accept acceptable / reject unacceptable scripted trace", result, "PASS" if result.passed == ("unacceptable" not in name) else "FAIL") for name, result in behavioral.controls],
    ]
    return {
        "real_handlers": [
            _row("lookup success", "replace system prompt; preserve history; update call record", lookup.successful_lookup),
            _row("lookup invalid reference", "error with no lookup/write or context mutation", lookup.invalid_reference),
            _row("lookup missing load", "error with org argument and no call write", lookup.missing_load),
            _row("above-max normal agreement", "no save and no quote", agreement.normal_evaluation),
            _row("above-max follow-up", "exact follow-up save payload; no quote", follow_up),
            _row("below-ceiling agreement", "exact save and quote payloads", agreement.below_ceiling_evaluation),
            _row("save failure", "error and no quote after None save", agreement.save_failure_evaluation),
            _row("transfer identity fixture", "policy unspecified across feature flags", transfer_observation, transfer.policy_verdict),
            _row("end_call valid reason", "store agreement reason and queue EndFrame", end_call.valid_reason),
            _row("end_call invalid reason", "error; no state mutation or EndFrame", end_call.invalid_reason),
        ],
        "prompt_contracts": [
            _row("ordinary priced prompt", "normalized rates and agreement/end instructions", prompts.ordinary_priced),
            _row("no-rate prompt", "no-rate instruction without literal None prices", prompts.no_rate),
            _row("formatted-rate prompt", "parse $1,800.50 / 1,950 / $2,100 and render opening", prompts.formatted_rate),
            _row("equal opening/goal prompt", "no instruction contradiction and no builder exception", prompts.equal_opening_goal),
        ],
        "synthetic_calibration": calibration,
    }


def _aggregate(runs: list[dict], category: str) -> list[dict]:
    """Keep every captured run and fail an aggregate row if any run fails."""
    if not runs:
        return []
    output: list[dict] = []
    for index, first in enumerate(runs[0][category]):
        per_run = [run[category][index] for run in runs]
        verdicts = [row["verdict"] for row in per_run]
        verdict = "FAIL" if "FAIL" in verdicts else "UNRESOLVED" if all(item == "UNRESOLVED" for item in verdicts) else "PASS"
        evidence = [f"Run {number + 1}: {item}" for number, row in enumerate(per_run) for item in row["evidence"]]
        output.append({**first, "verdict": verdict, "observed": " ".join(evidence), "evidence": evidence})
    return output


async def main(run_count: int) -> int:
    started = time.monotonic()
    errors: list[str] = []
    completed_runs: list[dict] = []
    for run_number in range(1, run_count + 1):
        try:
            captured = _capture_rows(
                await run_lookup_replay_scenarios(),
                await run_above_max_agreement_scenario(),
                await run_unconfirmed_transfer_probe(),
                await run_end_call_scenarios(),
                run_prompt_contracts(),
                run_room1_grader_calibration(),
                run_behavioral_calibration(),
            )
            completed_runs.append(captured)
        except Exception as error:
            errors.append(f"run {run_number} scenario execution: {type(error).__name__}: {error}")

    eval_pytest, eval_ok = _pytest(EVAL_TESTS)
    existing_pytest, existing_ok = _pytest(EXISTING_REGRESSION_TESTS)
    if not eval_ok:
        errors.append(f"evaluation harness pytest failed: {eval_pytest}")
    if not existing_ok:
        errors.append(f"existing regression pytest failed: {existing_pytest}")

    report = write_report(
        requested_run_count=run_count, run_results=completed_runs,
        duration_seconds=time.monotonic() - started,
        evaluation_pytest=eval_pytest, existing_regression=existing_pytest,
        real_handlers=_aggregate(completed_runs, "real_handlers"),
        prompt_contracts=_aggregate(completed_runs, "prompt_contracts"),
        calibration=_aggregate(completed_runs, "synthetic_calibration"), errors=errors,
    )
    print("Wrote evals/report.md and evals/report.json")
    print(f"Completed runs: {report['completed_run_count']}/{report['requested_run_count']}")
    print(f"Real handlers: {report['real_handler_summary']}")
    print(f"Prompt contracts: {report['prompt_contract_summary']}")
    print(f"Synthetic calibration: {report['synthetic_calibration_summary']}")
    return report["runner_exit_code"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-count", type=int, default=1)
    args = parser.parse_args()
    if args.run_count < 1:
        parser.error("--run-count must be at least 1")
    return args


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(parse_args().run_count)))
