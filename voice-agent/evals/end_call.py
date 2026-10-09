"""Shared offline probes for the production end_call handler."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from call_helpers import EndFrame, end_call
from evals.checks import EvaluationResult
from evals.safety import offline_guard


@dataclass(frozen=True)
class EndCallReport:
    valid_reason: EvaluationResult
    invalid_reason: EvaluationResult


async def run_end_call_scenarios() -> EndCallReport:
    """Exercise valid and invalid reasons without a pipeline or live call."""
    async def run_one(reason: str):
        context = SimpleNamespace()
        task = MagicMock()
        task.queue_frames = AsyncMock()
        results: list[dict] = []

        async def callback(payload, *, properties=None):
            results.append(json.loads(payload))

        await end_call("end_call", f"end-{reason}", {"reason": reason}, None, context, callback, task)
        return context, task, results[0]

    with offline_guard():
        valid_context, valid_task, valid_result = await run_one("agreement")
        invalid_context, invalid_task, invalid_result = await run_one("not_a_reason")

    valid_frames = valid_task.queue_frames.call_args.args[0] if valid_task.queue_frames.called else []
    valid = EvaluationResult(
        passed=(
            valid_result["status"] == "success"
            and valid_context.end_reason == "agreement"
            and len(valid_frames) == 1 and isinstance(valid_frames[0], EndFrame)
        ),
        evidence=(f"Tool result: {valid_result!r}.", f"Stored end_reason: {getattr(valid_context, 'end_reason', None)!r}.", f"Queued frames: {[type(frame).__name__ for frame in valid_frames]!r}."),
    )
    invalid = EvaluationResult(
        passed=(
            invalid_result["status"] == "error"
            and not hasattr(invalid_context, "end_reason")
            and not invalid_task.queue_frames.called
        ),
        evidence=(f"Tool result: {invalid_result!r}.", f"end_reason set: {hasattr(invalid_context, 'end_reason')}.", f"Frames queued: {invalid_task.queue_frames.called}."),
    )
    return EndCallReport(valid_reason=valid, invalid_reason=invalid)
