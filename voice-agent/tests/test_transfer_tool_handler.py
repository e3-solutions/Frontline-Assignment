"""Tests for transfer_tool_handler.py — load-reference guardrail."""

import json
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from transfer_tool_handler import TransferToolHandler


def _make_handler():
    """Create a TransferToolHandler with mocked dependencies."""
    orchestrator = MagicMock()
    handler = TransferToolHandler(
        orchestrator=orchestrator,
        http_session=MagicMock(),
        stt=MagicMock(),
        tts=MagicMock(),
        llm=MagicMock(),
        skip_tts_processor=MagicMock(),
        transcript=MagicMock(),
        speech_sync=MagicMock(),
        audiobuffer=MagicMock(),
        context_aggregator=MagicMock(),
    )
    return handler, orchestrator


def _make_context(load_uuid=None):
    """Create a minimal context object with optional load_uuid."""
    ctx = types.SimpleNamespace()
    if load_uuid is not None:
        ctx.load_uuid = load_uuid
    return ctx


def _make_load(
    *,
    transfer_call_to="(555) 123-4567",
    transfer_country_code="+1",
):
    return {
        "id": "aaaaaaaa-1111-2222-3333-444444444444",
        "load_id": "LOAD-001",
        "transfer_call_to": transfer_call_to,
        "transfer_country_code": transfer_country_code,
    }
 
@pytest.mark.asyncio
async def test_transfer_blocked_when_no_load_uuid():
    """Transfer should be rejected if context.load_uuid is not set."""
    handler, orchestrator = _make_handler()
    context = _make_context()  # no load_uuid
    result_callback = AsyncMock()

    await handler.handle_transfer_to_human(
        function_name="transfer_to_human",
        tool_call_id="call_1",
        args={"reason": "carrier asked", "load_number": "LOAD-999"},
        llm=MagicMock(),
        context=context,
        result_callback=result_callback,
    )

    result_callback.assert_awaited_once()
    result = json.loads(result_callback.call_args[0][0])
    assert result["status"] == "error"
    assert "load reference" in result["message"].lower()
    orchestrator.set_transfer_metadata.assert_not_called()


@pytest.mark.asyncio
async def test_transfer_blocked_when_load_uuid_is_none():
    """Transfer should be rejected if context.load_uuid is explicitly None."""
    handler, orchestrator = _make_handler()
    context = _make_context(load_uuid=None)
    context.load_uuid = None  # explicitly set
    result_callback = AsyncMock()

    await handler.handle_transfer_to_human(
        function_name="transfer_to_human",
        tool_call_id="call_2",
        args={"reason": "carrier asked", "load_number": "LOAD-999"},
        llm=MagicMock(),
        context=context,
        result_callback=result_callback,
    )

    result = json.loads(result_callback.call_args[0][0])
    assert result["status"] == "error"
    orchestrator.set_transfer_metadata.assert_not_called()


@pytest.mark.asyncio
@patch("transfer_tool_handler.NegotiationDBService.get_load")
async def test_transfer_proceeds_when_load_uuid_present(mock_get_load):
    """Transfer should proceed normally when context.load_uuid is set."""
    mock_get_load.return_value = _make_load()
    handler, orchestrator = _make_handler()
    context = _make_context(load_uuid="aaaaaaaa-1111-2222-3333-444444444444")
    result_callback = AsyncMock()
    handler._speech_sync.schedule_after_speech = AsyncMock()

    await handler.handle_transfer_to_human(
        function_name="transfer_to_human",
        tool_call_id="call_3",
        args={
            "reason": "carrier asked for human",
            "load_number": "LOAD-001",
            "price_asked_by_carrier": 2500,
            "best_price_offered_by_bot": 2200,
        },
        llm=MagicMock(),
        context=context,
        result_callback=result_callback,
    )

    result_callback.assert_awaited_once()
    result = json.loads(result_callback.call_args[0][0])
    assert result["status"] == "transferring"
    mock_get_load.assert_called_once_with("aaaaaaaa-1111-2222-3333-444444444444")
    orchestrator.set_transfer_metadata.assert_called_once_with(
        reason="carrier asked for human",
        load_number="LOAD-001",
        price_asked_by_carrier=2500,
        best_price_offered_by_bot=2200,
        human_phone_number="+15551234567",
    )
    handler._speech_sync.schedule_after_speech.assert_awaited_once()


