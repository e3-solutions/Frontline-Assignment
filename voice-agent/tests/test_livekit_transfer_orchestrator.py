from types import SimpleNamespace

import pytest

import orchestrator as orchestrator_module
from livekit_telephony_service import RoomCredentials, SipParticipant


class FakeTelephony:
    def __init__(self):
        self.config = SimpleNamespace(livekit_url="wss://test.livekit.cloud")
        self.calls = []

    async def create_room(self, **kwargs):
        self.calls.append(("create", kwargs))
        return RoomCredentials("briefing-room", "room-token")

    async def dial_phone(self, **kwargs):
        self.calls.append(("dial", kwargs))
        return SipParticipant("broker-1", "PA_1", "sip-1")

    async def move_participant(self, **kwargs):
        self.calls.append(("move", kwargs))

    async def delete_room(self, room_name):
        self.calls.append(("delete", room_name))


@pytest.mark.asyncio
async def test_human_is_moved_from_briefing_room_to_carrier_room():
    telephony = FakeTelephony()
    transfer = orchestrator_module.TransferOrchestrator(telephony=telephony)
    transfer.state.room1_name = "carrier-room"
    transfer.state.room2_name = "briefing-room"
    transfer.state.human_participant_identity = "broker-1"
    transfer._mark_transfer_started()

    await transfer.execute_transfer_human_to_room1(None)

    assert telephony.calls == [
        (
            "move",
            {
                "source_room": "briefing-room",
                "destination_room": "carrier-room",
                "participant_identity": "broker-1",
            },
        ),
        ("delete", "briefing-room"),
    ]
    assert transfer.is_transfer_in_progress() is False
