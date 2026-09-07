import pytest

from livekit_telephony_service import LiveKitTelephonyService, SipParticipant
from telephony_config import LiveKitTelephonyConfig


class FakeGateway:
    def __init__(self):
        self.calls = []

    async def create_room(self, room_name):
        self.calls.append(("create_room", room_name))

    async def delete_room(self, room_name):
        self.calls.append(("delete_room", room_name))

    async def create_sip_participant(self, **kwargs):
        self.calls.append(("dial", kwargs))
        return SipParticipant(kwargs["participant_identity"], "PA_1", "call-1")

    async def move_participant(self, **kwargs):
        self.calls.append(("move", kwargs))

    async def remove_participant(self, **kwargs):
        self.calls.append(("remove", kwargs))


@pytest.fixture
def config():
    return LiveKitTelephonyConfig(
        livekit_url="wss://example.livekit.cloud",
        livekit_api_key="key",
        livekit_api_secret="secret",
        livekit_inbound_trunk_id="ST_inbound",
        livekit_dispatch_rule_id="SDR_rule",
        livekit_outbound_trunk_id="ST_outbound",
        livekit_outbound_number="+14155550199",
        room_prefix="negotiation",
    )


@pytest.mark.asyncio
async def test_dial_phone_uses_configured_gateway(config):
    gateway = FakeGateway()
    service = LiveKitTelephonyService(config=config, gateway=gateway)

    participant = await service.dial_phone(
        room_name="room-one",
        phone_number="+14155550100",
        role="broker",
        display_name="Broker Line",
    )

    operation, payload = gateway.calls[0]
    assert operation == "dial"
    assert payload["room_name"] == "room-one"
    assert payload["phone_number"] == "+14155550100"
    assert payload["participant_identity"].startswith("broker-")
    assert participant.participant_id == "PA_1"


@pytest.mark.asyncio
async def test_move_participant_preserves_explicit_room_direction(config):
    gateway = FakeGateway()
    service = LiveKitTelephonyService(config=config, gateway=gateway)

    await service.move_participant(
        source_room="briefing-room",
        destination_room="carrier-room",
        participant_identity="broker-123",
    )

    assert gateway.calls == [
        (
            "move",
            {
                "source_room": "briefing-room",
                "destination_room": "carrier-room",
                "participant_identity": "broker-123",
            },
        )
    ]
