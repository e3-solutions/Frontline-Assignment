import asyncio
from types import SimpleNamespace

import pytest

import orchestrator as orchestrator_module
from livekit_telephony_service import (
    ParticipantMoveOutcomeUnknown,
    RoomCredentials,
    SipParticipant,
)
from transfer_state import TransferPhase


class FakeTelephony:
    def __init__(self, *, dial_error=None, move_error=None):
        self.config = SimpleNamespace(livekit_url="wss://test.livekit.cloud")
        self.calls = []
        self.dial_error = dial_error
        self.move_error = move_error

    async def create_room(self, **kwargs):
        self.calls.append(("create", kwargs))
        return RoomCredentials("briefing-room", "room-token")

    def issue_room_token(self, room_name, identity):
        self.calls.append(("token", room_name, identity))
        return "hold-token"

    async def dial_phone(self, **kwargs):
        self.calls.append(("dial", kwargs))
        if self.dial_error:
            raise self.dial_error
        return SipParticipant(kwargs["participant_identity"], "PA_1", "sip-1")

    async def move_participant_verified(self, **kwargs):
        self.calls.append(("move", kwargs))
        if self.move_error:
            raise self.move_error

    async def delete_room(self, room_name):
        self.calls.append(("delete", room_name))

    async def remove_participant(self, **kwargs):
        self.calls.append(("remove", kwargs))


class FakeMedia:
    def __init__(self, **kwargs):
        self.calls = []
        self.primary = kwargs["primary"]
        self.on_handoff_ended = kwargs["on_handoff_ended"]
        self.disconnect_on_arm = False
        self.departure_task = None

    async def start_hold(self):
        self.calls.append("start_hold")

    async def gate_primary_media(self, gated):
        self.calls.append(("gate", gated))

    async def stop_hold(self, *, retain_observer):
        self.calls.append(("stop_hold", retain_observer))
        if retain_observer and self.disconnect_on_arm:
            self.departure_task = asyncio.create_task(
                self.on_handoff_ended("PA_1")
            )
            await asyncio.sleep(0)

    async def restore_primary(self):
        self.calls.append("restore_primary")

    async def play_primary_announcement(self, text):
        self.calls.append(("announcement", text))

    async def detach_primary_publisher(self):
        self.calls.append("detach_primary")

    async def end_primary_pipeline(self):
        self.calls.append("end_primary")

    async def cleanup(self):
        self.calls.append("cleanup")

    async def quarantine_ambiguous_handoff(self):
        self.calls.append("quarantine_ambiguous")


class FakeRoom2:
    def __init__(self, state, orchestrator):
        self.state = state
        self.orchestrator = orchestrator
        self.calls = []

    async def start(self, **kwargs):
        self.calls.append("start")

    async def wait_for_broker(self, timeout):
        self.calls.append(("wait_for_broker", timeout))

    async def mark_broker_answered(self):
        self.calls.append("answered")

    async def stop(self):
        self.calls.append("stop")


class FakeNotifier:
    def __init__(self, error=None):
        self.error = error
        self.calls = 0

    async def notify(self, _message):
        self.calls += 1
        if self.error:
            raise self.error


def build_transfer(*, telephony=None, notifier=None):
    media_instances = []
    room2_instances = []

    def media_factory(**kwargs):
        instance = FakeMedia(**kwargs)
        media_instances.append(instance)
        return instance

    def room2_factory(state, orchestrator):
        instance = FakeRoom2(state, orchestrator)
        room2_instances.append(instance)
        return instance

    transfer = orchestrator_module.TransferOrchestrator(
        telephony=telephony or FakeTelephony(),
        media_factory=media_factory,
        room2_factory=room2_factory,
        notifier=notifier or FakeNotifier(),
    )
    context = SimpleNamespace(
        room_name="carrier-room",
        skip_tts=False,
        call_mode="BOT_ACTIVE",
        load_context={"maxRate": 2500},
    )
    aggregator = SimpleNamespace(
        _context=SimpleNamespace(messages=[{"role": "system", "content": "prompt"}])
    )
    transfer.set_room1_references(
        room1_url="wss://test.livekit.cloud",
        room1_token="room1-token",
        room1_name="carrier-room",
        task=SimpleNamespace(),
        context=context,
        context_aggregator=aggregator,
        transport=SimpleNamespace(),
    )
    transfer.set_transfer_metadata(
        reason="carrier requested a broker",
        human_phone_number="+14155550100",
    )
    transfer.state.carrier_participant_id = "PA_carrier"
    return transfer, context, media_instances, room2_instances


