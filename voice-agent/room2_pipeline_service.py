"""Room2 pipeline service.

Single Responsibility: Build and run the pipecat pipeline for Room2.
"""

import asyncio
import os
from contextlib import suppress
from datetime import datetime, timezone

from loguru import logger
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.frames.frames import LLMRunFrame

from transfer_state import TransferState
from transport_factory import TransportFactory
from context_builder import Room2ContextBuilder
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from speech_sync import SpeechSyncProcessor
from tts_skip_processor import TTSSkipGateProcessor
from transfer_tool_handler import TransferToolHandler
from pipecat.services.cartesia.tts import CartesiaTTSService

from audio_storage import save_audio_to_supabase


class Room2PipelineService:
    """Builds and manages the Room2 pipeline lifecycle."""

    def __init__(self, state: TransferState, orchestrator):
        self._state = state
        self._orchestrator = orchestrator
        self._transport = None
        self._task = None
        self._runner = None
        self._run_future = None
        self._context = None
        self._broker_connected = asyncio.Event()
        self._broker_media_ready = asyncio.Event()
        self._broker_answered = asyncio.Event()
        self._opening_started = False
        self._callback_tasks: set[asyncio.Task] = set()
        self._transcript_ids: set[str] = set()
        self._audiobuffer = None
        self._recording_started = False

    @property
    def transport(self):
        return self._transport

    @property
    def task(self):
        return self._task

    async def start(
        self,
        stt,
        tts,
        llm,
        skip_tts_processor,
        transcript,
        speech_sync,
        audiobuffer,
        context_aggregator,
    ) -> asyncio.Task:
        """Build and start the Room2 pipeline.

        Args:
            stt: Speech-to-text service (reused from Room1)
            tts: Text-to-speech service (reused from Room1)
            llm: LLM service (reused from Room1)
            skip_tts_processor: TTS skip gate processor
            transcript: Transcript processor
            speech_sync: Speech sync processor
            audiobuffer: Audio buffer processor

        Returns:
            asyncio.Task running the pipeline

        Parameters
        ----------
        audiobuffer
        speech_sync
        transcript
        skip_tts_processor
        llm
        tts
        stt
        context_aggregator
        """
        # The bot receives a separate token for the broker room and joins it
        # directly; the telephony service is responsible for bringing in the
        # human participant.
        self._transport = TransportFactory.create(
            url=self._state.room2_url,
            token=self._state.room2_token,
            room_name=self._state.room2_name,
            bot_name="Negotiation Agent",
        )

        # === Create FRESH STT ===
        stt = DeepgramSTTService(
            api_key=os.getenv("DEEPGRAM_API_KEY"),
            live_options=LiveOptions(
                model="nova-3",
                language="en-US",
                smart_format=True,
                interim_results=True,
                encoding="linear16",
                sample_rate=8000,
                endpointing=600,
            ),
        )

        # Create a fresh synthesizer for the broker briefing room.
        CARTESIA_VOICE = "e07c00bc-4134-4eae-9ea4-1a55fb45746b"
        tts = CartesiaTTSService(
            api_key=os.environ["CARTESIA_API_KEY"],
            voice_id=CARTESIA_VOICE,
        )

        # === Create FRESH LLM ===
        llm = OpenAILLMService(
            api_key=os.getenv("OPENAI_API_KEY"),
            model="gpt-4.1-mini",
            params=OpenAILLMService.InputParams(
                frequency_penalty=0.6,
                presence_penalty=0.5,
                temperature=0.3,
            ),
        )

        # === Build Room2 context with Room1 history ===
        self._context, room2_context_aggregator = Room2ContextBuilder.build(
            state=self._state,
            llm=llm,
        )

        # === Create FRESH processors ===
        transcript = TranscriptProcessor()
        audiobuffer = AudioBufferProcessor(num_channels=1)
        self._audiobuffer = audiobuffer
        speech_sync = SpeechSyncProcessor()
        skip_tts_processor = TTSSkipGateProcessor(self._context)

        # === Register Room2-specific tool handlers ===
        transfer_handler = TransferToolHandler(
            orchestrator=self._orchestrator,
            http_session=None,
            stt=stt,
            tts=tts,
            llm=llm,
            skip_tts_processor=skip_tts_processor,
            transcript=transcript,
            speech_sync=speech_sync,
            audiobuffer=audiobuffer,
            context_aggregator=room2_context_aggregator,
        )

        llm.register_function(
            "transfer_human_to_carrier",
            transfer_handler.handle_transfer_human_to_carrier,
        )

        # Build pipeline
        pipeline = Pipeline(
            [
                self._transport.input(),
                stt,
                transcript.user(),
                room2_context_aggregator.user(),
                llm,
                skip_tts_processor,
                tts,
                speech_sync,
                self._transport.output(),
                audiobuffer,
                transcript.assistant(),
                room2_context_aggregator.assistant(),
            ]
        )

        self._task = PipelineTask(
            pipeline,
            params=PipelineParams(
                enable_metrics=True,
                enable_usage_metrics=True,
                allow_interruptions=True,
                audio_in_sample_rate=8000,
                audio_out_sample_rate=8000,
                turn_analyzer=LocalSmartTurnAnalyzerV3(),
            ),
        )

        self._runner = PipelineRunner()

        @transcript.event_handler("on_transcript_update")
        async def on_transcript_update(_processor, frame):
            if not frame.messages:
                return
            message = frame.messages[-1]
            message_id = f"{message.role}:{message.content}"
            if message_id in self._transcript_ids:
                return
            self._transcript_ids.add(message_id)
            self._state.room2_transcript.append(
                {
                    "role": "broker" if message.role == "user" else "agent",
                    "content": message.content,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )

        @audiobuffer.event_handler("on_audio_data")
        async def on_audio_data(_buffer, audio, sample_rate, num_channels):
            call_id = self._orchestrator.call_id
            if not call_id:
                return
            self._state.room2_recording_url = await save_audio_to_supabase(
                audio,
                f"{call_id}-consultation",
                sample_rate,
                num_channels,
            )

        # Setup participant tracking for human joining Room2
        self._setup_room2_events()

        logger.info(
            f"Starting Room2 pipeline in {self._state.room2_name} "
            f"at {self._state.room2_url}"
        )
        self._run_future = asyncio.create_task(self._runner.run(self._task))

        return self._run_future

    def _setup_room2_events(self):
        """Register event handlers for Room2."""

        async def track_human(participant_id: str) -> bool:
            metadata = await self._transport.get_participant_metadata(participant_id)
            identity = metadata.get("identity") or metadata.get("name")

            # Pipecat 0.0.95 exposes the participant SID through its public
            # event, but its metadata helper omits the LiveKit identity.
            client = getattr(self._transport, "_client", None)
            try:
                participant = client.room.remote_participants.get(participant_id)
                identity = getattr(participant, "identity", None) or identity
            except (AttributeError, RuntimeError):
                pass

            expected_id = self._state.human_participant_id
            expected_identity = self._state.human_participant_identity
            if expected_id and expected_id != participant_id:
                logger.info(
                    f"[Room2] Ignoring unexpected participant: {participant_id}"
                )
                return False
            if expected_identity and expected_identity != identity:
                logger.info(f"[Room2] Ignoring unexpected identity: {identity}")
                return False

            logger.info(
                f"[Room2] Participant connected: sid={participant_id} "
                f"identity={identity}"
            )

            self._state.human_participant_id = participant_id
            self._state.human_participant_identity = identity or expected_identity
            self._context.session_id = participant_id
            self._broker_connected.set()
            return True

        async def mark_broker_media_ready(participant_id: str) -> None:
            if not await track_human(participant_id):
                return
            self._broker_media_ready.set()
            await self._start_opening_if_ready()

        @self._transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant_id):
            """Track the expected broker while the outbound leg is dialing."""
            await track_human(participant_id)

        @self._transport.event_handler("on_participant_connected")
        async def on_participant_connected(transport, participant_id):
            """Track any participant joining Room2."""
            await track_human(participant_id)

        @self._transport.event_handler("on_audio_track_subscribed")
        async def on_audio_track_subscribed(transport, participant_id):
            """Record transport-level input readiness for the expected broker."""
            await mark_broker_media_ready(participant_id)

        @self._transport.event_handler("on_participant_disconnected")
        async def on_participant_disconnected(transport, participant_id):
            """End the broker pipeline when its telephony participant leaves."""
            if participant_id != self._state.human_participant_id:
                return
            logger.info(f"[Room2] Human broker disconnected: {participant_id}")
            callback = asyncio.create_task(
                self._orchestrator.on_broker_left_consultation()
            )
            self._callback_tasks.add(callback)
            callback.add_done_callback(self._callback_tasks.discard)

    async def mark_broker_answered(self) -> None:
        """Record that LiveKit's wait-until-answered SIP request completed."""

        self._broker_answered.set()
        await self._start_opening_if_ready()

    async def _start_opening_if_ready(self) -> None:
        if not (self._broker_answered.is_set() and self._broker_media_ready.is_set()):
            return
        if not self._recording_started and self._audiobuffer is not None:
            self._recording_started = True
            await self._audiobuffer.start_recording()
        if not self._opening_started:
            self._opening_started = True
            await self._task.queue_frames([LLMRunFrame()])

    async def wait_for_broker(self, timeout: float) -> None:
        """Wait for the expected broker to be visible to the Room2 transport."""

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        await asyncio.wait_for(self._broker_connected.wait(), timeout=timeout)
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise asyncio.TimeoutError
        await asyncio.wait_for(self._broker_media_ready.wait(), timeout=remaining)
        if not self._broker_answered.is_set():
            raise RuntimeError("Broker presence was observed before answer confirmation")

    async def stop(self):
        """Stop the Room2 pipeline."""
        if self._recording_started and self._audiobuffer is not None:
            with suppress(Exception):
                await self._audiobuffer.stop_recording()
            self._recording_started = False
        if self._task:
            await self._task.cancel()
            logger.info("Room2 pipeline stopped")
        if self._run_future:
            with suppress(BaseException):
                await self._run_future
        current_task = asyncio.current_task()
        for callback in tuple(self._callback_tasks):
            if callback is current_task:
                continue
            if not callback.done():
                callback.cancel()
            with suppress(BaseException):
                await callback
        self._callback_tasks.clear()
        self._task = None
        self._transport = None
        self._runner = None
        self._run_future = None
