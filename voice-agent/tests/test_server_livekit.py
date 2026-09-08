from fastapi.testclient import TestClient

from livekit_ingress import LiveKitSipEvent
from livekit_telephony_service import RoomCredentials, SipParticipant
from server import create_app
from telephony_config import LiveKitTelephonyConfig


def valid_config():
    return LiveKitTelephonyConfig(
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="key",
        livekit_api_secret="secret",
        livekit_inbound_trunk_id="ST_inbound",
        livekit_dispatch_rule_id="SDR_rule",
        livekit_outbound_trunk_id="ST_outbound",
        livekit_outbound_number="+14155550199",
        room_prefix="negotiation",
    )


class FakeWebhook:
    async def accept(self, **_kwargs):
        return LiveKitSipEvent(
            event_id="EV_1",
            room_name="inbound-room",
            participant_sid="PA_1",
            participant_identity="caller-1",
            sip_call_id="sip-1",
            telnyx_call_id="telnyx-1",
            trunk_id="ST_inbound",
            dispatch_rule_id="SDR_rule",
            called_number="+14155550199",
            caller_number="+14155550100",
        )


class FakeTelephony:
    def __init__(self):
        self.deleted = []

    def issue_room_token(self, room_name, identity):
        return f"token:{room_name}:{identity}"

    async def create_room(self, **_kwargs):
        return RoomCredentials("outbound-room", "outbound-token")

    async def dial_phone(self, **_kwargs):
        return SipParticipant("carrier-1", "PA_2", "telnyx-2")

    async def delete_room(self, room_name):
        self.deleted.append(room_name)


def test_verified_webhook_starts_bot_once():
    starts = []

    async def start(request, _session):
        starts.append(request)

    app = create_app(
        config=valid_config(),
        webhook_service=FakeWebhook(),
        telephony=FakeTelephony(),
        bot_starter=start,
    )
    with TestClient(app) as client:
        first = client.post(
            "/livekit-webhook", content=b"signed", headers={"Authorization": "token"}
        )
        duplicate = client.post(
            "/livekit-webhook", content=b"signed", headers={"Authorization": "token"}
        )

    assert first.status_code == 202
    assert duplicate.json()["status"] == "duplicate"
    assert len(starts) == 1
    assert starts[0].provider_call_id == "telnyx-1"


def test_outbound_call_creates_sip_participant_before_bot_start(monkeypatch):
    monkeypatch.setenv("OUTBOUND_CALL_API_KEY", "dial-test-key")
    starts = []

    async def start(request, _session):
        starts.append(request)

    app = create_app(
        config=valid_config(),
        webhook_service=FakeWebhook(),
        telephony=FakeTelephony(),
        bot_starter=start,
    )
    with TestClient(app) as client:
        response = client.post(
            "/outbound-call",
            json={"to_phone": "+1 (415) 555-0100", "from_phone": "+14155550199"},
            headers={"X-API-Key": "dial-test-key"},
        )

    assert response.status_code == 202
    assert response.json()["participant_identity"] == "carrier-1"
    assert starts[0].room_name == "outbound-room"
    assert starts[0].provider_call_id == "telnyx-2"
