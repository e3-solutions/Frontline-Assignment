from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from livekit_transfer_media import LiveKitTransferMedia, PrimaryMediaBinding


def build_media():
    primary_input = SimpleNamespace(
        pause_processing_frames=AsyncMock(),
        resume_processing_frames=AsyncMock(),
    )
    transport = SimpleNamespace(input=lambda: primary_input)
    context = SimpleNamespace(skip_tts=False, call_mode="BOT_ACTIVE")
    task = SimpleNamespace(cancel=AsyncMock(), queue_frame=AsyncMock())
    media = LiveKitTransferMedia(
        primary=PrimaryMediaBinding(
            room_name="carrier-room",
            room_url="wss://test.livekit.cloud",
            task=task,
            context=context,
            transport=transport,
        ),
        hold_token="token",
    )
    return media, primary_input, context


@pytest.mark.asyncio
async def test_primary_media_gate_pauses_input_and_suppresses_tts():
    media, primary_input, context = build_media()

    await media.gate_primary_media(True)
    await media.gate_primary_media(True)

    primary_input.pause_processing_frames.assert_awaited_once()
    assert context.skip_tts is True
    assert context.call_mode == "TRANSFER_HOLD"


@pytest.mark.asyncio
async def test_restore_primary_resumes_the_single_prompt_pipeline():
    media, primary_input, context = build_media()
    await media.gate_primary_media(True)

    await media.restore_primary()

    primary_input.resume_processing_frames.assert_awaited_once()
    assert context.skip_tts is False
    assert context.call_mode == "BOT_ACTIVE"


@pytest.mark.asyncio
async def test_detach_unpublishes_exact_livekit_audio_track():
    local_participant = SimpleNamespace(unpublish_track=AsyncMock())
    transport = SimpleNamespace(
        _client=SimpleNamespace(
            _audio_track=SimpleNamespace(sid="TR_audio"),
            room=SimpleNamespace(local_participant=local_participant),
        )
    )

    await LiveKitTransferMedia._unpublish_audio(transport)

    local_participant.unpublish_track.assert_awaited_once_with("TR_audio")


@pytest.mark.asyncio
async def test_detach_fails_closed_when_publisher_is_not_ready():
    with pytest.raises(RuntimeError, match="not ready"):
        await LiveKitTransferMedia._unpublish_audio(SimpleNamespace())
