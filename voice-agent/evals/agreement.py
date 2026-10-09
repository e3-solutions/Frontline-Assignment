"""Shared offline scenarios for agreement-recording safety and success paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import UUID

import call_helpers
from call_helpers import record_agreement
from evals.checks import EvaluationResult, check_above_max_recording
from evals.safety import offline_guard


MAX_RATE = 2100.0
ABOVE_MAX_PRICE = 2200.0
BELOW_CEILING_PRICE = 2000.0


@dataclass(frozen=True)
class AgreementScenarioReport:
    """Observed side effects and evaluations for mocked agreement tool calls."""

    normal_result: dict
    follow_up_result: dict
    normal_evaluation: EvaluationResult
    follow_up_evaluation: EvaluationResult
    follow_up_payload_evaluation: EvaluationResult
    below_ceiling_result: dict
    below_ceiling_evaluation: EvaluationResult
    save_failure_result: dict
    save_failure_evaluation: EvaluationResult
    normal_save_calls: tuple[tuple, ...]
    normal_quote_calls: tuple[dict[str, object], ...]
    follow_up_save_calls: tuple[tuple, ...]
    follow_up_quote_calls: tuple[dict[str, object], ...]
    below_ceiling_save_calls: tuple[tuple, ...]
    below_ceiling_quote_calls: tuple[dict[str, object], ...]
    save_failure_save_calls: tuple[tuple, ...]
    save_failure_quote_calls: tuple[dict[str, object], ...]


def _agreement_context() -> SimpleNamespace:
    return SimpleNamespace(
        load_uuid="00000000-0000-0000-0000-000000000123",
        load_context={"load_id": "REF-1234", "maxRate": MAX_RATE},
        caller_mc="123456",
        caller_phone="+14155550100",
        call_id="00000000-0000-0000-0000-000000000099",
    )


async def run_above_max_agreement_scenario() -> AgreementScenarioReport:
    """Run agreement paths without persistence or network access."""
    context = _agreement_context()
    async def run_one(tool_call_id, arguments, save_response):
        """Isolate each scenario's save/quote mocks from every other case."""
        results: list[dict] = []

        async def capture_result(payload, *, properties=None):
            results.append(json.loads(payload))

        save_agreement = MagicMock(return_value=save_response)
        notify_quote = MagicMock(return_value="quote-001")
        with (
            patch.object(call_helpers, "save_agreement", new=save_agreement),
            patch.object(
                call_helpers.NegotiationDBService,
                "notify_carrier_quote",
                new=notify_quote,
            ),
        ):
            await record_agreement(
                "record_agreement", tool_call_id, arguments, None, context, capture_result
            )
        return (
            results[0],
            tuple(call.args for call in save_agreement.call_args_list),
            tuple(dict(call.kwargs) for call in notify_quote.call_args_list),
        )

    with offline_guard():
        normal_result, normal_save_calls, normal_quote_calls = await run_one(
            "normal-above-max",
            {"agreed_price": ABOVE_MAX_PRICE, "above_max": False},
            UUID("00000000-0000-0000-0000-000000000201"),
        )
        follow_up_result, follow_up_save_calls, follow_up_quote_calls = await run_one(
            "follow-up-above-max",
            {"agreed_price": ABOVE_MAX_PRICE, "above_max": True,
             "carrier_contact_name": "Casey Carrier", "carrier_contact_phone": "+14155550101"},
            UUID("00000000-0000-0000-0000-000000000202"),
        )
        below_ceiling_result, below_ceiling_save_calls, below_ceiling_quote_calls = await run_one(
            "below-ceiling",
            {"agreed_price": BELOW_CEILING_PRICE, "above_max": False,
             "carrier_contact_name": "Jordan Carrier", "carrier_contact_phone": "+14155550102"},
            UUID("00000000-0000-0000-0000-000000000203"),
        )
        save_failure_result, save_failure_save_calls, save_failure_quote_calls = await run_one(
            "save-failure",
            {"agreed_price": BELOW_CEILING_PRICE, "above_max": False},
            None,
        )

    normal_evaluation = check_above_max_recording(
        max_rate=MAX_RATE, agreed_price=ABOVE_MAX_PRICE, above_max=False,
        database_recorded=bool(normal_save_calls), quote_sent=bool(normal_quote_calls),
    )
    follow_up_evaluation = check_above_max_recording(
        max_rate=MAX_RATE, agreed_price=ABOVE_MAX_PRICE, above_max=True,
        database_recorded=bool(follow_up_save_calls), quote_sent=bool(follow_up_quote_calls),
    )
    expected_follow_up_save = (context.load_uuid, ABOVE_MAX_PRICE, context.call_id, True, "Casey Carrier", "+14155550101")
    follow_up_payload_evaluation = EvaluationResult(
        passed=(follow_up_save_calls == (expected_follow_up_save,) and not follow_up_quote_calls and follow_up_result["status"] == "success"),
        evidence=(f"Expected follow-up save call: {expected_follow_up_save!r}.", f"Observed follow-up save calls: {follow_up_save_calls!r}.", f"Observed follow-up quote calls: {follow_up_quote_calls!r}.", f"Handler result: {follow_up_result['status']}."),
    )
    expected_below_ceiling_save = (context.load_uuid, BELOW_CEILING_PRICE, context.call_id, False, "Jordan Carrier", "+14155550102")
    expected_below_ceiling_quote = {"load_name": "REF-1234", "agreed_price": BELOW_CEILING_PRICE, "mc_number": context.caller_mc, "source_type": "call", "carrier_name": "Jordan Carrier", "carrier_phone": "+14155550102"}
    below_ceiling_evaluation = EvaluationResult(
        passed=(below_ceiling_save_calls == (expected_below_ceiling_save,) and below_ceiling_quote_calls == (expected_below_ceiling_quote,) and below_ceiling_result["status"] == "success"),
        evidence=(f"Expected below-ceiling save call: {expected_below_ceiling_save!r}.", f"Observed below-ceiling save calls: {below_ceiling_save_calls!r}.", f"Expected quote payload: {expected_below_ceiling_quote!r}.", f"Observed quote calls: {below_ceiling_quote_calls!r}.", f"Handler result: {below_ceiling_result['status']}."),
    )
    save_failure_evaluation = EvaluationResult(
        passed=(bool(save_failure_save_calls) and not save_failure_quote_calls and save_failure_result == {"status": "error", "message": "Failed to record in database"}),
        evidence=(f"Save attempts: {save_failure_save_calls!r}.", f"Quote-notification calls: {save_failure_quote_calls!r}.", f"Handler result: {save_failure_result!r}.", "This scenario owns its None-returning save mock, independent of the normal above-max scenario."),
    )

    return AgreementScenarioReport(
        normal_result=normal_result,
        follow_up_result=follow_up_result,
        normal_evaluation=normal_evaluation,
        follow_up_evaluation=follow_up_evaluation,
        follow_up_payload_evaluation=follow_up_payload_evaluation,
        below_ceiling_result=below_ceiling_result,
        below_ceiling_evaluation=below_ceiling_evaluation,
        save_failure_result=save_failure_result,
        save_failure_evaluation=save_failure_evaluation,
        normal_save_calls=normal_save_calls,
        normal_quote_calls=normal_quote_calls,
        follow_up_save_calls=follow_up_save_calls,
        follow_up_quote_calls=follow_up_quote_calls,
        below_ceiling_save_calls=below_ceiling_save_calls,
        below_ceiling_quote_calls=below_ceiling_quote_calls,
        save_failure_save_calls=save_failure_save_calls,
        save_failure_quote_calls=save_failure_quote_calls,
    )