async def start_consultation(transfer):
    task = asyncio.create_task(
        transfer.execute_transfer_to_room2(
            http_session=None,
            stt=None,
            tts=None,
            llm=None,
            skip_tts_processor=None,
            transcript=None,
            speech_sync=None,
            audiobuffer=None,
            context_aggregator=None,
        )
    )
    for _ in range(20):
        if transfer.state.phase is TransferPhase.CONSULTING:
            return task
        await asyncio.sleep(0)
    raise AssertionError(f"consultation did not start: {transfer.state.phase}")


@pytest.mark.asyncio
async def test_success_holds_briefs_moves_verifies_then_marks_transferred():
    telephony = FakeTelephony()
    transfer, context, media_instances, room2_instances = build_transfer(
        telephony=telephony
    )
    consultation = await start_consultation(transfer)

    await transfer.execute_transfer_human_to_room1(None)
    await consultation

    assert transfer.state.phase is TransferPhase.HANDOFF_COMPLETE
    assert transfer.state.terminal_reason == "broker_arrived_in_primary_room"
    assert context.end_reason == "call_transferred"
    assert [call[0] for call in telephony.calls if call[0] in {"create", "dial", "move", "delete"}] == [
        "create",
        "dial",
        "move",
        "delete",
    ]
    assert media_instances[0].calls == [
        ("gate", True),
        "start_hold",
        ("stop_hold", True),
        "detach_primary",
    ]
    assert room2_instances[0].calls[-1] == "stop"
    assert transfer.is_transfer_in_progress() is False

    await transfer.on_handoff_ended("unrelated-participant")
    assert media_instances[0].calls[-1] == "detach_primary"
    await transfer.on_handoff_ended("PA_carrier")
    await transfer.on_handoff_ended("PA_carrier")
    assert media_instances[0].calls[-2:] == [
        ("stop_hold", False),
        "end_primary",
    ]
    assert telephony.calls[-2:] == [
        (
            "remove",
            {
                "room_name": "carrier-room",
                "participant_identity": transfer.state.human_participant_identity,
            },
        ),
        ("delete", "carrier-room"),
    ]


@pytest.mark.asyncio
async def test_dial_failure_restores_caller_and_does_not_mark_transferred():
    telephony = FakeTelephony(dial_error=RuntimeError("busy"))
    transfer, context, media_instances, room2_instances = build_transfer(
        telephony=telephony
    )

    await transfer.execute_transfer_to_room2(
        None, None, None, None, None, None, None, None, None
    )

    assert transfer.state.phase is TransferPhase.FAILED
    assert not hasattr(context, "end_reason")
    assert "restore_primary" in media_instances[0].calls
    assert any(call[0] == "announcement" for call in media_instances[0].calls)
    assert room2_instances[0].calls[-1] == "stop"
    assert ("delete", "briefing-room") in telephony.calls
    assert transfer.is_transfer_in_progress() is False


@pytest.mark.asyncio
async def test_retry_after_failed_dial_uses_fresh_room2_participant_state():
    telephony = FakeTelephony(dial_error=RuntimeError("busy"))
    transfer, context, _, _ = build_transfer(telephony=telephony)
    transfer.state.human_participant_id = "PA_stale"

    await transfer.execute_transfer_to_room2(
        None, None, None, None, None, None, None, None, None
    )
    telephony.dial_error = None
    retry = await start_consultation(transfer)
    await transfer.execute_transfer_human_to_room1(None)
    await retry

    assert transfer.state.phase is TransferPhase.HANDOFF_COMPLETE
    assert transfer.state.human_participant_id == "PA_1"
    assert context.end_reason == "call_transferred"


@pytest.mark.asyncio
async def test_move_failure_cleans_room2_and_restores_primary():
    telephony = FakeTelephony(move_error=RuntimeError("move rejected"))
    transfer, context, media_instances, _ = build_transfer(telephony=telephony)
    consultation = await start_consultation(transfer)

    await transfer.execute_transfer_human_to_room1(None)
    await consultation

    assert transfer.state.phase is TransferPhase.FAILED
    assert not hasattr(context, "end_reason")
    assert "restore_primary" in media_instances[0].calls
    assert ("delete", "briefing-room") in telephony.calls


