"""LiveKit media control for holding and restoring the Room1 caller."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import MixerEnableFrame, OutputAudioRawFrame, TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask

from transport_factory import TransportFactory


@dataclass(slots=True)
class PrimaryMediaBinding:
    """Room1 objects needed while the consultation runs in Room2."""

    room_name: str
    room_url: str
    task: Any
    context: Any
    transport: Any


class LiveKitTransferMedia:
    """Own the temporary hold publisher and gate the primary bot media."""

    def __init__(
        self,
        *,
        primary: PrimaryMediaBinding,
        hold_token: str,
        hold_connect_timeout: float = 10.0,
        on_handoff_ended: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._primary = primary
        self._hold_token = hold_token
        self._hold_connect_timeout = hold_connect_timeout
        self._on_handoff_ended = on_handoff_ended
        self._hold_task: PipelineTask | None = None
        self._hold_future: asyncio.Task[Any] | None = None
        self._hold_publisher: asyncio.Task[None] | None = None
        self._hold_transport: Any | None = None
        self._primary_media_gated = False
        self._handoff_observer = False
        self._callback_tasks: set[asyncio.Task] = set()

    @property
    def hold_active(self) -> bool:
        return self._hold_task is not None

    async def gate_primary_media(self, gated: bool) -> None:
        """Pause caller input and suppress Room1 TTS during consultation."""

        if gated == self._primary_media_gated:
            return
        primary_input = self._primary.transport.input()
        if gated:
            await primary_input.pause_processing_frames()
        else:
            await primary_input.resume_processing_frames()
        self._primary_media_gated = gated
        self._primary.context.skip_tts = gated
        self._primary.context.call_mode = "TRANSFER_HOLD" if gated else "BOT_ACTIVE"

    async def start_hold(self) -> None:
        """Join Room1 as a separate output-only hold-music publisher."""

        if self._hold_task is not None:
            return

        transport = TransportFactory.create_hold_music(
            url=self._primary.room_url,
            token=self._hold_token,
            room_name=self._primary.room_name,
        )
        connected = asyncio.Event()

        @transport.event_handler("on_connected")
        async def on_connected(_transport):
            connected.set()

        @transport.event_handler("on_participant_disconnected")
        async def on_participant_disconnected(_transport, participant_id):
            if self._handoff_observer and self._on_handoff_ended is not None:
                callback = asyncio.create_task(
                    self._on_handoff_ended(participant_id)
                )
                self._callback_tasks.add(callback)
                callback.add_done_callback(self._callback_tasks.discard)

        task = PipelineTask(Pipeline([transport.output()]), idle_timeout_secs=None)
        runner = PipelineRunner(handle_sigint=False)
        future = asyncio.create_task(runner.run(task))

        self._hold_transport = transport
        self._hold_task = task
        self._hold_future = future
        self._hold_publisher = asyncio.create_task(self._publish_hold_silence(task))
        try:
            await asyncio.wait_for(connected.wait(), timeout=self._hold_connect_timeout)
        except BaseException:
            await self.stop_hold(retain_observer=False)
            raise

    async def stop_hold(self, *, retain_observer: bool) -> None:
        """Stop hold audio, optionally keeping the participant as a call observer."""

        task = self._hold_task
        if task is None:
            return

        publisher, self._hold_publisher = self._hold_publisher, None
        if publisher is not None:
            publisher.cancel()
            with suppress(BaseException):
                await publisher
        with suppress(Exception):
            await task.queue_frame(MixerEnableFrame(enable=False))

        self._handoff_observer = retain_observer
        if retain_observer:
            try:
                await self._unpublish_audio(self._hold_transport)
            except BaseException:
                self._handoff_observer = False
                await self.stop_hold(retain_observer=False)
                raise
            return

        self._hold_task = None
        future, self._hold_future = self._hold_future, None
        self._hold_transport = None
        with suppress(Exception):
            await task.cancel()
        if future is not None:
            with suppress(BaseException):
                await future

    async def play_primary_announcement(self, text: str) -> None:
        previous = bool(getattr(self._primary.context, "skip_tts", False))
        self._primary.context.skip_tts = False
        try:
            await self._primary.task.queue_frame(
                TTSSpeakFrame(text=text, append_to_context=False)
            )
        finally:
            self._primary.context.skip_tts = previous

    async def detach_primary_publisher(self) -> None:
        await self._unpublish_audio(self._primary.transport)

    async def end_primary_pipeline(self) -> None:
        await self._primary.task.cancel()

    async def restore_primary(self) -> None:
        """Return control of Room1 to the original single-prompt pipeline."""

        await self.stop_hold(retain_observer=False)
        await self.gate_primary_media(False)

    async def quarantine_ambiguous_handoff(self) -> None:
        """Remove bot audio without assuming whether the broker move completed."""

        await self.stop_hold(retain_observer=True)
        await self.detach_primary_publisher()

    async def cleanup(self) -> None:
        with suppress(Exception):
            await self.stop_hold(retain_observer=False)
        with suppress(Exception):
            await self.gate_primary_media(False)

    async def _publish_hold_silence(self, task: PipelineTask) -> None:
        """Drive the mixer with paced frames so its looping file is published."""

        sample_rate = 24000
        frame_seconds = 0.02
        silence = bytes(int(sample_rate * frame_seconds) * 2)
        loop = asyncio.get_running_loop()
        next_frame_at = loop.time()
        while (
            self._hold_task is task
            and self._hold_future is not None
            and not self._hold_future.done()
        ):
            await task.queue_frame(
                OutputAudioRawFrame(
                    audio=silence,
                    sample_rate=sample_rate,
                    num_channels=1,
                )
            )
            next_frame_at += frame_seconds
            await asyncio.sleep(max(0.0, next_frame_at - loop.time()))

    @staticmethod
    async def _unpublish_audio(transport: Any) -> None:
        client = getattr(transport, "_client", None)
        track = getattr(client, "_audio_track", None)
        track_sid = str(getattr(track, "sid", "") or "")
        room = getattr(client, "room", None)
        local_participant = getattr(room, "local_participant", None)
        if not track_sid or local_participant is None:
            raise RuntimeError("LiveKit audio publisher is not ready to detach")
        await local_participant.unpublish_track(track_sid)
