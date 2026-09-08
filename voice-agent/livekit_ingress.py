"""Verified LiveKit webhook parsing for inbound Telnyx SIP calls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Protocol

from telephony_config import LiveKitTelephonyConfig, normalize_e164


MAX_LIVEKIT_WEBHOOK_BYTES = 256 * 1024


class LiveKitWebhookRejected(Exception):
    """A webhook that must not enter the application routing path."""

    def __init__(self, code: str, *, status_code: int) -> None:
        self.code = code
        self.status_code = status_code
        super().__init__(code)


class LiveKitWebhookVerifier(Protocol):
    """The small LiveKit SDK boundary used by ingress."""

    def receive(self, body: str, auth_token: str) -> Any: ...


@dataclass(frozen=True)
class LiveKitSipEvent:
    """Provider-neutral values accepted from a verified LiveKit SIP event."""

    event_id: str
    room_name: str
    participant_sid: str
    participant_identity: str
    sip_call_id: str
    telnyx_call_id: str
    trunk_id: str
    dispatch_rule_id: str
    called_number: str
    caller_number: str | None


class LiveKitWebhookService:
    """Verify the raw webhook body and extract the accepted SIP contract."""

    def __init__(
        self,
        config: LiveKitTelephonyConfig | None = None,
        *,
        runtime_config: LiveKitTelephonyConfig | None = None,
        verifier: LiveKitWebhookVerifier | None = None,
    ) -> None:
        if config is not None and runtime_config is not None:
            raise TypeError("pass config or runtime_config, not both")
        selected = config or runtime_config
        if selected is None:
            raise TypeError("LiveKit telephony config is required")
        self._config = selected.require_valid()
        self._verifier = verifier or _default_verifier(selected)

    async def accept(
        self,
        *,
        raw_body: bytes,
        authorization: str | None,
    ) -> LiveKitSipEvent:
        """Return one valid inbound SIP event after signature verification."""

        if not raw_body or len(raw_body) > MAX_LIVEKIT_WEBHOOK_BYTES:
            raise LiveKitWebhookRejected("INVALID_BODY", status_code=400)
        if not authorization or not authorization.strip():
            raise LiveKitWebhookRejected("INVALID_SIGNATURE", status_code=401)
        try:
            body_text = raw_body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LiveKitWebhookRejected("INVALID_BODY", status_code=400) from exc

        # WebhookReceiver authenticates the exact body bytes represented as UTF-8.
        # Do not deserialize or reformat the payload before this boundary.
        try:
            verified_event = self._verifier.receive(body_text, authorization)
            if asyncio.iscoroutine(verified_event):
                verified_event = await verified_event
        except Exception as exc:
            raise LiveKitWebhookRejected(
                "INVALID_SIGNATURE",
                status_code=401,
            ) from exc

        return parse_verified_sip_event(verified_event, self._config)


async def verify_livekit_webhook(
    *,
    raw_body: bytes,
    authorization: str | None,
    config: LiveKitTelephonyConfig,
    verifier: LiveKitWebhookVerifier | None = None,
) -> LiveKitSipEvent:
    """Functional entry point for frameworks that do not retain service state."""

    return await LiveKitWebhookService(config, verifier=verifier).accept(
        raw_body=raw_body,
        authorization=authorization,
    )


def parse_verified_sip_event(
    event: Any,
    config: LiveKitTelephonyConfig,
) -> LiveKitSipEvent:
    """Parse one already verified LiveKit ``participant_joined`` SIP event."""

    if _text(event, "event") != "participant_joined":
        raise LiveKitWebhookRejected("UNSUPPORTED_EVENT", status_code=202)

    participant = getattr(event, "participant", None)
    room = getattr(event, "room", None)
    if participant is None or room is None:
        raise LiveKitWebhookRejected("MALFORMED_EVENT", status_code=422)
    if not _participant_is_sip(participant):
        raise LiveKitWebhookRejected("NOT_SIP_PARTICIPANT", status_code=422)

    event_id = _text(event, "id")
    room_name = _text(room, "name")
    participant_sid = _text(participant, "sid")
    participant_identity = _text(participant, "identity")
    if not all((event_id, room_name, participant_sid, participant_identity)):
        raise LiveKitWebhookRejected("MISSING_EVENT_IDENTITY", status_code=422)

    raw_attributes = getattr(participant, "attributes", None)
    if not isinstance(raw_attributes, dict):
        try:
            raw_attributes = dict(raw_attributes or {})
        except (TypeError, ValueError) as exc:
            raise LiveKitWebhookRejected(
                "MALFORMED_SIP_ATTRIBUTES",
                status_code=422,
            ) from exc
    attributes = {
        str(key): str(value).strip()
        for key, value in raw_attributes.items()
        if value is not None
    }

    required_names = (
        "sip.callID",
        "sip.callIDFull",
        "sip.trunkID",
        "sip.ruleID",
        "sip.trunkPhoneNumber",
    )
    if any(not attributes.get(name) for name in required_names):
        raise LiveKitWebhookRejected("MISSING_SIP_ATTRIBUTES", status_code=422)

    trunk_id = attributes["sip.trunkID"]
    dispatch_rule_id = attributes["sip.ruleID"]
    if trunk_id != config.livekit_inbound_trunk_id:
        raise LiveKitWebhookRejected("TRUNK_MISMATCH", status_code=403)
    if dispatch_rule_id != config.livekit_dispatch_rule_id:
        raise LiveKitWebhookRejected("DISPATCH_RULE_MISMATCH", status_code=403)

    try:
        called_number = normalize_e164(attributes["sip.trunkPhoneNumber"])
        caller_number = normalize_e164(attributes.get("sip.phoneNumber"))
    except ValueError as exc:
        raise LiveKitWebhookRejected(
            "INVALID_PHONE_NUMBER",
            status_code=422,
        ) from exc
    if called_number is None:
        raise LiveKitWebhookRejected("INVALID_PHONE_NUMBER", status_code=422)

    return LiveKitSipEvent(
        event_id=event_id,
        room_name=room_name,
        participant_sid=participant_sid,
        participant_identity=participant_identity,
        sip_call_id=attributes["sip.callID"],
        telnyx_call_id=attributes["sip.callIDFull"],
        trunk_id=trunk_id,
        dispatch_rule_id=dispatch_rule_id,
        called_number=called_number,
        caller_number=caller_number,
    )


def _text(value: Any, attribute: str) -> str:
    return str(getattr(value, attribute, "") or "").strip()


def _participant_is_sip(participant: Any) -> bool:
    value = getattr(participant, "kind", None)
    name = str(getattr(value, "name", "") or value or "").upper()
    if name in {"SIP", "PARTICIPANT_KIND_SIP"} or name.endswith("_SIP"):
        return True
    try:
        from livekit.protocol.models_pb2 import ParticipantInfo

        return ParticipantInfo.Kind.Name(int(value)).upper().endswith("_SIP")
    except (ImportError, TypeError, ValueError):
        return False


def _default_verifier(
    config: LiveKitTelephonyConfig,
) -> LiveKitWebhookVerifier:
    """Build the production SDK verifier while keeping imports optional in tests."""

    from livekit import api

    return api.WebhookReceiver(
        api.TokenVerifier(
            config.livekit_api_key,
            config.livekit_api_secret,
        )
    )
