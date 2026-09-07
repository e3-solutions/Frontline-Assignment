from __future__ import annotations

from types import SimpleNamespace

import pytest

from livekit_ingress import (
    MAX_LIVEKIT_WEBHOOK_BYTES,
    LiveKitWebhookRejected,
    LiveKitWebhookService,
    parse_verified_sip_event,
    verify_livekit_webhook,
)
from telephony_config import load_livekit_telephony_config


def _config():
    return load_livekit_telephony_config(
        {
            "LIVEKIT_URL": "wss://candidate.livekit.cloud",
            "LIVEKIT_API_KEY": "api-key",
            "LIVEKIT_API_SECRET": "api-secret",
            "LIVEKIT_SIP_INBOUND_TRUNK_ID": "ST_inbound",
            "LIVEKIT_SIP_DISPATCH_RULE_ID": "SDR_inbound",
            "LIVEKIT_SIP_OUTBOUND_TRUNK_ID": "ST_outbound",
            "LIVEKIT_SIP_OUTBOUND_NUMBER": "+13125550199",
        }
    )


def _verified_event(
    *,
    event_type: str = "participant_joined",
    kind="SIP",
    attributes=None,
):
    if attributes is None:
        attributes = {
            "sip.callID": "LK-call-1",
            "sip.callIDFull": "telnyx-call-1",
            "sip.trunkID": "ST_inbound",
            "sip.ruleID": "SDR_inbound",
            "sip.trunkPhoneNumber": "+1 (312) 555-0100",
            "sip.phoneNumber": "0044 20 7946 0958",
        }
    return SimpleNamespace(
        id="EV_1",
        event=event_type,
        room=SimpleNamespace(name="candidate-room-1"),
        participant=SimpleNamespace(
            sid="PA_1",
            identity="sip-caller-1",
            kind=kind,
            attributes=attributes,
        ),
    )


class FakeVerifier:
    def __init__(self, *, event=None, error: Exception | None = None) -> None:
        self.event = _verified_event() if event is None else event
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def receive(self, body: str, authorization: str):
        self.calls.append((body, authorization))
        if self.error is not None:
            raise self.error
        return self.event


class AsyncFakeVerifier(FakeVerifier):
    async def receive(self, body: str, authorization: str):
        self.calls.append((body, authorization))
        return self.event


@pytest.mark.asyncio
async def test_service_verifies_exact_body_before_parsing_and_normalizes_numbers() -> (
    None
):
    verifier = FakeVerifier()
    service = LiveKitWebhookService(_config(), verifier=verifier)
    raw_body = b'{"event":"participant_joined", "room":{"name":"raw"}}'

    event = await service.accept(
        raw_body=raw_body,
        authorization="Bearer signed-token",
    )

    assert verifier.calls == [(raw_body.decode(), "Bearer signed-token")]
    assert event.event_id == "EV_1"
    assert event.room_name == "candidate-room-1"
    assert event.participant_sid == "PA_1"
    assert event.sip_call_id == "LK-call-1"
    assert event.telnyx_call_id == "telnyx-call-1"
    assert event.called_number == "+13125550100"
    assert event.caller_number == "+442079460958"


@pytest.mark.asyncio
async def test_functional_entry_point_supports_an_async_injected_verifier() -> None:
    verifier = AsyncFakeVerifier()

    event = await verify_livekit_webhook(
        raw_body=b"{}",
        authorization="Bearer signed-token",
        config=_config(),
        verifier=verifier,
    )

    assert event.participant_identity == "sip-caller-1"
    assert verifier.calls == [("{}", "Bearer signed-token")]


