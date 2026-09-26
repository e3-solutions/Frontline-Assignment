import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from call_helpers import end_call, record_agreement


def context(**overrides):
    values = {
        "load_uuid": "LOAD-UUID",
        "call_id": uuid4(),
        "caller_mc": "123456",
        "caller_phone": "+15550100",
        "load_context": {"load_id": "LOAD-1234", "maxRate": 1800},
        "call_mode": "BOT_ACTIVE",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


async def invoke_record(ctx, **arguments):
    callback = AsyncMock()
    await record_agreement("record_agreement", "tool-1", arguments, None, ctx, callback)
    return json.loads(callback.call_args.args[0])


@pytest.mark.asyncio
@patch("call_helpers.save_agreement")
@patch("call_helpers.NegotiationDBService.notify_carrier_quote")
async def test_above_ceiling_ordinary_agreement_is_blocked(notify, save):
    result = await invoke_record(context(), agreed_price=2200, above_max=False)
    assert result["code"] == "PRICE_ABOVE_CEILING"
    save.assert_not_called()
    notify.assert_not_called()


@pytest.mark.asyncio
@patch("call_helpers.save_agreement", return_value=uuid4())
@patch("call_helpers.NegotiationDBService.notify_carrier_quote")
async def test_above_max_bid_is_stored_without_accepted_quote(notify, save):
    ctx = context()
    result = await invoke_record(
        ctx,
        agreed_price=2200,
        above_max=True,
        carrier_contact_name="Sam Jones",
        carrier_contact_phone="555-0100",
    )
    assert result["status"] == "success"
    assert ctx.above_max_bid_recorded is True
    assert "no agreement" in result["message"].lower()
    save.assert_called_once()
    notify.assert_not_called()


@pytest.mark.asyncio
@patch("call_helpers.save_agreement")
async def test_in_range_bid_cannot_be_mislabeled_above_max(save):
    result = await invoke_record(
        context(),
        agreed_price=1700,
        above_max=True,
        carrier_contact_name="Sam Jones",
        carrier_contact_phone="555-0100",
    )
    assert result["code"] == "PRICE_NOT_ABOVE_CEILING"
    save.assert_not_called()


@pytest.mark.asyncio
@patch("call_helpers.save_agreement")
async def test_above_max_requires_contact_details(save):
    result = await invoke_record(context(caller_phone=None), agreed_price=2200, above_max=True)
    assert result["status"] == "error"
    save.assert_not_called()


@pytest.mark.asyncio
@patch("call_helpers.save_agreement", return_value=uuid4())
@patch("call_helpers.NegotiationDBService.notify_carrier_quote")
async def test_valid_agreement_sets_state_and_notifies_once(notify, save):
    ctx = context()
    result = await invoke_record(ctx, agreed_price=1700, above_max=False)
    assert result["status"] == "success"
    assert ctx.agreement_recorded is True
    notify.assert_called_once()


@pytest.mark.asyncio
async def test_end_agreement_requires_successful_persistence():
    callback = AsyncMock()
    task = AsyncMock()
    await end_call("end_call", "tool-2", {"reason": "agreement"}, None, context(), callback, task=task)
    result = json.loads(callback.call_args.args[0])
    assert result["code"] == "AGREEMENT_NOT_RECORDED"
    task.queue_frames.assert_not_called()


@pytest.mark.asyncio
async def test_rejected_identity_cannot_record_outcome():
    result = await invoke_record(context(carrier_identity_rejected=True), agreed_price=1700)
    assert result["code"] == "CARRIER_IDENTITY_NOT_CONFIRMED"
