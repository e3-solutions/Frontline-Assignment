"""Room2 pipeline service.

Single Responsibility: Build and run the pipecat pipeline for Room2.
"""

import asyncio
import os

from loguru import logger
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask

from transfer_state import TransferState
from transport_factory import TransportFactory
from context_builder import Room2ContextBuilder
from response_aware_sentence_aggregator import ResponseAwareSentenceAggregator
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from tts import Qwen3VoiceCloneService
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transcriptions.language import Language
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from speech_sync import SpeechSyncProcessor
from tts_skip_processor import TTSSkipGateProcessor
from transfer_tool_handler import TransferToolHandler
from pipecat.services.cartesia.tts import CartesiaTTSService


room2_context = None

class Room2PipelineService:
    """Builds and manages the Room2 pipeline lifecycle."""

    def __init__(self, state: TransferState, orchestrator):
        self._state = state
        self._orchestrator = orchestrator
        self._transport = None
        self._task = None
        self._runner = None
        self._run_future = None

    @property
    def transport(self):
        return self._transport

    @property
    def task(self):
        return self._task

    async def start(self, stt, tts, llm, skip_tts_processor, transcript, speech_sync, audiobuffer, context_aggregator) -> asyncio.Task:
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
        # Create transport for Room2 (no dialin_settings — bot is joining directly)
        self._transport = TransportFactory.create(
            room_url=self._state.room2_url,
            token=self._state.room2_token,
            bot_name="Negotiation Agent",
            daily_dialin_settings=self._state.daily_dialin_settings,
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

        # === Create FRESH TTS ===
        # tts = Qwen3VoiceCloneService(
        #     websocket_url=os.getenv("QWEN3_TTS_WEBSOCKET_URL"),
        #     params=Qwen3VoiceCloneService.InputParams(
        #         language=Language.EN,
        #         speaker="vivian",
        #         chunk_size=37,
        #         speed=1.2,
        #         instruct=(
        #             "Use a neutral american female accent. Speak with a warm, "
        #             "conversational, friendly tone. Use natural, slight conversational "
        #             "fillers like 'well' or 'you know', and ensure the pacing is relaxed, "
        #             "like a podcast host. Your speech needs to be very clear and precise."
        #         ),
        #     ),
        #     sample_rate=24000,
        #     text_aggregator=ResponseAwareSentenceAggregator(),
        # )
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
        global room2_context
        room2_context, room2_context_aggregator = Room2ContextBuilder.build(
            state=self._state,
            llm=llm,
        )

        # === Create FRESH processors ===
        transcript = TranscriptProcessor()
        audiobuffer = AudioBufferProcessor(num_channels=1)
        speech_sync = SpeechSyncProcessor()
        skip_tts_processor = TTSSkipGateProcessor(room2_context)

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

        llm.register_function("transfer_human_to_carrier", transfer_handler.handle_transfer_human_to_carrier)

        # Build pipeline
        pipeline = Pipeline([
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
        ])

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

        # Setup participant tracking for human joining Room2
        self._setup_room2_events()

        logger.info(f"Starting Room2 pipeline at {self._state.room2_url}")
        self._run_future = asyncio.create_task(self._runner.run(self._task))

        return self._run_future

    def _setup_room2_events(self):
        """Register event handlers for Room2."""

        @self._transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(transport, participant):
            """Human broker joined Room2 — start the conversation."""
            participant_id = participant["id"]
            info = participant.get("info", {})
            user_name = info.get("userName", "")

            room2_context.session_id = participant.get("id")

            logger.info(f"[Room2] First participant joined: {participant_id} ({user_name})")

            # Skip the bot itself
            if user_name == "Negotiation Agent":
                return

            # This is the human broker
            self._state.human_participant_id = participant_id
            logger.info(f"[Room2] Human broker identified: {participant_id}")

            # Start the conversation — bot should brief the human
            # await self._task.queue_frames([LLMRunFrame()])

        @self._transport.event_handler("on_participant_joined")
        async def on_participant_joined(transport, participant):
            """Track any participant joining Room2."""
            participant_id = participant["id"]
            info = participant.get("info", {})
            user_name = info.get("userName", "")

            logger.info(f"[Room2] Participant joined: {participant_id} ({user_name})")
            logger.debug(f"[Room2] Full participant info: {participant}")

            if user_name == "Negotiation Agent":
                return

            self._state.human_participant_id = participant_id

        @self._transport.event_handler("on_dialout_connected")
        async def on_dialout_connected(transport, data):
            """Capture human's SIP session ID when dialout connects."""
            logger.info(f"[Room2] Dialout connected: {data}")
            session_id = data.get("sessionId")
            if session_id:
                self._state.human_session_id = session_id
                logger.info(f"[Room2] Human SIP session ID: {session_id}")

        @self._transport.event_handler("on_dialout_answered")
        async def on_dialout_answered(transport, data):
            """Capture session ID from dialout answered event."""
            logger.info(f"[Room2] Dialout answered: {data}")
            session_id = data.get("sessionId")
            if session_id:
                self._state.human_session_id = session_id
                logger.info(f"[Room2] Human SIP session ID (from answered): {session_id}")

    async def stop(self):
        """Stop the Room2 pipeline."""
        if self._task:
            await self._task.cancel()
            logger.info("Room2 pipeline stopped")
        self._task = None
        self._transport = None
        self._runner = None