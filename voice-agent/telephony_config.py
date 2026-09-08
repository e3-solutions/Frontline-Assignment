"""Configuration primitives for LiveKit SIP telephony.

Loading configuration is deliberately side-effect free: importing this module does
not read the process environment or import the LiveKit SDK.  Callers can inspect a
partially configured value for readiness endpoints and can explicitly require a
valid value before constructing provider clients.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from urllib.parse import urlparse


_E164_PATTERN = re.compile(r"^\+[1-9]\d{7,14}$")
_E164_FORMATTING = str.maketrans("", "", " -().")


class TelephonyConfigError(ValueError):
    """Raised when LiveKit telephony configuration is incomplete or invalid."""

    def __init__(self, errors: tuple[str, ...]) -> None:
        self.errors = errors
        super().__init__(", ".join(errors))


@dataclass(frozen=True)
class LiveKitTelephonyConfig:
    """Typed LiveKit and SIP identifiers needed by ingress and outbound calls."""

    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str = field(repr=False)
    livekit_inbound_trunk_id: str
    livekit_dispatch_rule_id: str
    livekit_outbound_trunk_id: str
    livekit_outbound_number: str = ""
    room_prefix: str = "negotiation"
    errors: tuple[str, ...] = ()

    provider: str = "livekit"
    carrier: str = "telnyx"

    @property
    def valid(self) -> bool:
        return not self.errors

    @property
    def readiness_reason(self) -> str | None:
        return self.errors[0] if self.errors else None

    @property
    def inbound_trunk_id(self) -> str:
        return self.livekit_inbound_trunk_id

    @property
    def dispatch_rule_id(self) -> str:
        return self.livekit_dispatch_rule_id

    @property
    def outbound_trunk_id(self) -> str:
        return self.livekit_outbound_trunk_id

    @property
    def livekit_sip_inbound_trunk_id(self) -> str:
        return self.livekit_inbound_trunk_id

    @property
    def livekit_sip_dispatch_rule_id(self) -> str:
        return self.livekit_dispatch_rule_id

    @property
    def livekit_sip_outbound_trunk_id(self) -> str:
        return self.livekit_outbound_trunk_id

    @property
    def livekit_sip_outbound_number(self) -> str:
        return self.livekit_outbound_number

    def require_valid(self) -> LiveKitTelephonyConfig:
        """Return this value or raise with every configuration error."""

        if self.errors:
            raise TelephonyConfigError(self.errors)
        return self


# This name keeps server integration familiar to the historical implementation.
LiveKitRuntimeConfig = LiveKitTelephonyConfig


def _value(environment: Mapping[str, str], name: str) -> str:
    return str(environment.get(name) or "").strip()


def load_livekit_telephony_config(
    environment: Mapping[str, str] | None = None,
) -> LiveKitTelephonyConfig:
    """Load configuration without raising for absent environment variables.

    The returned error codes are stable and suitable for readiness reporting.  A
    caller that is about to construct the LiveKit client should call
    :meth:`LiveKitTelephonyConfig.require_valid` first.
    """

    values = os.environ if environment is None else environment
    livekit_url = _value(values, "LIVEKIT_URL").rstrip("/")
    livekit_api_key = _value(values, "LIVEKIT_API_KEY")
    livekit_api_secret = _value(values, "LIVEKIT_API_SECRET")
    inbound_trunk_id = _value(values, "LIVEKIT_SIP_INBOUND_TRUNK_ID")
    dispatch_rule_id = _value(values, "LIVEKIT_SIP_DISPATCH_RULE_ID")
    outbound_trunk_id = _value(values, "LIVEKIT_SIP_OUTBOUND_TRUNK_ID")
    outbound_number_value = _value(values, "LIVEKIT_SIP_OUTBOUND_NUMBER")
    room_prefix = _value(values, "LIVEKIT_ROOM_PREFIX") or "negotiation"

    errors: list[str] = []
    parsed_url = urlparse(livekit_url)
    if not livekit_url:
        errors.append("livekit_url_missing")
    elif parsed_url.scheme not in {"ws", "wss"} or not parsed_url.hostname:
        errors.append("livekit_url_invalid")

    required = (
        (livekit_api_key, "livekit_api_key_missing"),
        (livekit_api_secret, "livekit_api_secret_missing"),
        (inbound_trunk_id, "livekit_sip_inbound_trunk_id_missing"),
        (dispatch_rule_id, "livekit_sip_dispatch_rule_id_missing"),
        (outbound_trunk_id, "livekit_sip_outbound_trunk_id_missing"),
    )
    errors.extend(code for value, code in required if not value)
    outbound_number = ""
    if not outbound_number_value:
        errors.append("livekit_sip_outbound_number_missing")
    else:
        try:
            outbound_number = normalize_e164(outbound_number_value) or ""
        except ValueError:
            errors.append("livekit_sip_outbound_number_invalid")

    return LiveKitTelephonyConfig(
        livekit_url=livekit_url,
        livekit_api_key=livekit_api_key,
        livekit_api_secret=livekit_api_secret,
        livekit_inbound_trunk_id=inbound_trunk_id,
        livekit_dispatch_rule_id=dispatch_rule_id,
        livekit_outbound_trunk_id=outbound_trunk_id,
        livekit_outbound_number=outbound_number,
        room_prefix=room_prefix,
        errors=tuple(errors),
    )


def load_livekit_runtime_config(
    service_kind: str = "ingress",
    environment: Mapping[str, str] | None = None,
) -> LiveKitRuntimeConfig:
    """Compatibility entry point for ingress/server code.

    The single-prompt application has one shared telephony contract.  ``service_kind``
    is accepted so a server can use the same call shape as the historical service,
    but it intentionally does not weaken validation for either process.
    """

    if service_kind not in {"ingress", "bot_runner"}:
        raise ValueError("service_kind must be 'ingress' or 'bot_runner'")
    return load_livekit_telephony_config(environment)


def validate_livekit_telephony_config(
    config: LiveKitTelephonyConfig,
) -> LiveKitTelephonyConfig:
    """Require a valid configuration and return it for convenient composition."""

    return config.require_valid()


def normalize_e164(value: str | None) -> str | None:
    """Normalize common visual formatting into a strict E.164 phone number.

    An international country code must be present, expressed either with ``+`` or
    the conventional ``00`` prefix.  Empty values are retained as ``None`` so a
    withheld caller number can be represented without inventing an identity.
    """

    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    candidate = candidate.translate(_E164_FORMATTING)
    if candidate.startswith("00"):
        candidate = f"+{candidate[2:]}"
    if not _E164_PATTERN.fullmatch(candidate):
        raise ValueError("phone number must be a valid E.164 value")
    return candidate