@pytest.mark.asyncio
async def test_ambiguous_move_never_restores_bot_audio_into_room1():
    telephony = FakeTelephony(
        move_error=ParticipantMoveOutcomeUnknown("participant location unknown")
    )
    transfer, context, media_instances, _ = build_transfer(telephony=telephony)
    consultation = await start_consultation(transfer)

    await transfer.execute_transfer_human_to_room1(None)
    await consultation

    assert transfer.state.terminal_reason == "handoff_outcome_unknown"
    assert not hasattr(context, "end_reason")
    assert "quarantine_ambiguous" in media_instances[0].calls
    assert "restore_primary" not in media_instances[0].calls
    assert not any(call[0] == "announcement" for call in media_instances[0].calls)


@pytest.mark.asyncio
async def test_broker_departure_while_observer_is_armed_cannot_record_success():
    transfer, context, media_instances, _ = build_transfer()
    consultation = await start_consultation(transfer)
    media_instances[0].disconnect_on_arm = True

    await transfer.execute_transfer_human_to_room1(None)
    await consultation
    await media_instances[0].departure_task

    assert transfer.state.phase is TransferPhase.FAILED
    assert transfer.state.terminal_reason == "broker_disconnected_during_handoff"
    assert not hasattr(context, "end_reason")
    assert "restore_primary" in media_instances[0].calls


@pytest.mark.asyncio
async def test_broker_disconnect_terminalizes_attempt_without_hanging():
    transfer, _, media_instances, _ = build_transfer()
    consultation = await start_consultation(transfer)

    await transfer.on_broker_left_consultation()
    await asyncio.wait_for(consultation, timeout=0.1)

    assert transfer.state.terminal_reason == "broker_disconnected"
    assert "restore_primary" in media_instances[0].calls
    assert transfer.is_transfer_in_progress() is False


@pytest.mark.asyncio
async def test_carrier_disconnect_cleans_secondary_leg_without_restoring_room1():
    transfer, _, media_instances, _ = build_transfer()
    consultation = await start_consultation(transfer)

    await transfer.on_carrier_left_primary()
    await asyncio.wait_for(consultation, timeout=0.1)

    assert transfer.state.phase is TransferPhase.CANCELLED
    assert transfer.state.terminal_reason == "carrier_disconnected"
    assert "cleanup" in media_instances[0].calls
    assert "restore_primary" not in media_instances[0].calls


@pytest.mark.asyncio
async def test_consultation_deadline_restores_caller(monkeypatch):
    monkeypatch.setenv("LIVEKIT_TRANSFER_CONSULTATION_TIMEOUT_SECONDS", "0.001")
    transfer, _, media_instances, _ = build_transfer()

    await transfer.execute_transfer_to_room2(
        None, None, None, None, None, None, None, None, None
    )

    assert transfer.state.phase is TransferPhase.FAILED
    assert transfer.state.terminal_reason == "consultation_timeout"
    assert "restore_primary" in media_instances[0].calls


@pytest.mark.asyncio
async def test_duplicate_transfer_and_handoff_callbacks_have_one_external_effect():
    telephony = FakeTelephony()
    transfer, _, _, _ = build_transfer(telephony=telephony)
    consultation = await start_consultation(transfer)

    duplicate = asyncio.create_task(
        transfer.execute_transfer_to_room2(
            None, None, None, None, None, None, None, None, None
        )
    )
    await duplicate
    await asyncio.gather(
        transfer.execute_transfer_human_to_room1(None),
        transfer.execute_transfer_human_to_room1(None),
    )
    await consultation

    assert len([call for call in telephony.calls if call[0] == "create"]) == 1
    assert len([call for call in telephony.calls if call[0] == "dial"]) == 1
    assert len([call for call in telephony.calls if call[0] == "move"]) == 1


@pytest.mark.asyncio
async def test_notification_failure_is_not_on_the_telephony_critical_path():
    telephony = FakeTelephony()
    notifier = FakeNotifier(RuntimeError("slack unavailable"))
    transfer, _, _, _ = build_transfer(telephony=telephony, notifier=notifier)
    consultation = await start_consultation(transfer)

    assert any(call[0] == "dial" for call in telephony.calls)
    await transfer.on_broker_left_consultation()
    await consultation
