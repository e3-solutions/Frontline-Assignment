"""LiveKit Room1/Room2 warm-transfer coordinator for the single-prompt agent."""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from contextlib import suppress
from typing import Any
from uuid import uuid4

from loguru import logger

from livekit_telephony_service import (
    LiveKitTelephonyService,
    ParticipantMoveOutcomeUnknown,
)
from livekit_transfer_media import LiveKitTransferMedia, PrimaryMediaBinding
from models import TransferMessage
from number_strategy import RandomSelectionStrategy
from room2_pipeline_service import Room2PipelineService
from transfer_notifier import NotificationType, TransferNotifier
from transfer_state import TransferPhase, TransferState


TRANSFER_UNAVAILABLE_MESSAGE = (
    "I could not connect the transfer. You are back with me and we can continue."
)


class BrokerMediaTimeout(TimeoutError):
    """The broker answered but never became usable in the consultation room."""


class TransferOrchestrator:
    """Hold the carrier, brief a broker, and hand the broker into Room1."""

    def __init__(
        self,
        telephony: LiveKitTelephonyService | None = None,
        *,
        media_factory: Callable[..., LiveKitTransferMedia] = LiveKitTransferMedia,
        room2_factory: Callable[..., Room2PipelineService] = Room2PipelineService,
        notifier: Any | None = None,
    ) -> None:
        self._state = TransferState()
        self._telephony = telephony or LiveKitTelephonyService()
        self._media_factory = media_factory
        self._room2_factory = room2_factory
        self._room1_task: Any | None = None
        self._room1_transport: Any | None = None
        self._room1_context: Any | None = None
        self._room1_context_aggregator: Any | None = None
        self._room2_pipeline: Room2PipelineService | None = None
        self._media: LiveKitTransferMedia | None = None
        self._transfer_in_progress = False
        self._transfer_complete_event = asyncio.Event()
        self._attempt_lock = asyncio.Lock()
        self._handoff_lock = asyncio.Lock()
        self._handoff_end_lock = asyncio.Lock()
        self._cleanup_lock = asyncio.Lock()
        self._handoff_ended = False
        self._handoff_departure = asyncio.Event()
        self._handoff_departed_participant_id: str | None = None
        self.number_selection_strategy = RandomSelectionStrategy()
        self.notifier = notifier or TransferNotifier(NotificationType.SLACK)
        self.call_id: str | None = None

    @property
    def state(self) -> TransferState:
        return self._state

    def set_state(self, state: TransferState) -> None:
        self._state = state

    def is_transfer_in_progress(self) -> bool:
        return self._transfer_in_progress

    async def wait_for_transfer_complete(self) -> None:
        if self._transfer_in_progress:
            await self._transfer_complete_event.wait()

    def _mark_transfer_started(self) -> None:
        self._transfer_in_progress = True
        self._transfer_complete_event.clear()
        self._handoff_ended = False
        self._handoff_departure.clear()
        self._handoff_departed_participant_id = None
        self._state.start()

    def _mark_transfer_complete(self) -> None:
        self._transfer_in_progress = False
        self._transfer_complete_event.set()

    def set_room1_references(
        self,
        room1_url: str,
        room1_token: str,
        task: Any,
        context: Any,
        context_aggregator: Any,
        transport: Any | None = None,
        call_id: str | None = None,
        room1_name: str | None = None,
    ) -> None:
        self._state.room1_url = room1_url
        self._state.room1_name = room1_name or context.room_name
        self._state.room1_token = room1_token
        self._room1_task = task
        self._room1_transport = transport
        self._room1_context = context
        self._room1_context_aggregator = context_aggregator
        self.call_id = call_id

    def set_transfer_metadata(
        self,
        reason: str,
        load_number: str | None = None,
        price_asked_by_carrier: float | None = None,
        best_price_offered_by_bot: float | None = None,
        human_phone_number: str | None = None,
    ) -> None:
        self._state.transfer_reason = reason
        self._state.load_number = load_number
        self._state.price_asked_by_carrier = price_asked_by_carrier
        self._state.best_price_offered_by_bot = best_price_offered_by_bot
        if human_phone_number:
            self._state.human_phone_number = human_phone_number

    async def execute_transfer_to_room2(
        self,
        http_session: Any,
        stt: Any,
        tts: Any,
        llm: Any,
        skip_tts_processor: Any,
        transcript: Any,
        speech_sync: Any,
        audiobuffer: Any,
        context_aggregator: Any,
    ) -> None:
        """Start one bounded consultation attempt and wait for its terminal result."""

        del http_session
        async with self._attempt_lock:
            if self._transfer_in_progress:
                logger.warning("Ignoring duplicate transfer request")
                return
            if self._state.room2_name or self._room2_pipeline is not None:
                await self._cleanup_room2()
                if self._state.room2_name or self._room2_pipeline is not None:
                    raise RuntimeError(
                        "Previous transfer resources could not be cleaned up"
                    )
            self._mark_transfer_started()

        try:
            broker_number = self.number_selection_strategy.select(
                self._state.human_phone_number
            )
            if not broker_number:
                raise RuntimeError("No broker transfer number is configured")
            if not self._state.room1_name or not self._state.room1_url:
                raise RuntimeError("Primary LiveKit room is unavailable")
            if self._room1_transport is None or self._room1_task is None:
                raise RuntimeError("Primary media is unavailable")

            self._state.load_context = getattr(self._room1_context, "load_context", None)
            self._capture_room1_context()

            room = await self._telephony.create_room(
                purpose="broker-briefing",
                bot_identity="negotiation-agent-room2",
            )
            self._state.room2_url = self._telephony.config.livekit_url
            self._state.room2_name = room.name
            self._state.room2_token = room.token

            hold_token = self._telephony.issue_room_token(
                self._state.room1_name,
                f"hold-observer-{self._state.attempt_id}",
            )
            self._media = self._media_factory(
                primary=PrimaryMediaBinding(
                    room_name=self._state.room1_name,
                    room_url=self._state.room1_url,
                    task=self._room1_task,
                    context=self._room1_context,
                    transport=self._room1_transport,
                ),
                hold_token=hold_token,
                hold_connect_timeout=_timeout(
                    "LIVEKIT_TRANSFER_HOLD_CONNECT_TIMEOUT_SECONDS", 10.0
                ),
                on_handoff_ended=self.on_handoff_ended,
            )
            await self._media.gate_primary_media(True)
            await self._media.start_hold()
            self._state.transition(TransferPhase.CALLER_ON_HOLD)

            expected_identity = f"broker-{uuid4().hex[:12]}"
            self._state.human_participant_identity = expected_identity
            self._room2_pipeline = self._room2_factory(self._state, self)
            await self._room2_pipeline.start(
                stt=stt,
                tts=tts,
                llm=llm,
                skip_tts_processor=skip_tts_processor,
                transcript=transcript,
                speech_sync=speech_sync,
                audiobuffer=audiobuffer,
                context_aggregator=context_aggregator,
            )

            await self._notify_best_effort()
            self._state.transition(TransferPhase.DIALING_BROKER)
            broker_timeout = _timeout("LIVEKIT_TRANSFER_BROKER_TIMEOUT_SECONDS", 45.0)
            loop = asyncio.get_running_loop()
            broker_deadline = loop.time() + broker_timeout
            participant = await asyncio.wait_for(
                self._telephony.dial_phone(
                    room_name=room.name,
                    phone_number=broker_number,
                    role="broker",
                    display_name="Broker Line",
                    participant_identity=expected_identity,
                ),
                timeout=broker_timeout,
            )
            self._state.human_participant_identity = participant.identity
            self._state.human_participant_id = participant.participant_id
            self._state.human_session_id = participant.provider_call_id
            await self._room2_pipeline.mark_broker_answered()
            remaining = broker_deadline - loop.time()
            if remaining <= 0:
                raise BrokerMediaTimeout("Broker answered after the consultation deadline")
            try:
                await self._room2_pipeline.wait_for_broker(remaining)
            except asyncio.TimeoutError as exc:
                raise BrokerMediaTimeout(
                    "Broker media did not become ready in Room2"
                ) from exc
            self._state.transition(TransferPhase.CONSULTING)

            try:
                await asyncio.wait_for(
                    self._transfer_complete_event.wait(),
                    timeout=_timeout(
                        "LIVEKIT_TRANSFER_CONSULTATION_TIMEOUT_SECONDS", 180.0
                    ),
                )
            except asyncio.TimeoutError:
                await self._terminal_failure("consultation_timeout")
        except asyncio.CancelledError:
            await self._terminal_failure("transfer_cancelled", cancelled=True)
            raise
        except Exception as exc:
            logger.exception("LiveKit broker transfer failed")
            await self._terminal_failure(_failure_reason(exc))

    def _capture_room1_context(self) -> None:
        context = getattr(self._room1_context_aggregator, "_context", None)
        messages = getattr(context, "messages", None)
        self._state.room1_messages = list(messages or [])

    async def execute_transfer_human_to_room1(self, session_id: str | None) -> None:
        """Move the answered broker into Room1 and verify their arrival."""

        del session_id
        async with self._handoff_lock:
            if self._state.phase is TransferPhase.HANDOFF_COMPLETE:
                return
            if self._state.phase is not TransferPhase.CONSULTING:
                raise RuntimeError(
                    f"Broker handoff is invalid during {self._state.phase.value}"
                )

            identity = self._state.human_participant_identity
            if not identity:
                raise RuntimeError("Broker participant identity is unavailable")
            if not self._state.room1_name or not self._state.room2_name:
                raise RuntimeError("Warm-transfer room state is incomplete")

            self._state.transition(TransferPhase.HANDOFF_REQUESTED)
            try:
                await self._telephony.move_participant_verified(
                    source_room=self._state.room2_name,
                    destination_room=self._state.room1_name,
                    participant_identity=identity,
                    timeout=_timeout(
                        "LIVEKIT_TRANSFER_ARRIVAL_TIMEOUT_SECONDS", 10.0
                    ),
                )
            except ParticipantMoveOutcomeUnknown as exc:
                logger.exception("LiveKit broker handoff outcome is unknown")
                await self._terminal_failure(
                    _failure_reason(exc),
                    restore_primary=False,
                    ambiguous_handoff=True,
                )
                return
            except Exception as exc:
                logger.exception("LiveKit broker handoff failed")
                await self._terminal_failure(_failure_reason(exc))
                return

            await self._complete_handoff(identity)

    async def on_broker_left_consultation(self) -> None:
        if self._state.phase in {
            TransferPhase.DIALING_BROKER,
            TransferPhase.CONSULTING,
        }:
            await self._terminal_failure("broker_disconnected")

    async def on_carrier_left_primary(self) -> None:
        """Terminate the secondary leg when the caller leaves during transfer."""

        if self._transfer_in_progress:
            await self._terminal_failure(
                "carrier_disconnected",
                cancelled=True,
                restore_primary=False,
            )

    async def on_handoff_ended(self, participant_id: str | None = None) -> None:
        """Release the observer and finalize after either human leaves."""

        if participant_id and participant_id not in {
            self._state.carrier_participant_id,
            self._state.human_participant_id,
        }:
            return
        if self._state.phase is TransferPhase.HANDOFF_REQUESTED:
            self._handoff_departed_participant_id = participant_id
            self._handoff_departure.set()
            await self._terminal_failure("broker_disconnected_during_handoff")
            return
        if self._state.phase is not TransferPhase.HANDOFF_COMPLETE:
            return
        async with self._handoff_end_lock:
            if self._handoff_ended:
                return
            self._handoff_ended = True
            async with self._cleanup_lock:
                await self._cleanup_room2()
                media = self._media
                identity = self._state.human_participant_identity
                room_name = self._state.room1_name
                if identity and room_name:
                    await self._retry_cleanup(
                        lambda: self._telephony.remove_participant(
                            room_name=room_name,
                            participant_identity=identity,
                        ),
                        "remove remaining broker",
                    )
                if room_name:
                    await self._retry_cleanup(
                        lambda: self._telephony.delete_room(room_name),
                        "delete completed primary room",
                    )
                if media is not None:
                    with suppress(Exception):
                        await media.stop_hold(retain_observer=False)
                    with suppress(Exception):
                        await media.end_primary_pipeline()

    async def _complete_handoff(self, identity: str) -> None:
        async with self._cleanup_lock:
            if not self._transfer_in_progress:
                await self._remove_late_broker(identity)
                return

            try:
                if self._media is None:
                    raise RuntimeError("Transfer media is unavailable")
                await self._media.stop_hold(retain_observer=True)
                await self._media.detach_primary_publisher()
            except Exception:
                logger.exception("Post-handoff media cleanup failed")
                await self._recover_after_arrived_broker(identity)
                return

            if self._handoff_departure.is_set():
                if (
                    self._handoff_departed_participant_id
                    == self._state.carrier_participant_id
                ):
                    await self._cleanup_after_carrier_departure(identity)
                else:
                    await self._recover_after_arrived_broker(
                        identity,
                        reason="broker_disconnected_during_handoff",
                    )
                return

            if self._room1_context is not None:
                self._room1_context.end_reason = "call_transferred"
            self._state.finish(
                TransferPhase.HANDOFF_COMPLETE,
                "broker_arrived_in_primary_room",
            )
            self._mark_transfer_complete()
            await self._cleanup_room2()

    async def _cleanup_after_carrier_departure(self, identity: str) -> None:
        if self._state.room1_name:
            await self._retry_cleanup(
                lambda: self._telephony.remove_participant(
                    room_name=self._state.room1_name,
                    participant_identity=identity,
                ),
                "remove broker after carrier departure",
            )
            await self._retry_cleanup(
                lambda: self._telephony.delete_room(self._state.room1_name),
                "delete primary room after carrier departure",
            )
        if self._media is not None:
            with suppress(Exception):
                await self._media.cleanup()
            with suppress(Exception):
                await self._media.end_primary_pipeline()
        self._state.finish(TransferPhase.CANCELLED, "carrier_disconnected_during_handoff")
        self._mark_transfer_complete()

    async def _recover_after_arrived_broker(
        self,
        identity: str,
        *,
        reason: str = "handoff_media_cleanup_failed",
    ) -> None:
        """Remove an arrived broker before restoring the single-prompt bot."""

        removed = False
        if self._state.room1_name:
            removed = await self._retry_cleanup(
                lambda: self._telephony.remove_participant(
                    room_name=self._state.room1_name,
                    participant_identity=identity,
                ),
                "remove broker after media cleanup failure",
            )

        if self._media is not None:
            if removed:
                with suppress(Exception):
                    await self._media.restore_primary()
                with suppress(Exception):
                    await self._media.play_primary_announcement(
                        TRANSFER_UNAVAILABLE_MESSAGE
                    )
            else:
                with suppress(Exception):
                    await self._media.quarantine_ambiguous_handoff()
        self._state.finish(TransferPhase.FAILED, reason)
        self._mark_transfer_complete()

    async def _remove_late_broker(self, identity: str) -> None:
        if not self._state.room1_name:
            return
        await self._retry_cleanup(
            lambda: self._telephony.remove_participant(
                room_name=self._state.room1_name,
                participant_identity=identity,
            ),
            "remove broker after losing the terminal race",
        )

    async def _terminal_failure(
        self,
        reason: str,
        *,
        cancelled: bool = False,
        restore_primary: bool = True,
        ambiguous_handoff: bool = False,
    ) -> None:
        """Elect one failure result, clean Room2, and restore the primary bot."""

        async with self._cleanup_lock:
            if not self._transfer_in_progress:
                return
            phase = TransferPhase.CANCELLED if cancelled else TransferPhase.FAILED
            self._state.finish(phase, reason)
            await self._cleanup_room2()
            if self._media is not None:
                if restore_primary:
                    with suppress(Exception):
                        await self._media.restore_primary()
                    if not cancelled:
                        with suppress(Exception):
                            await self._media.play_primary_announcement(
                                TRANSFER_UNAVAILABLE_MESSAGE
                            )
                elif ambiguous_handoff:
                    try:
                        await self._media.quarantine_ambiguous_handoff()
                    except Exception:
                        logger.exception("Ambiguous handoff quarantine failed")
                        with suppress(Exception):
                            await self._media.end_primary_pipeline()
                        if self._state.room1_name:
                            await self._retry_cleanup(
                                lambda: self._telephony.delete_room(
                                    self._state.room1_name
                                ),
                                "delete primary room after quarantine failure",
                            )
                else:
                    with suppress(Exception):
                        await self._media.cleanup()
            self._mark_transfer_complete()

    async def _cleanup_room2(self) -> None:
        pipeline = self._room2_pipeline
        if pipeline is not None:
            try:
                await pipeline.stop()
                self._room2_pipeline = None
            except Exception:
                logger.exception("Could not stop the Room2 pipeline")
        room_name = self._state.room2_name
        if room_name:
            deleted = await self._retry_cleanup(
                lambda: self._telephony.delete_room(room_name),
                "delete consultation room",
            )
            if deleted:
                self._state.room2_name = None

    async def _retry_cleanup(self, operation: Callable[[], Any], label: str) -> bool:
        for attempt in (1, 2):
            try:
                await operation()
                return True
            except Exception:
                logger.exception(f"Could not {label} (attempt {attempt}/2)")
                await asyncio.sleep(0)
        return False

    async def _notify_best_effort(self) -> None:
        try:
            await self.notifier.notify(
                TransferMessage(
                    load_number=self._state.load_number,
                    reason_of_transfer=self._state.transfer_reason,
                    price_asked_by_carrier=self._state.price_asked_by_carrier,
                    best_price_offered_by_bot=self._state.best_price_offered_by_bot,
                )
            )
        except Exception:
            logger.exception("Transfer notification failed; continuing with handoff")


def _timeout(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be numeric") from exc
    if value <= 0:
        raise RuntimeError(f"{name} must be greater than zero")
    return value


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, BrokerMediaTimeout):
        return "broker_media_timeout"
    if isinstance(exc, asyncio.TimeoutError):
        return "broker_answer_timeout"
    if isinstance(exc, ParticipantMoveOutcomeUnknown):
        return "handoff_outcome_unknown"
    return type(exc).__name__
