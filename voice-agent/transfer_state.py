"""Provider-neutral state for the LiveKit Room1/Room2 warm transfer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4


class TransferPhase(StrEnum):
    """Stable phases used by orchestration, logs, and the final call record."""

    IDLE = "idle"
    PREPARING = "preparing"
    CALLER_ON_HOLD = "caller_on_hold"
    DIALING_BROKER = "dialing_broker"
    CONSULTING = "consulting"
    HANDOFF_REQUESTED = "handoff_requested"
    HANDOFF_COMPLETE = "handoff_complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TransferState:
    """Room, participant, negotiation, and lifecycle state for one transfer."""

    # Room 1 (carrier room)
    room1_url: str | None = None
    room1_name: str | None = None
    room1_token: str | None = None
    carrier_participant_id: str | None = None
    carrier_participant_identity: str | None = None
    carrier_session_id: str | None = None

    # Room 2 (human room)
    room2_url: str | None = None
    room2_name: str | None = None
    room2_token: str | None = None
    human_participant_id: str | None = None
    human_participant_identity: str | None = None
    human_session_id: str | None = None

    # Provider-neutral call metadata
    provider_call_id: str | None = None
    telephony_provider: str | None = None

    # Phone numbers
    human_phone_number: str | None = None

    # Preserved context from Room1 and Room2
    room1_messages: list = field(default_factory=list)
    room2_transcript: list[dict[str, str]] = field(default_factory=list)
    room2_recording_url: str | None = None

    # Load context from Room1 (pricing and load details for Room2)
    load_context: dict | None = None

    # Transfer metadata
    transfer_reason: str | None = None
    load_number: str | None = None
    price_asked_by_carrier: float | None = None
    best_price_offered_by_bot: float | None = None

    # Provider-neutral lifecycle values safe to store in the final call result.
    attempt_id: str | None = None
    phase: TransferPhase = TransferPhase.IDLE
    terminal_reason: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

    def start(self) -> None:
        """Start a fresh attempt without discarding Room1 metadata."""

        self.attempt_id = str(uuid4())
        self.phase = TransferPhase.PREPARING
        self.terminal_reason = None
        self.started_at = _now()
        self.completed_at = None
        self.room2_transcript.clear()
        self.room2_recording_url = None
        self.room2_url = None
        self.room2_name = None
        self.room2_token = None
        self.human_participant_id = None
        self.human_participant_identity = None
        self.human_session_id = None

    def transition(self, phase: TransferPhase) -> None:
        self.phase = phase

    def finish(self, phase: TransferPhase, reason: str) -> None:
        if phase not in {
            TransferPhase.HANDOFF_COMPLETE,
            TransferPhase.FAILED,
            TransferPhase.CANCELLED,
        }:
            raise ValueError(f"{phase} is not terminal")
        self.phase = phase
        self.terminal_reason = reason
        self.completed_at = _now()

    def audit_snapshot(self) -> dict[str, object]:
        """Return the bounded transfer audit stored with the final call result."""

        return {
            "attempt_id": self.attempt_id,
            "phase": self.phase.value,
            "reason": self.terminal_reason,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "broker_participant_id": self.human_participant_id,
            "broker_provider_call_id": self.human_session_id,
            "consultation_transcript": list(self.room2_transcript),
            "consultation_recording_url": self.room2_recording_url,
            "cleanup_pending": self.room2_name is not None,
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
