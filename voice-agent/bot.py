"""Single-prompt negotiation bot running over LiveKit."""

import asyncio
import os
import re
import uvicorn
from functools import partial

import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from loguru import logger
from pydantic import BaseModel
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from tool_definitions import (
    VERIFY_CARRIER_FUNCTION,
    GET_LOAD_CONTEXT_FUNCTION,
    RECORD_AGREEMENT_FUNCTION,
    END_CALL_FUNCTION,
    TRANSFER_TO_HUMAN_FUNCTION,
)
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
)
from pipecat.processors.transcript_processor import TranscriptProcessor
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.services.deepgram.stt import DeepgramSTTService, LiveOptions
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.transports.base_transport import BaseTransport
from pipecat.services.cartesia.tts import CartesiaTTSService

from audio_storage import save_audio_to_supabase, store_audio_url_in_call
from call_helpers import (
    end_call,
    finish_call,
    get_load_context,
    persist_confirmed_carrier_identity,
    record_agreement,
    snapshot_universal_context,
    start_call,
    verify_carrier,
)
from db_operations import get_org_id_for_phone, get_org_name_for_phone
from load_context_utils import get_initial_system_prompt
from phone_verification import resolve_caller_identity
from server_utils import AgentRequest
from speech_sync import SpeechSyncProcessor
from src import SupabaseService
from datetime import datetime, timezone
from tts_skip_processor import TTSSkipGateProcessor

from orchestrator import TransferOrchestrator
from transfer_tool_handler import TransferToolHandler
from transport_factory import TransportFactory


class StartRequest(BaseModel):
    """Compatibility wrapper used by the BotRunner client."""

    body: AgentRequest


_active_bot_task: asyncio.Task | None = None

load_dotenv(override=True)

# Initialize Supabase service
SupabaseService.initialize()

# === TRANSFER: Global orchestrator instance ===
_orchestrator: TransferOrchestrator = None


_AFFIRMATIVE_IDENTITY_CONFIRMATION_PHRASES = (
    "yes",
    "yeah",
    "yep",
    "yup",
    "correct",
    "right",
    "that's right",
    "that is right",
    "that's correct",
    "that is correct",
    "that's us",
    "that is us",
    "it is",
    "we are",
    "sure",
    "affirmative",
)
_NEGATIVE_IDENTITY_CONFIRMATION_PHRASES = (
    "no",
    "nope",
    "nah",
    "not us",
    "not our",
    "not correct",
    "that's not us",
    "that is not us",
    "wrong",
    "incorrect",
    "different company",
)


def _normalize_confirmation_text(text: str) -> str:
    cleaned = text.lower().replace("’", "'")
    cleaned = re.sub(r"[^a-z0-9'\s]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _has_confirmation_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {text} "
    return any(f" {phrase} " in padded for phrase in phrases)


def _clear_staged_carrier_identity(context) -> None:
    context.awaiting_carrier_identity_confirmation = False
    context.carrier_identity_confirmed = False
    context.phone_verified = False
    context.caller_mc = None
    context.carrier_name = None
    context.caller_dot_number = None
    context.identity_source = None


async def _persist_confirmed_carrier_identity_from_transcript(context) -> None:
    try:
        succeeded = await persist_confirmed_carrier_identity(context)
        if succeeded:
            logger.info("Carrier identity confirmed from caller transcript")
        else:
            logger.info(
                "Carrier identity confirmation observed, but persistence "
                "did not complete; get_load_context fallback can retry"
            )
    except Exception:
        logger.exception("Unexpected carrier identity confirmation failure")


def _track_background_task(context, task: asyncio.Task) -> None:
    tasks = getattr(context, "_background_tasks", None)
    if tasks is None:
        tasks = set()
        context._background_tasks = tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)


def _handle_carrier_identity_confirmation_from_transcript(
    context,
    text: str,
) -> None:
    if not getattr(context, "awaiting_carrier_identity_confirmation", False):
        return

    normalized = _normalize_confirmation_text(text)
    if not normalized:
        return

    if _has_confirmation_phrase(normalized, _NEGATIVE_IDENTITY_CONFIRMATION_PHRASES):
        logger.info("Caller denied staged carrier identity; clearing pending identity")
        _clear_staged_carrier_identity(context)
        return

    if _has_confirmation_phrase(normalized, _AFFIRMATIVE_IDENTITY_CONFIRMATION_PHRASES):
        context.awaiting_carrier_identity_confirmation = False
        task = asyncio.create_task(
            _persist_confirmed_carrier_identity_from_transcript(context)
        )
        _track_background_task(context, task)


