"""Parallel, safe evaluation runner.

Default mode audits deterministic scenario traces.  It has no network calls,
does not read application credentials, and never invokes a provider.  Live
adapters are deliberately separate from this module's default path.
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from statistics import median

from .models import ExpectedTurn, Scenario, ScenarioResult, TurnResult
from .scenarios import SCENARIOS


def percentile(values: list[float], value: int) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil((value / 100) * len(ordered)) - 1)
    return ordered[index]


def _offline_observation(turn: ExpectedTurn) -> tuple[str, list[str], dict[str, dict[str, object]]]:
    """Golden safe behavior, used to exercise the evaluator rather than an LLM."""
    # This deliberately supplies no potentially secret rate text. The exact
    # content is not a model response and is labelled synthetic in reports.
    text = "Let me check that."
    if "reference" in turn.required_phrases:
        text = "Great, do you have a reference number?"
    if "one moment" in turn.required_phrases:
        text = "One moment."
    return text, list(turn.required_tools), turn.required_tool_arguments


def evaluate_turn(turn: ExpectedTurn, text: str, tools: list[str], tool_arguments: dict[str, dict[str, object]] | None = None) -> TurnResult:
    lower = text.lower()
    failures: list[str] = []
    for tool in turn.required_tools:
        if tool not in tools:
            failures.append(f"missing required tool: {tool}")
    for tool in turn.forbidden_tools:
        if tool in tools:
            failures.append(f"forbidden tool invoked: {tool}")
    for phrase in turn.required_phrases:
        if phrase not in lower:
            failures.append(f"missing required phrase: {phrase}")
    for phrase in turn.forbidden_phrases:
        if phrase in lower:
            failures.append(f"forbidden phrase leaked: {phrase}")
    tool_arguments = tool_arguments or {}
    for tool, expected in turn.required_tool_arguments.items():
        actual = tool_arguments.get(tool, {})
        for key, value in expected.items():
            if actual.get(key) != value:
                failures.append(f"incorrect {tool}.{key}: expected {value!r}, got {actual.get(key)!r}")
    return TurnResult(turn.caller, not failures, failures, tools, tool_arguments, turn.synthetic_ms)


def evaluate_scenario(scenario: Scenario, judge=None) -> ScenarioResult:
    results = []
    for turn in scenario.turns:
        text, tools, tool_arguments = _offline_observation(turn)
        result = evaluate_turn(turn, text, tools, tool_arguments)
        if judge is not None:
            try:
                result.judge = judge.judge(result, asdict(turn))
            except Exception as exc:
                # An unavailable external judge is a diagnostic infrastructure
                # failure, not a reason to report a fake behavioral pass.
                result.passed = False
                result.failures.append(f"judge unavailable: {exc}")
        results.append(result)
    audio = [r.latency_ms.get("first_audio") for r in results if r.latency_ms.get("first_audio") is not None]
    passed = all(r.passed for r in results)
    return ScenarioResult(
        scenario.id, scenario.priority, "PASS" if passed else "FAIL", scenario.boundary,
        results, median(audio) if audio else None, percentile(audio, 95),
        sum(r.passed for r in results) / len(results) if results else 0,
    )


def run_parallel(scenarios: tuple[Scenario, ...], workers: int, judge=None) -> list[ScenarioResult]:
    """Parallelize independent scenarios; retain deterministic report order."""
    with ThreadPoolExecutor(max_workers=max(1, workers), thread_name_prefix="voice-eval") as pool:
        futures = {pool.submit(evaluate_scenario, scenario, judge): scenario.id for scenario in scenarios}
        result_by_id = {}
        for future in as_completed(futures):
            result_by_id[futures[future]] = future.result()
    return [result_by_id[scenario.id] for scenario in scenarios]


def build_report(results: list[ScenarioResult], mode: str) -> dict:
    turns = [turn for result in results for turn in result.turns]
    return {
        "mode": mode,
        "side_effects": "none; fixture-backed offline evaluation",
        "summary": {"scenarios": len(results), "passed": sum(r.status == "PASS" for r in results),
                    "failed": sum(r.status == "FAIL" for r in results), "turn_completion_rate": sum(t.passed for t in turns) / len(turns)},
        "latency": {"label": "synthetic timing validates metric aggregation; it is not production performance",
                    "p50_first_audio_ms": median([t.latency_ms["first_audio"] for t in turns]),
                    "p95_first_audio_ms": percentile([t.latency_ms["first_audio"] for t in turns], 95)},
        "scenarios": [result.to_dict() for result in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run safe Frontline voice-agent evaluations")
    parser.add_argument("--workers", type=int, default=4, help="parallel scenarios (default: 4)")
    parser.add_argument("--output", type=Path, default=Path("eval-report.json"))
    parser.add_argument("--judge-command", help="optional JSONL-compatible small-model judge command")
    args = parser.parse_args()
    judge = None
    if args.judge_command:
        from .live import CommandJudge
        judge = CommandJudge(args.judge_command)
    report = build_report(run_parallel(SCENARIOS, args.workers, judge), "offline+judge" if judge else "offline")
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"{report['summary']['passed']}/{report['summary']['scenarios']} scenarios passed; "
          f"turn completion {report['summary']['turn_completion_rate']:.0%}; report: {args.output}")
    return 0 if report["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
