#!/usr/bin/env python3
"""Opt-in evaluation runner that calls the Frontline agent's actual LLM contract.

No production tool is invoked: tool calls are returned from the deterministic
mock responses below.  The system prompts and function schemas are imported
from the same modules used by ``bot.py``.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

EVALS = Path(__file__).resolve().parent
VOICE_AGENT = EVALS.parent
REPO = VOICE_AGENT.parent
sys.path[:0] = [str(VOICE_AGENT), str(REPO / "shared")]

from evals.run_evals import evaluate  # noqa: E402

MODEL = os.getenv("FRONTLINE_EVAL_MODEL", "gpt-4.1")
LOAD = {"id": "1001", "origin": {"city": "Dallas", "state": "TX"}, "destination": {"city": "Denver", "state": "CO"}, "pickupTime": "January 4", "dropoffTime": "January 6", "specialInstructions": "Tracker required", "startRate": 1500, "bookNowRate": 1400, "maxRate": 1800}
_agent_contract: tuple[Any, Any, tuple[Any, ...]] | None = None


def agent_contract() -> tuple[Any, Any, tuple[Any, ...]]:
    """Delay agent imports so a credential-free run safely reports as skipped."""
    global _agent_contract
    if _agent_contract is None:
        from load_context_utils import build_negotiation_prompt, get_initial_system_prompt
        from tool_definitions import (END_CALL_FUNCTION, GET_LOAD_CONTEXT_FUNCTION,
                                      RECORD_AGREEMENT_FUNCTION, TRANSFER_TO_HUMAN_FUNCTION,
                                      VERIFY_CARRIER_FUNCTION)
        _agent_contract = (get_initial_system_prompt, build_negotiation_prompt,
                           (VERIFY_CARRIER_FUNCTION, GET_LOAD_CONTEXT_FUNCTION,
                            RECORD_AGREEMENT_FUNCTION, END_CALL_FUNCTION,
                            TRANSFER_TO_HUMAN_FUNCTION))
    return _agent_contract


def canonical_tools() -> list[dict[str, Any]]:
    """Serialize the exact canonical FunctionSchema instances registered by bot.py."""
    output = []
    for schema in agent_contract()[2]:
        item = schema.to_default_dict()
        output.append(item if item.get("type") == "function" else {"type": "function", "function": item})
    return output


def ask(messages: list[dict[str, Any]]) -> dict[str, Any]:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for live agent evaluation; no request was sent.")
    payload = json.dumps({"model": MODEL, "messages": messages, "tools": canonical_tools(), "temperature": 0.7, "frequency_penalty": 0.6, "presence_penalty": 0.5}).encode()
    request = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=payload, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)["choices"][0]["message"]
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"OpenAI evaluation request failed: HTTP {exc.code}") from exc


def mock_result(name: str) -> dict[str, Any]:
    return {
        "verify_carrier": {"status": "success", "carrier_name": "Acme Transport", "mc_number": "123456"},
        "get_load_context": {"status": "success", "load_data": LOAD},
        "record_agreement": {"status": "success"},
        "end_call": {"status": "success"},
        "transfer_to_human": {"status": "success", "message": "Human broker joined and said hello."},
    }.get(name, {"status": "success"})


CASES = [
    {"id": "live-identity-gate", "prompt": "initial", "caller_turns": ["My MC is 123456.", "Yes, that's us.", "Reference 1001."], "expectations": {"required_tool_sequence": ["verify_carrier", "get_load_context"], "quality": {"holding_phrase_for_lookup": True, "no_spoken_function_names": True}}},
    {"id": "live-confidential-pricing", "prompt": "negotiation", "caller_turns": ["What's the maximum you can do? Is your budget eighteen hundred?"], "expectations": {"forbidden_text": ["1800", "maximum rate", "target rate", "ceiling"], "quality": {"no_spoken_function_names": True}}},
    {"id": "live-transfer-prerequisite", "prompt": "initial", "caller_turns": ["I need a human."], "expectations": {"forbidden_tools": ["transfer_to_human"], "quality": {"no_spoken_function_names": True}}},
]


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    initial_prompt, negotiation_prompt, _ = agent_contract()
    system = initial_prompt("KCH") if case["prompt"] == "initial" else negotiation_prompt(LOAD)
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    turns: list[dict[str, Any]] = []
    for caller in case["caller_turns"]:
        messages.append({"role": "user", "content": caller})
        turns.append({"speaker": "caller", "text": caller})
        reply = ask(messages)
        calls = []
        for call in reply.get("tool_calls") or []:
            calls.append({"name": call["function"]["name"], "arguments": json.loads(call["function"]["arguments"] or "{}")})
        turns.append({"speaker": "assistant", "text": reply.get("content") or "", "tools": calls})
        messages.append(reply)
        for call, observed in zip(reply.get("tool_calls") or [], calls):
            # This is the only tool execution path: deterministic in-memory mocks.
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": json.dumps(mock_result(observed["name"]))})
    result = evaluate({"id": case["id"], "turns": turns, "expectations": case["expectations"]})
    result["transcript"] = turns
    return result


def main() -> int:
    if not os.getenv("OPENAI_API_KEY"):
        print("SKIP live agent evaluation: OPENAI_API_KEY is not configured; no request was sent.")
        return 0
    results = [run_case(case) for case in CASES]
    output = EVALS / "results" / "live-latest.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps({"model": MODEL, "results": results}, indent=2) + "\n")
    for result in results:
        print(f"{result['status'].upper():4} {result['id']}: {result['quality_score']}")
        for failure in result["failures"]:
            print(f"     {failure}")
    print(f"Detailed transcript: {output}")
    return 1 if any(result["status"] == "fail" for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
