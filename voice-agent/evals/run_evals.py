#!/usr/bin/env python3
"""Offline evaluator for recorded/simulated Frontline conversation fixtures."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SCENARIOS = ROOT / "scenarios.json"
RESULTS = ROOT / "results"


def assistant_turns(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    return [turn for turn in scenario.get("turns", []) if turn.get("speaker") == "assistant"]


def assistant_text(scenario: dict[str, Any]) -> str:
    return "\n".join(str(turn.get("text", "")) for turn in assistant_turns(scenario)).lower()


def tool_calls(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    return [tool for turn in assistant_turns(scenario) for tool in turn.get("tools", [])]


def evaluate(scenario: dict[str, Any]) -> dict[str, Any]:
    """Evaluate an active fixture using explicit, inspectable expectations."""
    if not isinstance(scenario.get("turns"), list):
        return {"id": scenario["id"], "status": "error", "checks": [], "quality_score": "0/0",
                "failures": ["malformed evidence: turns must be a list"], "evidence": []}
    if not assistant_turns(scenario):
        return {"id": scenario["id"], "status": "unknown", "checks": [], "quality_score": "0/0",
                "failures": ["missing evidence: no observed assistant turn"], "evidence": []}
    if any(not isinstance(turn.get("tools", []), list) for turn in assistant_turns(scenario)):
        return {"id": scenario["id"], "status": "error", "checks": [], "quality_score": "0/0",
                "failures": ["malformed evidence: assistant tools must be a list"], "evidence": []}
    checks: list[dict[str, str]] = []
    failures: list[str] = []
    text = assistant_text(scenario)
    calls = tool_calls(scenario)
    names = [str(call.get("name", "")) for call in calls]
    expected = scenario.get("expectations", {})

    for phrase in expected.get("forbidden_text", []):
        passed = str(phrase).lower() not in text
        checks.append({"rule": f"does not say {phrase!r}", "status": "pass" if passed else "fail"})
        if not passed:
            failures.append(f"forbidden text appeared: {phrase!r}")

    for phrase in expected.get("required_text", []):
        passed = str(phrase).lower() in text
        checks.append({"rule": f"says {phrase!r}", "status": "pass" if passed else "fail"})
        if not passed:
            failures.append(f"required text did not appear: {phrase!r}")

    for name in expected.get("required_tools", []):
        passed = name in names
        checks.append({"rule": f"calls {name}", "status": "pass" if passed else "fail"})
        if not passed:
            failures.append(f"missing required tool: {name}")

    for name in expected.get("forbidden_tools", []):
        passed = name not in names
        checks.append({"rule": f"does not call {name}", "status": "pass" if passed else "fail"})
        if not passed:
            failures.append(f"forbidden tool called: {name}")

    for requirement in expected.get("tool_arguments", []):
        name = requirement["name"]
        arguments = requirement["arguments"]
        passed = any(
            call.get("name") == name
            and all(call.get("arguments", {}).get(key) == value for key, value in arguments.items())
            for call in calls
        )
        checks.append({"rule": f"{name} arguments include {arguments}", "status": "pass" if passed else "fail"})
        if not passed:
            failures.append(f"missing {name} call with arguments {arguments}")

    sequence = expected.get("required_tool_sequence", [])
    cursor = 0
    for name in names:
        if cursor < len(sequence) and name == sequence[cursor]:
            cursor += 1
    if sequence:
        passed = cursor == len(sequence)
        checks.append({"rule": "tool order: " + " → ".join(sequence), "status": "pass" if passed else "fail"})
        if not passed:
            failures.append("tool sequence not observed: " + " → ".join(sequence))

    if "end_reason" in expected:
        reasons = [call.get("arguments", {}).get("reason") for call in calls if call.get("name") == "end_call"]
        passed = expected["end_reason"] in reasons
        checks.append({"rule": f"ends as {expected['end_reason']}", "status": "pass" if passed else "fail"})
        if not passed:
            failures.append(f"expected end reason {expected['end_reason']!r}; saw {reasons!r}")

    quality = expected.get("quality", {})
    quality_checks = {
        "holding_phrase_for_lookup": all(
            not any(tool.get("name") in {"verify_carrier", "get_load_context"} for tool in turn.get("tools", []))
            or any(marker in str(turn.get("text", "")).lower() for marker in ("let me", "one moment", "one second"))
            for turn in assistant_turns(scenario)
        ),
        "no_spoken_function_names": not any(name in text for name in ("verify_carrier", "get_load_context", "record_agreement", "end_call", "transfer_to_human")),
    }
    score = 0
    possible = 0
    for key, required in quality.items():
        if required:
            possible += 1
            passed = quality_checks.get(key, False)
            score += int(passed)
            checks.append({"rule": f"quality: {key}", "status": "pass" if passed else "fail"})
            if not passed:
                failures.append(f"interaction quality failed: {key}")

    evidence = [{"turn": index + 1, "text": turn.get("text", ""), "tools": [tool.get("name") for tool in turn.get("tools", [])]}
                for index, turn in enumerate(assistant_turns(scenario))]
    return {"id": scenario["id"], "status": "pass" if not failures else "fail", "checks": checks,
            "quality_score": f"{score}/{possible}", "failures": failures, "evidence": evidence}


def write_markdown(report: dict[str, Any], destination: Path) -> None:
    lines = ["# Frontline evaluation results", "", f"Generated: {report['generated_at']}", ""]
    for result in report["results"]:
        lines += [f"## {result['id']}: {result['status'].upper()}", ""]
        lines += [f"- Quality score: {result['quality_score']}"]
        lines += [f"- {check['status'].upper()}: {check['rule']}" for check in result["checks"]]
        lines += [f"- Failure: {failure}" for failure in result["failures"]]
        lines += [f"- Evidence turn {item['turn']}: tools={item['tools']}; text={item['text']!r}" for item in result.get("evidence", [])]
        lines.append("")
    destination.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    payload = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    active = [scenario for scenario in payload["scenarios"] if scenario.get("status") == "active"]
    if "--demo-violation" in sys.argv:
        active.append({"id": "intentional-confidentiality-violation", "turns": [{"speaker": "assistant", "text": "Our ceiling is 1800."}], "expectations": {"forbidden_text": ["ceiling", "1800"]}})
    results = [evaluate(scenario) for scenario in active]
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "active": len(active),
              "planned": max(0, len(payload["scenarios"]) - len(active)), "results": results}
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "latest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_markdown(report, RESULTS / "latest.md")
    print(f"Evaluated {report['active']} active scenarios; {report['planned']} planned.")
    for result in results:
        print(f"{result['status'].upper():4} {result['id']} ({result['quality_score']})")
        for failure in result["failures"]:
            print(f"     {failure}")
    return 1 if any(result["status"] in {"fail", "error", "unknown"} for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
