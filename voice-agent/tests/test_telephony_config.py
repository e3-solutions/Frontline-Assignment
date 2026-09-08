from __future__ import annotations

import pytest

from telephony_config import (
    TelephonyConfigError,
    load_livekit_runtime_config,
    load_livekit_telephony_config,
    normalize_e164,
    validate_livekit_telephony_config,
)


def _valid_environment() -> dict[str, str]:
    return {
        "LIVEKIT_URL": "wss://candidate.livekit.cloud/",
        "LIVEKIT_API_KEY": "api-key",
        "LIVEKIT_API_SECRET": "api-secret",
        "LIVEKIT_SIP_INBOUND_TRUNK_ID": "ST_inbound",
        "LIVEKIT_SIP_DISPATCH_RULE_ID": "SDR_inbound",
        "LIVEKIT_SIP_OUTBOUND_TRUNK_ID": "ST_outbound",
        "LIVEKIT_SIP_OUTBOUND_NUMBER": "+1 (312) 555-0199",
    }


def test_missing_environment_is_loaded_without_import_or_startup_failure() -> None:
    config = load_livekit_telephony_config({})

    assert config.valid is False
    assert config.readiness_reason == "livekit_url_missing"
    assert config.errors == (
        "livekit_url_missing",
        "livekit_api_key_missing",
        "livekit_api_secret_missing",
        "livekit_sip_inbound_trunk_id_missing",
        "livekit_sip_dispatch_rule_id_missing",
        "livekit_sip_outbound_trunk_id_missing",
        "livekit_sip_outbound_number_missing",
    )


def test_valid_configuration_is_typed_normalized_and_provider_specific() -> None:
    values = _valid_environment()
    values["LIVEKIT_API_KEY"] = "  api-key  "

    config = load_livekit_telephony_config(values)

    assert config.valid is True
    assert config.provider == "livekit"
    assert config.carrier == "telnyx"
    assert config.livekit_url == "wss://candidate.livekit.cloud"
    assert config.livekit_api_key == "api-key"
    assert config.inbound_trunk_id == "ST_inbound"
    assert config.dispatch_rule_id == "SDR_inbound"
    assert config.outbound_trunk_id == "ST_outbound"
    assert config.livekit_outbound_number == "+13125550199"


@pytest.mark.parametrize(
    "livekit_url",
    [
        "candidate.livekit.cloud",
        "https://candidate.livekit.cloud",
        "wss:///missing-host",
    ],
)
def test_livekit_url_must_be_a_websocket_origin(livekit_url: str) -> None:
    values = _valid_environment()
    values["LIVEKIT_URL"] = livekit_url

    config = load_livekit_telephony_config(values)

    assert config.errors == ("livekit_url_invalid",)


def test_explicit_validation_reports_all_missing_values() -> None:
    config = load_livekit_telephony_config({})

    with pytest.raises(TelephonyConfigError) as failure:
        validate_livekit_telephony_config(config)

    assert failure.value.errors == config.errors


def test_runtime_compatibility_loader_does_not_weaken_validation() -> None:
    values = _valid_environment()
    values.pop("LIVEKIT_SIP_OUTBOUND_TRUNK_ID")

    config = load_livekit_runtime_config("ingress", values)

    assert config.errors == ("livekit_sip_outbound_trunk_id_missing",)


@pytest.mark.parametrize(
    ("outbound_number", "expected_error"),
    [
        ("", "livekit_sip_outbound_number_missing"),
        ("3125550199", "livekit_sip_outbound_number_invalid"),
        ("anonymous", "livekit_sip_outbound_number_invalid"),
    ],
)
def test_outbound_caller_id_is_required_and_must_be_e164(
    outbound_number: str,
    expected_error: str,
) -> None:
    values = _valid_environment()
    values["LIVEKIT_SIP_OUTBOUND_NUMBER"] = outbound_number

    config = load_livekit_telephony_config(values)

    assert config.errors == (expected_error,)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+1 (312) 555-0100", "+13125550100"),
        ("0044 20 7946 0958", "+442079460958"),
        (" +919876543210 ", "+919876543210"),
        (None, None),
        ("", None),
    ],
)
def test_normalize_e164(raw: str | None, expected: str | None) -> None:
    assert normalize_e164(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "3125550100",
        "+012345678",
        "+1234567",
        "+1234567890123456",
        "+1-800-FLOWERS",
    ],
)
def test_normalize_e164_rejects_ambiguous_or_invalid_numbers(raw: str) -> None:
    with pytest.raises(ValueError, match=r"E\.164"):
        normalize_e164(raw)