@pytest.mark.asyncio
@patch("transfer_tool_handler.NegotiationDBService.get_load")
async def test_transfer_blocked_when_load_lookup_fails(mock_get_load):
    mock_get_load.return_value = None
    handler, orchestrator = _make_handler()
    context = _make_context(load_uuid="aaaaaaaa-1111-2222-3333-444444444444")
    result_callback = AsyncMock()
    handler._speech_sync.schedule_after_speech = AsyncMock()

    await handler.handle_transfer_to_human(
        function_name="transfer_to_human",
        tool_call_id="call_4",
        args={"reason": "carrier asked for human", "load_number": "LOAD-001"},
        llm=MagicMock(),
        context=context,
        result_callback=result_callback,
    )

    result = json.loads(result_callback.call_args[0][0])
    assert result["status"] == "error"
    assert "load could not be found" in result["message"].lower()
    orchestrator.set_transfer_metadata.assert_not_called()
    handler._speech_sync.schedule_after_speech.assert_not_called()


@pytest.mark.asyncio
@patch("transfer_tool_handler.NegotiationDBService.get_load")
async def test_transfer_blocked_when_load_has_no_transfer_number(mock_get_load):
    mock_get_load.return_value = _make_load(transfer_call_to=None)
    handler, orchestrator = _make_handler()
    context = _make_context(load_uuid="aaaaaaaa-1111-2222-3333-444444444444")
    result_callback = AsyncMock()
    handler._speech_sync.schedule_after_speech = AsyncMock()

    await handler.handle_transfer_to_human(
        function_name="transfer_to_human",
        tool_call_id="call_5",
        args={"reason": "carrier asked for human", "load_number": "LOAD-001"},
        llm=MagicMock(),
        context=context,
        result_callback=result_callback,
    )

    result = json.loads(result_callback.call_args[0][0])
    assert result["status"] == "error"
    assert "no broker transfer number" in result["message"].lower()
    orchestrator.set_transfer_metadata.assert_not_called()
    handler._speech_sync.schedule_after_speech.assert_not_called()


def _make_kch_load(*, carrier_sales_rep_phone="+12058752486"):
    """KCH `public.loads` row shape returned by NegotiationDBService.get_load."""
    return {
        "load_number": "KCH-1001",
        "id": "KCH-1001",
        "load_id": "KCH-1001",
        "carrier_sales_rep_phone": carrier_sales_rep_phone,
        # No transfer_country_code/transfer_call_to from KCH
    }


@pytest.mark.asyncio
@patch("transfer_tool_handler.NegotiationDBService.get_load")
async def test_transfer_uses_carrier_sales_rep_phone_when_present(mock_get_load):
    """Transfer should dial the E.164 stored on `public.loads.carrier_sales_rep_phone`."""
    mock_get_load.return_value = _make_kch_load()
    handler, orchestrator = _make_handler()
    context = _make_context(load_uuid="KCH-1001")
    result_callback = AsyncMock()
    handler._speech_sync.schedule_after_speech = AsyncMock()

    await handler.handle_transfer_to_human(
        function_name="transfer_to_human",
        tool_call_id="call_kch_1",
        args={"reason": "carrier asked for human", "load_number": "KCH-1001"},
        llm=MagicMock(),
        context=context,
        result_callback=result_callback,
    )

    result = json.loads(result_callback.call_args[0][0])
    assert result["status"] == "transferring"
    orchestrator.set_transfer_metadata.assert_called_once()
    kwargs = orchestrator.set_transfer_metadata.call_args.kwargs
    assert kwargs["human_phone_number"] == "+12058752486"


@pytest.mark.asyncio
@patch("transfer_tool_handler.NegotiationDBService.get_load")
async def test_transfer_blocked_when_carrier_sales_rep_phone_missing(mock_get_load):
    """Empty `carrier_sales_rep_phone` must block transfer with the missing-routing error."""
    mock_get_load.return_value = _make_kch_load(carrier_sales_rep_phone=None)
    handler, orchestrator = _make_handler()
    context = _make_context(load_uuid="KCH-1001")
    result_callback = AsyncMock()
    handler._speech_sync.schedule_after_speech = AsyncMock()

    await handler.handle_transfer_to_human(
        function_name="transfer_to_human",
        tool_call_id="call_kch_2",
        args={"reason": "carrier asked for human", "load_number": "KCH-1001"},
        llm=MagicMock(),
        context=context,
        result_callback=result_callback,
    )

    result = json.loads(result_callback.call_args[0][0])
    assert result["status"] == "error"
    assert "no broker transfer number" in result["message"].lower()
    orchestrator.set_transfer_metadata.assert_not_called()
    handler._speech_sync.schedule_after_speech.assert_not_called()
