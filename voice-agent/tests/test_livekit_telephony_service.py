import pytest

from livekit_telephony_service import (
    LiveKitTelephonyService,
    ParticipantMoveOutcomeUnknown,
    SipParticipant,
)
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

    async def participant_exists(self, **kwargs):
        self.calls.append(("exists", kwargs))
        return False


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


class ReconcilingGateway(FakeGateway):
    def __init__(self, *, first_move_error=False, ambiguous=False):
        super().__init__()
        self.first_move_error = first_move_error
        self.ambiguous = ambiguous
        self.move_count = 0
        self.location = "briefing-room"

    async def move_participant(self, **kwargs):
        self.calls.append(("move", kwargs))
        self.move_count += 1
        if self.first_move_error and self.move_count == 1:
            if self.ambiguous:
                self.location = None
            raise RuntimeError("provider rejected move")
        self.location = kwargs["destination_room"]

    async def participant_exists(self, **kwargs):
        self.calls.append(("exists", kwargs))
        return kwargs["room_name"] == self.location


@pytest.mark.asyncio
async def test_verified_move_retries_only_when_broker_is_still_in_source(config):
    gateway = ReconcilingGateway(first_move_error=True)
    service = LiveKitTelephonyService(config=config, gateway=gateway)

    await service.move_participant_verified(
        source_room="briefing-room",
        destination_room="carrier-room",
        participant_identity="broker-123",
        timeout=0.02,
    )

    assert gateway.move_count == 2
    assert gateway.location == "carrier-room"


@pytest.mark.asyncio
async def test_verified_move_never_retries_an_ambiguous_outcome(config):
    gateway = ReconcilingGateway(first_move_error=True, ambiguous=True)
    service = LiveKitTelephonyService(config=config, gateway=gateway)

    with pytest.raises(ParticipantMoveOutcomeUnknown):
        await service.move_participant_verified(
            source_room="briefing-room",
            destination_room="carrier-room",
            participant_identity="broker-123",
            timeout=0.02,
        )

    assert gateway.move_count == 1
