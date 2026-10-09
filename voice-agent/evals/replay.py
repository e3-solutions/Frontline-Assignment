"""Small, dependency-free building blocks for offline call replays.

The replay intentionally uses the same initial-prompt builder as the bot while
keeping the context lightweight, as the handler tests do.  Tool handlers can
therefore mutate it exactly as they do during a call without starting a voice
pipeline or contacting external services.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import call_helpers
from call_helpers import get_load_context
from evals.checks import EvaluationResult
from load_context_utils import get_initial_system_prompt
from evals.safety import offline_guard


FAKE_LOAD = {
    "id": "00000000-0000-0000-0000-000000000123",
    "load_id": "REF-1234",
    "origin_city": "Atlanta", "origin_state": "GA",
    "destination_city": "Chicago", "destination_state": "IL",
    "pickup_time": "June 10 at 9 AM", "dropoff_time": "June 11 at 4 PM",
    "equipment": "Dry van", "commodity": "Paper goods",
    "special_instructions": "Driver must check in on arrival",
    "start_rate": 1800, "book_now_rate": 1950, "max_rate": 2100,
}


@dataclass(frozen=True)
class LookupReplayReport:
    successful_lookup: EvaluationResult
    invalid_reference: EvaluationResult
    missing_load: EvaluationResult


def build_greeting_context(org_name: str | None = None) -> SimpleNamespace:
    """Return an LLMContext-shaped object seeded with the production greeting.

    The fixed history represents a carrier who has been greeted, supplied an
    MC number, confirmed the returned carrier identity, and supplied a load
    reference.  It is deliberately plain data so tests can inspect prompt
    replacement directly.
    """
    greeting_prompt = get_initial_system_prompt(org_name=org_name)
    return SimpleNamespace(
        messages=[
            {"role": "system", "content": greeting_prompt},
            {
                "role": "assistant",
                "content": "Hi, this is Northstar Freight, can I get your MC number?",
            },
            {"role": "user", "content": "My MC is 123456."},
            {"role": "assistant", "content": "Is this Acme Trucking?"},
            {"role": "user", "content": "Yes. The reference is REF-1234."},
        ],
        org_id="00000000-0000-0000-0000-000000000001",
        call_id="00000000-0000-0000-0000-000000000099",
        caller_phone="+14155550100",
    )


async def run_lookup_replay_scenarios() -> LookupReplayReport:
    """Run every lookup handler scenario shared by pytest and the CLI report."""
    async def run_one(load_id: str, lookup_return):
        context = build_greeting_context(org_name="Northstar Freight")
        original_messages = context.messages.copy()
        results: list[dict] = []

        async def capture_result(payload, *, properties=None):
            results.append(json.loads(payload))

        lookup = MagicMock(return_value=lookup_return)
        update_call_load = MagicMock()
        with (
            offline_guard(),
            patch.dict(os.environ, {"HIGHWAY_PHONE_LOOKUP_ENABLED": "false"}),
            patch.object(call_helpers.NegotiationDBService, "get_load_by_reference", new=lookup),
            patch.object(call_helpers, "update_call_load", new=update_call_load),
        ):
            await get_load_context(
                "get_load_context", f"lookup-{load_id}", {"load_id": load_id},
                None, context, capture_result,
            )
        return context, original_messages, results[0], lookup, update_call_load

    success_context, success_history, success_result, success_lookup, success_update = await run_one("REF-1234", FAKE_LOAD)
    successful_lookup = EvaluationResult(
        passed=(
            success_lookup.call_args.args == ("REF-1234", success_context.org_id)
            and success_update.call_args.args == (success_context.call_id, FAKE_LOAD["id"])
            and success_result["status"] == "success"
            and success_context.messages[1:] == success_history[1:]
            and "We just found the load context for reference number: REF-1234." in success_context.messages[0]["content"]
        ),
        evidence=(
            f"Tool result: {success_result!r}.",
            f"Lookup arguments: {success_lookup.call_args.args!r}.",
            f"Call-record update: {success_update.call_args.args!r}.",
            "Greeting history preserved while the system prompt was replaced.",
        ),
    )
    invalid_context, invalid_messages, invalid_result, invalid_lookup, invalid_update = await run_one("Noted down", FAKE_LOAD)
    invalid_reference = EvaluationResult(
        passed=(
            invalid_result["status"] == "error"
            and not invalid_lookup.called and not invalid_update.called
            and invalid_context.messages == invalid_messages
        ),
        evidence=(f"Tool result: {invalid_result!r}.", "Lookup and call-record update were not called.", "Greeting and history were unchanged."),
    )
    missing_context, missing_messages, missing_result, missing_lookup, missing_update = await run_one("REF-9999", None)
    missing_load = EvaluationResult(
        passed=(
            missing_result == {"status": "error", "message": "No load found with ID: REF-9999"}
            and missing_lookup.call_args.args == ("REF-9999", missing_context.org_id)
            and not missing_update.called and missing_context.messages == missing_messages
        ),
        evidence=(f"Tool result: {missing_result!r}.", f"Lookup arguments: {missing_lookup.call_args.args!r}.", "No call-record update; greeting and history unchanged."),
    )
    return LookupReplayReport(successful_lookup, invalid_reference, missing_load)
