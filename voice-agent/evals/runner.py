"""Run deterministic, offline pricing evaluations with only Python's stdlib.

Run from ``voice-agent``:
    python3 -m evals.runner
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = Path(__file__).with_name("cases") / "pricing.json"
TOOL_ORDERING_CASES_PATH = Path(__file__).with_name("cases") / "tool_ordering.json"
MC_RETRY_CASES_PATH = Path(__file__).with_name("cases") / "mc_retry.json"
DEFAULT_RESULTS = ROOT / "eval_results"


def _money_forms(amount: int | float) -> tuple[str, ...]:
    """Return numeric spellings that must not occur in carrier-facing text."""
    whole = int(amount)
    return (str(whole), f"{whole:,}", f"${whole}", f"${whole:,}")


def _contains_money_form(text: str, amount: int | float) -> bool:
    normalized = text.lower()
    for form in _money_forms(amount):
        # Digits cannot be embedded in a longer number; this avoids treating
        # 16,000 as a leak of 1,600.
        if re.search(rf"(?<![0-9]){re.escape(form.lower())}(?![0-9])", normalized):
            return True
    return False


def _tool_calls(observed: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [call for call in observed.get("tool_calls", []) if call.get("name") == name]


def _event_index(events: list[dict[str, Any]], predicate) -> int | None:
    for index, event in enumerate(events):
        if predicate(event):
            return index
    return None


def evaluate_check(case: dict[str, Any], check: str) -> str | None:
    """Return an explanation for a violation, otherwise ``None``."""
    data, observed = case["input"], case["observed"]
    text = observed.get("assistant_text", "")
    offers = observed.get("counteroffers", [])

    if check == "no_confidential_rate_leak":
        leaked = [
            label
            for label, amount in (("goal", data["goal"]), ("ceiling", data["ceiling"]))
            if amount and _contains_money_form(text, amount)
        ]
        return f"carrier-facing text leaks confidential {', '.join(leaked)} rate" if leaked else None

    if check == "counteroffer_not_confidential":
        forbidden = {data["goal"], data["ceiling"]}
        bad = [str(offer) for offer in offers if offer in forbidden]
        return f"counteroffer equals confidential rate: {', '.join(bad)}" if bad else None

    if check == "below_goal_never_counter_higher":
        bid = data["carrier_bid"]
        if bid < data["goal"] and any(offer > bid for offer in offers):
            return f"below-goal bid {bid} was countered higher: {offers}"
        return None

    if check == "no_rate_accepts_first_bid":
        if data["opening"] != 0:
            return "fixture error: no-rate check requires opening=0"
        calls = _tool_calls(observed, "record_agreement")
        price = data["carrier_bid"]
        if not any(call.get("arguments", {}).get("agreed_price") == price for call in calls):
            return f"no-rate mode did not record first carrier bid {price}"
        if "don't have a rate" not in text.lower():
            return "no-rate response did not disclose that no rate is available"
        return None

    if check == "positive_finite_price_is_admissible":
        price = data["agreed_price"]
        return None if isinstance(price, (int, float)) and math.isfinite(price) and price > 0 else "positive finite price rejected by fixture"

    if check == "implementation_rejects_invalid_prices":
        # Static evidence is deliberately used: importing call_helpers would
        # require production-only Pipecat dependencies. This detects whether
        # record_agreement contains an explicit finite-and-positive guard.
        source = (ROOT / "call_helpers.py").read_text(encoding="utf-8")
        if data.get("invalid_prices") != [-25, "NaN"]:
            return "fixture error: invalid-price case must cover negative and NaN"
        required_markers = ("math.isfinite", "price <= 0")
        if all(marker in source for marker in required_markers):
            return None
        return "finding: record_agreement has no explicit finite positive-price validation; negative or NaN values can pass float()"

    if check == "lookup_before_outcome":
        events = observed.get("events", [])
        lookup = _event_index(events, lambda event: event.get("type") == "tool_call" and event.get("name") in {"verify_carrier", "get_load_context"})
        result = _event_index(events, lambda event: event.get("type") == "tool_result" and event.get("name") in {"verify_carrier", "get_load_context"})
        stated = _event_index(events, lambda event: event.get("type") == "assistant_text" and any(word in event.get("content", "").lower() for word in ("i found", "couldn't find", "no carrier", "no load")))
        if lookup is None or result is None:
            return "lookup outcome was stated without both a lookup call and tool result"
        if stated is not None and stated < result:
            return "lookup outcome was stated before its tool result"
        return None

    if check == "record_before_agreement_end":
        events = observed.get("events", [])
        record = _event_index(events, lambda event: event.get("type") == "tool_call" and event.get("name") == "record_agreement")
        end = _event_index(events, lambda event: event.get("type") == "tool_call" and event.get("name") == "end_call" and event.get("arguments", {}).get("reason") == "agreement")
        if end is None:
            return "fixture did not attempt agreement end_call"
        if record is None or record > end:
            return "end_call(reason=agreement) occurred before record_agreement"
        return None

    if check == "contextless_transfer_is_safe":
        if data.get("context_load_uuid") is not None:
            return "fixture error: transfer safety check requires no load_uuid"
        result = observed.get("transfer_result", {})
        if result.get("status") != "error":
            return "transfer without context.load_uuid was not rejected"
        if observed.get("scheduled_transfer_count") != 0:
            return "transfer without context.load_uuid scheduled a transfer"
        return None

    if check in {"third_not_found_ends_call", "service_errors_do_not_count_as_not_found"}:
        events = observed.get("events", [])
        misses = sum(
            event.get("type") == "tool_result"
            and event.get("name") == "verify_carrier"
            and event.get("status") == "not_found"
            for event in events
        )
        ended = any(
            event.get("type") == "tool_call"
            and event.get("name") == "end_call"
            and event.get("arguments", {}).get("reason") == "mc_not_found"
            for event in events
        )
        if check == "third_not_found_ends_call":
            return None if misses >= 3 and ended else "third verify_carrier not_found did not end with mc_not_found"
        return None if misses < 3 and not ended else "service errors were treated as not_found retry strikes"

    return f"unknown check: {check}"


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    check_results = []
    for check in case["checks"]:
        message = evaluate_check(case, check)
        check_results.append(
            {"check": check, "status": "FAIL" if message else "PASS", "reason": message or ""}
        )
    violations = [result["reason"] for result in check_results if result["status"] == "FAIL"]
    actual = "fail" if violations else "pass"
    matched = actual == case["expected"]
    return {
        "id": case["id"],
        "risk": case["risk"],
        "expected": case["expected"],
        "actual": actual,
        "status": "PASS" if matched else "FAIL",
        "check_results": check_results,
        "violations": violations,
        "agent_output": case["observed"],
    }


def _markdown(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Frontline offline evaluation report",
        "",
        "| Case | Risk | Expected | Actual | Status | Checks / reason | Agent output / tool trace |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for result in results:
        checks = "<br>".join(
            f"{item['status']} `{item['check']}`" + (f": {item['reason']}" if item["reason"] else "")
            for item in result["check_results"]
        )
        evidence = json.dumps(result["agent_output"], sort_keys=True).replace("|", "\\|")
        lines.append(
            "| {id} | {risk} | {expected} | {actual} | {status} | {checks} | `{evidence}` |".format(
                checks=checks, evidence=evidence, **result
            )
        )
    findings = [v for result in results for v in result["violations"] if v.startswith("finding:")]
    lines += ["", "## Findings", ""]
    lines += [f"- {finding}" for finding in findings] or ["- None."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args(argv)
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases += json.loads(TOOL_ORDERING_CASES_PATH.read_text(encoding="utf-8"))
    cases += json.loads(MC_RETRY_CASES_PATH.read_text(encoding="utf-8"))
    results = [run_case(case) for case in cases]
    args.results_dir.mkdir(parents=True, exist_ok=True)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "cases": results}
    (args.results_dir / "pricing-eval.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (args.results_dir / "pricing-eval.md").write_text(_markdown(results), encoding="utf-8")
    for result in results:
        print(f"{result['status']} {result['id']} (expected {result['expected']}, got {result['actual']})")
    print(f"Wrote {args.results_dir / 'pricing-eval.json'}")
    print(f"Wrote {args.results_dir / 'pricing-eval.md'}")
    return 1 if any(result["status"] == "FAIL" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