@pytest.mark.asyncio
async def test_invalid_signature_fails_closed() -> None:
    verifier = FakeVerifier(error=ValueError("bad signature"))
    service = LiveKitWebhookService(_config(), verifier=verifier)

    with pytest.raises(LiveKitWebhookRejected) as failure:
        await service.accept(raw_body=b"{}", authorization="Bearer invalid")

    assert failure.value.code == "INVALID_SIGNATURE"
    assert failure.value.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("raw_body", "authorization", "code", "status_code"),
    [
        (b"", "Bearer signed", "INVALID_BODY", 400),
        (b"{}", None, "INVALID_SIGNATURE", 401),
        (b"\xff", "Bearer signed", "INVALID_BODY", 400),
        (
            b"x" * (MAX_LIVEKIT_WEBHOOK_BYTES + 1),
            "Bearer signed",
            "INVALID_BODY",
            400,
        ),
    ],
    ids=("empty-body", "missing-authorization", "invalid-utf8", "oversized-body"),
)
async def test_request_envelope_is_rejected_before_verification(
    raw_body: bytes,
    authorization: str | None,
    code: str,
    status_code: int,
) -> None:
    verifier = FakeVerifier()
    service = LiveKitWebhookService(_config(), verifier=verifier)

    with pytest.raises(LiveKitWebhookRejected) as failure:
        await service.accept(raw_body=raw_body, authorization=authorization)

    assert (failure.value.code, failure.value.status_code) == (code, status_code)
    assert verifier.calls == []


@pytest.mark.parametrize(
    ("event", "code", "status_code"),
    [
        (_verified_event(event_type="room_finished"), "UNSUPPORTED_EVENT", 202),
        (_verified_event(kind="STANDARD"), "NOT_SIP_PARTICIPANT", 422),
        (
            _verified_event(attributes={"sip.callID": "LK-call-1"}),
            "MISSING_SIP_ATTRIBUTES",
            422,
        ),
    ],
)
def test_only_complete_participant_joined_sip_events_are_accepted(
    event,
    code: str,
    status_code: int,
) -> None:
    with pytest.raises(LiveKitWebhookRejected) as failure:
        parse_verified_sip_event(event, _config())

    assert (failure.value.code, failure.value.status_code) == (code, status_code)


@pytest.mark.parametrize(
    ("attribute", "value", "code"),
    [
        ("sip.trunkID", "ST_someone-else", "TRUNK_MISMATCH"),
        ("sip.ruleID", "SDR_someone-else", "DISPATCH_RULE_MISMATCH"),
    ],
)
def test_event_must_match_the_configured_ingress_route(
    attribute: str,
    value: str,
    code: str,
) -> None:
    event = _verified_event()
    event.participant.attributes[attribute] = value

    with pytest.raises(LiveKitWebhookRejected) as failure:
        parse_verified_sip_event(event, _config())

    assert failure.value.code == code
    assert failure.value.status_code == 403


@pytest.mark.parametrize(
    ("attribute", "value"),
    [
        ("sip.trunkPhoneNumber", "3125550100"),
        ("sip.phoneNumber", "anonymous"),
    ],
)
def test_invalid_sip_phone_attributes_are_rejected(
    attribute: str,
    value: str,
) -> None:
    event = _verified_event()
    event.participant.attributes[attribute] = value

    with pytest.raises(LiveKitWebhookRejected) as failure:
        parse_verified_sip_event(event, _config())

    assert failure.value.code == "INVALID_PHONE_NUMBER"
    assert failure.value.status_code == 422


def test_withheld_caller_number_is_allowed() -> None:
    event = _verified_event()
    event.participant.attributes.pop("sip.phoneNumber")

    parsed = parse_verified_sip_event(event, _config())

    assert parsed.caller_number is None


@pytest.mark.parametrize(
    ("target", "attribute"),
    [
        ("event", "id"),
        ("room", "name"),
        ("participant", "sid"),
        ("participant", "identity"),
    ],
)
def test_event_room_and_participant_identity_are_required(
    target: str,
    attribute: str,
) -> None:
    event = _verified_event()
    owner = event if target == "event" else getattr(event, target)
    setattr(owner, attribute, "")

    with pytest.raises(LiveKitWebhookRejected) as failure:
        parse_verified_sip_event(event, _config())

    assert failure.value.code == "MISSING_EVENT_IDENTITY"
    assert failure.value.status_code == 422