def get_orchestrator() -> TransferOrchestrator:
    """Get the global transfer orchestrator instance."""
    return _orchestrator


async def run_bot(
    transport: BaseTransport,
    request: AgentRequest,
    handle_sigint: bool = False,
) -> None:
    """Run the voice bot for an inbound call."""

    global _orchestrator

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

    CARTESIA_VOICE = "e07c00bc-4134-4eae-9ea4-1a55fb45746b"
    tts = CartesiaTTSService(
        api_key=os.environ["CARTESIA_API_KEY"],
        voice_id=CARTESIA_VOICE,
    )

    llm = OpenAILLMService(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-4.1",
        params=OpenAILLMService.InputParams(
            frequency_penalty=0.6,
            presence_penalty=0.5,
            temperature=0.7,
        ),
    )

    # Bind metadata to get_load_context using partial
    get_load_context_with_metadata = partial(
        get_load_context, caller_phone=request.caller_phone
    )

    # Phone-first carrier verification feature flag — gates the entire
    # phone-first behavior so flag=false produces zero behavior change vs.
    # the pre-PR baseline. When true: lookup runs and the transcript-driven
    # confirmation path can persist the phone→carrier mapping.
    phone_first_enabled = (
        os.getenv("HIGHWAY_PHONE_LOOKUP_ENABLED", "false").lower() == "true"
    )

    standard_tools = [
        VERIFY_CARRIER_FUNCTION,
        GET_LOAD_CONTEXT_FUNCTION,
        RECORD_AGREEMENT_FUNCTION,
        END_CALL_FUNCTION,
        TRANSFER_TO_HUMAN_FUNCTION,
    ]
    tools = ToolsSchema(standard_tools=standard_tools)

    # Fetch organization name + id for greeting and Supabase scoping.
    # We look up org_id directly here (rather than relying on context.org_id
    # which gets set later in create_call_async) because the parallel
    # phone_carrier_lookup query needs it before the LLM context is built.
    org_name = get_org_name_for_phone(request.bot_phone) if request.bot_phone else None
    org_id_for_lookup = (
        get_org_id_for_phone(request.bot_phone) if request.bot_phone else None
    )
    logger.info(f"Organization for greeting: name={org_name} id={org_id_for_lookup}")

    # Phone-first carrier verification (backend, pre-LLM). Runs Highway and
    # Supabase phone_carrier_lookup in parallel. Never raises; failure modes
    # collapse to CarrierLookupResult.unknown(...) and the bot falls through
    # to the current MC-first greeting.
    phone_verification = await resolve_caller_identity(
        request.caller_phone, org_id_for_lookup
    )
    logger.info(
        f"Phone verification: status={phone_verification.status} "
        f"reason={phone_verification.reason} "
        f"carrier={phone_verification.carrier_name}"
    )

    # Initialize LLM context
    messages = [
        {
            "role": "system",
            "content": get_initial_system_prompt(
                org_name=org_name,
                phone_verification=phone_verification,
                phone_first_enabled=phone_first_enabled,
            ),
        },
    ]

    # Setup the conversational context with tools
    context = LLMContext(messages, tools)
    context_aggregator = LLMContextAggregatorPair(context)

    # Store the provider room name for call transfer.
    context.room_name = request.room_name
    context.session_id = None  # Will be set when participant joins
    context.skip_tts = False
    context.call_mode = "BOT_ACTIVE"

    # Make caller_phone + org_id available on context early so verify_carrier
    # can upsert into phone_carrier_lookup when the LLM verifies an MC,
    # WITHOUT waiting for create_call_async to finish setting them.
    # Otherwise a fast LLM turn (e.g. caller denies a phone-verified carrier
    # and immediately gives a corrected MC) could fire verify_carrier before
    # context.org_id is populated, and the upsert guard would skip the write
    # — leaving the stale phone→MC mapping in place. create_call_async still
    # overwrites context.org_id later with the same value (idempotent).
    context.caller_phone = request.caller_phone
    context.org_id = org_id_for_lookup
    context.awaiting_carrier_identity_confirmation = False

    # Pre-populate carrier identity on known-carrier path so downstream tools
    # (record_agreement, transfer_to_human, etc.) see the MC without needing
    # the LLM to call verify_carrier.
    if phone_verification.status == "known_carrier":
        context.caller_mc = phone_verification.mc_number
        context.carrier_name = phone_verification.carrier_name
        context.phone_verified = True
        # Track where the identity came from so the backend confirmation path
        # can avoid a no-op write to Supabase when the data is already there.
        # "supabase" => row already exists with same data, skip the write.
        # "highway"  => not yet in Supabase, write on confirmation.
        context.identity_source = (
            "supabase"
            if phone_verification.reason == "from_supabase_lookup"
            else "highway"
        )
        context.carrier_identity_confirmed = False
        context.awaiting_carrier_identity_confirmation = True

    # Transcript processor for capturing human-readable conversation
    transcript = TranscriptProcessor()

    # Create audio buffer processor for recording (mono for telephony)
    audiobuffer = AudioBufferProcessor(num_channels=1)

    # Speech sync processor - tracks TTS start/stop for coordinating function calls
    speech_sync = SpeechSyncProcessor()

    # Skip tts processor
    skip_tts_processor = TTSSkipGateProcessor(context)

    # Curious question processor - wraps questions in <curious> tags for natural intonation
    # curious_processor = CuriousQuestionProcessor()

    # Register the function handlers
    llm.register_function("verify_carrier", verify_carrier)
    llm.register_function("get_load_context", get_load_context_with_metadata)
    llm.register_function("record_agreement", record_agreement)
    # llm.register_function("post_human_joined", post_human_joined)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript.user(),  # Capture user transcript
            context_aggregator.user(),
            llm,
            # curious_processor,  # Wrap questions in <curious> tags for natural intonation
            # frame_log_processor,
            # sentence_pause_processor,
            skip_tts_processor,
            tts,
            speech_sync,  # After TTS to track BotStarted/StoppedSpeakingFrame
            transport.output(),
            audiobuffer,  # Add audio buffer to pipeline for recording
            transcript.assistant(),  # Capture assistant transcript
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        idle_timeout_secs=None,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
            allow_interruptions=True,
            audio_in_sample_rate=8000,  # Native G.711 telephony rate
            audio_out_sample_rate=8000,  # Native G.711 telephony rate
            turn_analyzer=LocalSmartTurnAnalyzerV3(),
        ),
    )

    # === TRANSFER: Initialize orchestrator and set Room1 references ===
    _orchestrator = TransferOrchestrator()
    _orchestrator.set_room1_references(
        room1_url=request.livekit_url,
        room1_name=request.room_name,
        room1_token=request.token,
        task=task,
        context=context,
        context_aggregator=context_aggregator,
        transport=transport,
        call_id=request.provider_call_id,
    )
    _orchestrator.state.provider_call_id = request.provider_call_id
    _orchestrator.state.telephony_provider = "livekit"
    _orchestrator.state.carrier_participant_identity = request.participant_identity
    _orchestrator.state.carrier_participant_id = request.participant_sid

    # === TRANSFER: Create transfer tool handler ===
    # We need an aiohttp session for the transfer. Create one or reuse.
    transfer_http_session = aiohttp.ClientSession()

    transfer_handler = TransferToolHandler(
        orchestrator=_orchestrator,
        http_session=transfer_http_session,
        stt=stt,
        tts=tts,
        llm=llm,
        skip_tts_processor=skip_tts_processor,
        transcript=transcript,
        speech_sync=speech_sync,
        audiobuffer=audiobuffer,
        context_aggregator=context_aggregator,
    )

    # === TRANSFER: Register transfer tool handlers on LLM ===
    llm.register_function(
        "transfer_to_human", transfer_handler.handle_transfer_to_human
    )
    llm.register_function(
        "transfer_human_to_carrier", transfer_handler.handle_transfer_human_to_carrier
    )

    # Bind task to end_call function
    end_call_with_task = partial(end_call, task=task)
    llm.register_function("end_call", end_call_with_task)

    # Handler for audio recording
    @audiobuffer.event_handler("on_audio_data")
    async def on_audio_data(buffer, audio, sample_rate, num_channels):
        if hasattr(context, "call_id") and context.call_id:
            call_id_str = str(context.call_id)
            audio_url = await save_audio_to_supabase(
                audio, call_id_str, sample_rate, num_channels
            )
            if audio_url:
                await store_audio_url_in_call(call_id_str, audio_url)

    # Transcript event handler
    processed_messages = set()

    @transcript.event_handler("on_transcript_update")
    async def on_transcript_update(processor, frame):
        if not frame.messages:
            return
        message = frame.messages[-1]
        message_id = f"{message.role}:{message.content}"
        if message_id in processed_messages:
            return
        processed_messages.add(message_id)

        role = "caller" if message.role == "user" else "agent"
        display_role = "Caller" if message.role == "user" else "Agent"
        logger.info(f"[Transcript] {display_role}: {message.content}")

        if phone_first_enabled and message.role == "user":
            _handle_carrier_identity_confirmation_from_transcript(
                context, message.content
            )

        if not hasattr(context, "transcript_messages"):
            context.transcript_messages = []
        context.transcript_messages.append(
            {
                "role": role,
                "content": message.content,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    # LiveKit emits participant SIDs. The ingress request identifies the SIP
    # participant assigned to this call, so unrelated room occupants must not
    # start or terminate the negotiation pipeline.
    _call_started = False
    _matched_participant_sid: str | None = None
    _departure_handled = False
    _recording_started = False
    _recording_stopped = False

    async def _stop_recording_once() -> None:
        nonlocal _recording_stopped
        if not _recording_started or _recording_stopped:
            return
        _recording_stopped = True
        try:
            await audiobuffer.stop_recording()
        except Exception as e:
            logger.exception(f"Failed to stop recording: {e}")

    async def _participant_identity(participant_id: str) -> str | None:
        metadata = await transport.get_participant_metadata(participant_id)
        identity = metadata.get("identity") or metadata.get("name")

        # Pipecat 0.0.95's metadata helper does not include the LiveKit
        # identity, although the underlying SDK participant does.
        client = getattr(transport, "_client", None)
        try:
            participant = client.room.remote_participants.get(participant_id)
            return getattr(participant, "identity", None) or identity
        except (AttributeError, RuntimeError):
            return identity

    async def _matches_caller(participant_id: str) -> tuple[bool, str | None]:
        identity = await _participant_identity(participant_id)
        if request.participant_sid:
            return participant_id == request.participant_sid, identity
        if request.participant_identity:
            return identity == request.participant_identity, identity
        return True, identity

    async def _start_call(participant_id: str) -> None:
        nonlocal _call_started, _matched_participant_sid, _recording_started
        if _call_started:
            return

        matches, identity = await _matches_caller(participant_id)
        if not matches:
            logger.info(
                f"Ignoring non-caller participant: sid={participant_id} "
                f"identity={identity}"
            )
            return

        _call_started = True
        _matched_participant_sid = participant_id

        logger.info(
            f"Starting call for LiveKit participant: sid={participant_id} "
            f"identity={identity}"
        )
        context.session_id = participant_id
        context.participant_identity = identity

        # === TRANSFER: Track carrier participant ID ===
        _orchestrator.state.carrier_participant_id = participant_id
        _orchestrator.state.carrier_participant_identity = identity
        _orchestrator.state.carrier_session_id = participant_id
        logger.info(f"Carrier tracked: sid={participant_id}, identity={identity}")

        await audiobuffer.start_recording()
        _recording_started = True

        async def create_call_async():
            try:
                result = start_call(
                    load_id=None,
                    provider_call_id=request.provider_call_id,
                    telephony_provider="livekit",
                    caller_number=request.caller_phone,
                    caller_country_code=None,
                    caller_mc=(
                        phone_verification.mc_number
                        if phone_verification.status == "known_carrier"
                        else None
                    ),
                    bot_phone=request.bot_phone,
                )
                if result:
                    context.call_id = result.call_id
                    _orchestrator.call_id = str(result.call_id)
                    context.org_id = (
                        result.org_id
                    )  # Store org_id for multi-tenant isolation
                    logger.info(
                        f"Created call record: {result.call_id} (org: {result.org_id})"
                    )
            except Exception as e:
                logger.error(f"Failed to create call record: {e}")

        context._call_task = asyncio.create_task(create_call_async())

        # Start the conversation - single entry point avoids "ringing state" errors
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant_id):
        await _start_call(participant_id)

    @transport.event_handler("on_participant_connected")
    async def on_participant_connected(transport, participant_id):
        await _start_call(participant_id)

    @transport.event_handler("on_participant_disconnected")
    async def on_participant_disconnected(transport, participant_id):
        nonlocal _departure_handled
        if (
            _orchestrator.state.phase.value
            in {"handoff_requested", "handoff_complete"}
            and participant_id == _orchestrator.state.human_participant_id
        ):
            await _orchestrator.on_handoff_ended(participant_id)
            return
        if _departure_handled:
            return
        if _matched_participant_sid != participant_id:
            logger.info(f"Ignoring non-caller departure: sid={participant_id}")
            return

        _departure_handled = True
        logger.info(f"Caller left LiveKit room: sid={participant_id}")
        if _orchestrator.state.phase.value == "handoff_complete":
            await _orchestrator.on_handoff_ended(participant_id)
        elif _orchestrator.is_transfer_in_progress():
            await _orchestrator.on_carrier_left_primary()
        await _stop_recording_once()
        await task.cancel()

    runner = PipelineRunner(handle_sigint=handle_sigint)
    await runner.run(task)
    await _stop_recording_once()

    # Room1 pipeline has ended. Two possibilities:
    # 1. Normal disconnect (no transfer) → clean up and exit
    # 2. Transfer in progress → wait for transfer to complete

    # Check if a transfer is in progress
    if _orchestrator.is_transfer_in_progress():
        logger.info(
            "Room1 pipeline ended due to transfer. Waiting for transfer to complete..."
        )

        # Wait for the transfer to finish
        # The transfer_handler's asyncio.create_task is running the full
        # Phase 2 + Phase 3 flow. We need to wait for it.
        await _orchestrator.wait_for_transfer_complete()

        logger.info("Transfer flow complete.")
    else:
        logger.info("Room1 pipeline ended normally (no transfer).")

    # === Now safe to clean up ===
    # === TRANSFER: Clean up transfer HTTP session ===
    await transfer_http_session.close()

    # Save transcript after pipeline ends
    if hasattr(context, "call_id") and context.call_id:
        end_reason = getattr(context, "end_reason", "abrupt")
        transcription = list(getattr(context, "transcript_messages", None) or [])
        transcription.extend(
            {
                "role": "agent" if message["role"] == "agent" else "caller",
                "content": f"[BROKER CONSULTATION] {message['content']}",
                "timestamp": message["timestamp"],
            }
            for message in _orchestrator.state.room2_transcript
        )
        call_summary = {"outcome": end_reason}
        if _orchestrator.state.attempt_id:
            call_summary["transfer"] = _orchestrator.state.audit_snapshot()

        try:
            universal_context = snapshot_universal_context(context)
            if universal_context is not None:
                call_summary["universal_context"] = universal_context
                call_summary["universal_context_captured_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
        except Exception as e:
            logger.warning(f"Failed to snapshot universal context: {e}")
        finish_call(context.call_id, call_summary, end_reason, transcription)
        logger.info(
            f"Call saved: {context.call_id} with reason: {end_reason}, "
            f"{len(transcription or [])} messages"
        )


async def bot(request: AgentRequest) -> None:
    """Create a LiveKit transport and run one negotiation call."""
    transport = TransportFactory.create(
        url=request.livekit_url,
        token=request.token,
        room_name=request.room_name,
        bot_name="Negotiation Agent",
    )
    await run_bot(transport, request, handle_sigint=False)


def _bot_finished(task: asyncio.Task) -> None:
    """Release the single-call runner slot and surface background failures."""
    global _active_bot_task
    if _active_bot_task is task:
        _active_bot_task = None
    try:
        error = task.exception()
    except asyncio.CancelledError:
        logger.info("Bot task cancelled")
        return
    if error:
        logger.error(f"Bot task failed: {error}")


app = FastAPI(title="Negotiation BotRunner")


@app.post("/start", status_code=status.HTTP_202_ACCEPTED)
async def start_bot(payload: AgentRequest | StartRequest):
    """Accept either a direct AgentRequest or ``{"body": AgentRequest}``."""
    global _active_bot_task
    if _active_bot_task and not _active_bot_task.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This bot runner is already handling a call",
        )

    request = payload.body if isinstance(payload, StartRequest) else payload
    _active_bot_task = asyncio.create_task(
        bot(request), name=f"livekit-call-{request.room_name}"
    )
    _active_bot_task.add_done_callback(_bot_finished)
    return {"status": "started", "room_name": request.room_name}


@app.get("/health")
async def health_check():
    active = bool(_active_bot_task and not _active_bot_task.done())
    return {"status": "ok", "active_call": active}


if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "7860")),
    )
