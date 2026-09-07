"""LiveKit Room1/Room2 warm-transfer coordinator.

The negotiation pipeline and its LLM tools remain unchanged.  This module only
coordinates provider operations after the transfer tools are invoked.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from livekit_telephony_service import LiveKitTelephonyService
from models import TransferMessage
from number_strategy import RandomSelectionStrategy
from room2_pipeline_service import Room2PipelineService
from transfer_notifier import NotificationType, TransferNotifier
from transfer_state import TransferState


class TransferOrchestrator:
    """Brief a broker in Room2, then move that broker into Room1."""

    def __init__(self, telephony: LiveKitTelephonyService | None = None) -> None:
        self._state = TransferState()
        self._telephony = telephony or LiveKitTelephonyService()
        self._room1_task: Any | None = None
        self._room1_context: Any | None = None
        self._room1_context_aggregator: Any | None = None
        self._room2_pipeline: Room2PipelineService | None = None
        self._transfer_in_progress = False
        self._transfer_complete_event = asyncio.Event()
        self.number_selection_strategy = RandomSelectionStrategy()
        self.notifier = TransferNotifier(NotificationType.SLACK)
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
        if self._room1_context is not None:
            self._room1_context.end_reason = "call_transferred"

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
        call_id: str | None = None,
        room1_name: str | None = None,
    ) -> None:
        self._state.room1_url = room1_url
        self._state.room1_name = room1_name or context.room_name
        self._state.room1_token = room1_token
        self._room1_task = task
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
        """Move the bot to a briefing room and dial the configured broker."""

        del http_session
        self._mark_transfer_started()
        self._state.load_context = getattr(self._room1_context, "load_context", None)
        self._capture_room1_context()

        try:
            broker_number = self.number_selection_strategy.select(
                self._state.human_phone_number
            )
            if not broker_number:
                raise RuntimeError("No broker transfer number is configured")

            room = await self._telephony.create_room(
                purpose="broker-briefing",
                bot_identity="negotiation-agent-room2",
            )
            self._state.room2_url = self._telephony.config.livekit_url
            self._state.room2_name = room.name
            self._state.room2_token = room.token

            if self._room1_task is not None:
                await self._room1_task.cancel()

            self._room2_pipeline = Room2PipelineService(self._state, self)
            room2_future = await self._room2_pipeline.start(
                stt=stt,
                tts=tts,
                llm=llm,
                skip_tts_processor=skip_tts_processor,
                transcript=transcript,
                speech_sync=speech_sync,
                audiobuffer=audiobuffer,
                context_aggregator=context_aggregator,
            )

            await self.notifier.notify(
                TransferMessage(
                    load_number=self._state.load_number,
                    reason_of_transfer=self._state.transfer_reason,
                    price_asked_by_carrier=self._state.price_asked_by_carrier,
                    best_price_offered_by_bot=self._state.best_price_offered_by_bot,
                )
            )

            participant = await self._telephony.dial_phone(
                room_name=room.name,
                phone_number=broker_number,
                role="broker",
                display_name="Broker Line",
            )
            self._state.human_participant_identity = participant.identity
            self._state.human_participant_id = participant.participant_id
            self._state.human_session_id = participant.provider_call_id
            await room2_future
        except Exception:
            logger.exception("LiveKit broker transfer failed")
            await self._cleanup_room2()
            self._mark_transfer_complete()
            raise

    def _capture_room1_context(self) -> None:
        context = getattr(self._room1_context_aggregator, "_context", None)
        messages = getattr(context, "messages", None)
        self._state.room1_messages = list(messages or [])

    async def execute_transfer_human_to_room1(self, session_id: str | None) -> None:
        """Move the answered broker from Room2 into the waiting carrier room."""

        del session_id
        identity = self._state.human_participant_identity
        if not identity:
            raise RuntimeError("Broker participant identity is unavailable")
        if not self._state.room1_name or not self._state.room2_name:
            raise RuntimeError("Warm-transfer room state is incomplete")

        try:
            await self._telephony.move_participant(
                source_room=self._state.room2_name,
                destination_room=self._state.room1_name,
                participant_identity=identity,
            )
            if self._room2_pipeline is not None:
                await self._room2_pipeline.stop()
            await self._cleanup_room2()
        finally:
            self._mark_transfer_complete()

    async def _cleanup_room2(self) -> None:
        if self._state.room2_name:
            await self._telephony.delete_room(self._state.room2_name)
            self._state.room2_name = None
