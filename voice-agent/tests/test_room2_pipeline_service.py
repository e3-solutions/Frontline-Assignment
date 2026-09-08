import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from room2_pipeline_service import Room2PipelineService
from transfer_state import TransferState


class FakeTransport:
    def __init__(self, identity="broker-expected"):
        self.handlers = {}
        participant = SimpleNamespace(identity=identity)
        self._client = SimpleNamespace(
            room=SimpleNamespace(remote_participants={"PA_broker": participant})
        )

    def event_handler(self, name):
        def register(handler):
            self.handlers[name] = handler
            return handler

        return register

    async def get_participant_metadata(self, _participant_id):
        return {}


def build_service():
    state = TransferState(human_participant_identity="broker-expected")
    orchestrator = SimpleNamespace(on_broker_left_consultation=AsyncMock())
    service = Room2PipelineService(state, orchestrator)
    service._transport = FakeTransport()
    service._context = SimpleNamespace(session_id=None)
    service._task = SimpleNamespace(
        queue_frames=AsyncMock(),
        cancel=AsyncMock(),
    )
    service._audiobuffer = SimpleNamespace(
        start_recording=AsyncMock(),
        stop_recording=AsyncMock(),
    )
    service._setup_room2_events()
    return service, state, orchestrator


@pytest.mark.asyncio
async def test_early_media_does_not_start_briefing_before_answer():
    service, _, _ = build_service()

    await service._transport.handlers["on_participant_connected"](
        service._transport, "PA_broker"
    )
    await service._transport.handlers["on_audio_track_subscribed"](
        service._transport, "PA_broker"
    )

    service._task.queue_frames.assert_not_awaited()
    service._audiobuffer.start_recording.assert_not_awaited()

    await service.mark_broker_answered()

    service._task.queue_frames.assert_awaited_once()
    service._audiobuffer.start_recording.assert_awaited_once()


@pytest.mark.asyncio
async def test_answer_before_media_starts_once_when_track_is_ready():
    service, _, _ = build_service()

    await service.mark_broker_answered()
    service._task.queue_frames.assert_not_awaited()
    await service._transport.handlers["on_audio_track_subscribed"](
        service._transport, "PA_broker"
    )
    await service._transport.handlers["on_audio_track_subscribed"](
        service._transport, "PA_broker"
    )

    service._task.queue_frames.assert_awaited_once()
    service._audiobuffer.start_recording.assert_awaited_once()


@pytest.mark.asyncio
async def test_unexpected_participant_never_satisfies_broker_readiness():
    service, state, _ = build_service()

    await service._transport.handlers["on_audio_track_subscribed"](
        service._transport, "PA_unexpected"
    )

    assert service._broker_connected.is_set() is False
    assert service._broker_media_ready.is_set() is False
    assert state.human_participant_id is None


@pytest.mark.asyncio
async def test_broker_disconnect_notifies_orchestrator():
    service, state, orchestrator = build_service()
    state.human_participant_id = "PA_broker"

    await service._transport.handlers["on_participant_disconnected"](
        service._transport, "PA_broker"
    )
    await asyncio.sleep(0)

    orchestrator.on_broker_left_consultation.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_flushes_recording_and_waits_for_runner():
    service, _, _ = build_service()
    service._recording_started = True
    service._run_future = asyncio.create_task(asyncio.sleep(0))

    await service.stop()

    service._audiobuffer.stop_recording.assert_awaited_once()
