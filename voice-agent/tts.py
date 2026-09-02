#
# Qwen3-TTS service for pipecat integration.
#
# SPDX-License-Identifier: Apache-2.0
#

"""Qwen3-TTS text-to-speech service implementations for pipecat.

Services:
    - Qwen3TTSService: Custom voice TTS with predefined speakers
    - Qwen3VoiceDesignService: Voice design TTS with natural language descriptions
    - Qwen3VoiceCloneService: Voice cloning TTS from reference audio
"""

import json
import base64
import asyncio
import uuid
from typing import AsyncGenerator, Optional, Union
from enum import Enum
from pathlib import Path

from loguru import logger
from pydantic import BaseModel
import re

from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    ErrorFrame,
    Frame,
    InterruptionFrame,
    StartFrame,
    TTSAudioRawFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
    TextFrame,
)
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.tts_service import TTSService
from pipecat.transcriptions.language import Language
from pipecat.utils.text.base_text_aggregator import BaseTextAggregator


try:
    from websockets.asyncio.client import connect as websocket_connect
    from websockets.protocol import State
except ModuleNotFoundError as e:
    logger.error(f"Exception: {e}")
    logger.error("In order to use Qwen3TTS, you need to `pip install websockets`.")
    raise Exception(f"Missing module: {e}")

from streaming_whisper import StreamingWhisperLPC


# Context ID size - must match server
CONTEXT_ID_SIZE = 36


def language_to_qwen3_language(language: Language) -> Optional[str]:
    """Convert a pipecat Language enum to Qwen3-TTS language string."""
    LANGUAGE_MAP = {
        Language.EN: "English",
        Language.ZH: "Chinese",
        Language.JA: "Japanese",
        Language.KO: "Korean",
        Language.DE: "German",
        Language.FR: "French",
        Language.ES: "Spanish",
        Language.IT: "Italian",
        Language.PT: "Portuguese",
        Language.RU: "Russian",
        Language.AR: "Arabic",
        Language.NL: "Dutch",
        Language.PL: "Polish",
        Language.TR: "Turkish",
        Language.VI: "Vietnamese",
        Language.TH: "Thai",
        Language.ID: "Indonesian",
    }
    return LANGUAGE_MAP.get(language, "Auto")

# ============================================
# Qwen3VoiceCloneService - Voice Cloning TTS
# ============================================

def extract_whisper_block(text_: str) -> tuple[bool, str]:
    pattern = r"<whisper>(.*?)</whisper>"

    match = re.search(pattern, text_, re.DOTALL)

    if match:
        whisper_text = match.group(1).strip()
        return True, whisper_text

    return False, text_.strip()


class Qwen3VoiceCloneService(TTSService):
    """Qwen3-TTS Voice Clone service with WebSocket streaming.

    Clone any voice from a reference audio sample.
    
    Optimization: The reference audio is only sent on the first request.
    Subsequent requests reuse the cached voice_id from the server.
    """

    class InputParams(BaseModel):
        """Input parameters for Qwen3-TTS Voice Clone configuration."""
        language: Optional[Language] = Language.EN
        ref_audio: Optional[str] = None  # File path
        ref_text: Optional[str] = None
        x_vector_only_mode: bool = False
        chunk_size: int = 50
        speed: float = 1.0

    def __init__(
        self,
        *,
        websocket_url: str,
        params: Optional[InputParams] = None,
        sample_rate: Optional[int] = None,
        text_aggregator: BaseTextAggregator,
        **kwargs,
    ):
        """Initialize the Qwen3-TTS Voice Clone service."""
        super().__init__(sample_rate=sample_rate or 24000, text_aggregator=text_aggregator, **kwargs)

        params = params or Qwen3VoiceCloneService.InputParams()

        self._websocket_url = websocket_url
        self._websocket = None
        self.processor = StreamingWhisperLPC(
            sr=24000,
            whisper_volume=0.60,  # 0.15 = very soft | 0.28 = natural | 0.45 = loud
            lpc_order=18,
            bw_gamma=0.985,  # 0.97 = very breathy | 0.985 = natural | 0.995 = tight
        )

        self._settings = {
            "language": self.language_to_service_language(params.language) if params.language else "Auto",
            "ref_audio": None,
            "ref_text": params.ref_text,
            "x_vector_only_mode": params.x_vector_only_mode,
            "chunk_size": params.chunk_size,
            "speed": params.speed,
        }
        
        # Voice caching - server returns voice_id after first request
        self._cached_voice_id: Optional[str] = None
        
        # Current context_id for the active TTS generation
        self._current_context_id: Optional[str] = None
        
        # Background reader task
        self._reader_task: Optional[asyncio.Task] = None
        
        # Queue for received messages (both audio and JSON) for the current context
        self._recv_queue: asyncio.Queue = asyncio.Queue()
        
        # Load reference audio if provided
        if params.ref_audio:
            self.set_reference_audio(params.ref_audio, params.ref_text)

    def can_generate_metrics(self) -> bool:
        return True

    async def _process_text_frame(self, frame: TextFrame):
        text: Optional[str] = None
        if not self._aggregate_sentences:
            text = frame.text
        else:
            result = await self._text_aggregator.aggregate(frame.text)
            self._aggregated_text_includes_inter_frame_spaces = frame.includes_inter_frame_spaces

        if result:
            if isinstance(result, tuple):
                sentence, needs_pause = result
            else:
                sentence = result
                needs_pause = False

            if needs_pause:
                await self._inject_silence(0.5)

            await self._push_tts_frames(sentence, includes_inter_frame_spaces=False)

    async def _inject_silence(self, seconds: float):
        silence_bytes = int(self.sample_rate * seconds * 2) 
        silence = b"\x00" * silence_bytes

        silence_frame = TTSAudioRawFrame(
            audio=silence,
            sample_rate=self.sample_rate,
            num_channels=1,
        )

        await self.push_frame(silence_frame)

    def language_to_service_language(self, language: Language) -> Optional[str]:
        return language_to_qwen3_language(language)

    def set_reference_audio(
        self,
        ref_audio: Union[str, bytes, Path],
        ref_text: Optional[str] = None,
    ):
        """Set the reference audio for voice cloning."""
        ref_audio_b64: str
        
        if isinstance(ref_audio, bytes):
            ref_audio_b64 = base64.b64encode(ref_audio).decode()
        elif isinstance(ref_audio, Path):
            if not ref_audio.exists():
                raise FileNotFoundError(f"Reference audio file not found: {ref_audio}")
            with open(ref_audio, "rb") as f:
                ref_audio_b64 = base64.b64encode(f.read()).decode()
        elif isinstance(ref_audio, str):
            if ref_audio.startswith("/") or ref_audio.startswith("./") or ref_audio.startswith(".."):
                path = Path(ref_audio)
                if not path.exists():
                    raise FileNotFoundError(f"Reference audio file not found: {ref_audio}")
                with open(path, "rb") as f:
                    ref_audio_b64 = base64.b64encode(f.read()).decode()
            elif ref_audio.endswith((".wav", ".mp3", ".flac", ".ogg", ".m4a")):
                path = Path(ref_audio)
                if not path.exists():
                    raise FileNotFoundError(f"Reference audio file not found: {ref_audio}")
                with open(path, "rb") as f:
                    ref_audio_b64 = base64.b64encode(f.read()).decode()
            elif ref_audio.startswith("data:"):
                if ";base64," in ref_audio:
                    ref_audio_b64 = ref_audio.split(";base64,")[1]
                else:
                    ref_audio_b64 = ref_audio
            else:
                ref_audio_b64 = ref_audio
        else:
            raise TypeError(f"ref_audio must be str, bytes, or Path, got {type(ref_audio)}")

        logger.info(f"Reference audio set ({len(ref_audio_b64)} chars)")
        self._settings["ref_audio"] = ref_audio_b64
        self._settings["ref_text"] = ref_text
        self._cached_voice_id = None

    async def set_x_vector_only_mode(self, enabled: bool):
        logger.info(f"Setting x_vector_only_mode to: [{enabled}]")
        self._settings["x_vector_only_mode"] = enabled
        self._cached_voice_id = None

    async def set_speed(self, speed: float):
        logger.info(f"Switching TTS speed to: [{speed}]")
        self._settings["speed"] = speed

    def clear_voice_cache(self):
        """Clear cached voice_id, forcing ref_audio to be sent on next request."""
        logger.debug("Clearing cached voice_id")
        self._cached_voice_id = None

    async def start(self, frame: StartFrame):
        """Connect websocket when pipeline starts."""
        await super().start(frame)
        await self._connect_websocket()

    async def stop(self, frame: EndFrame):
        """Clean up websocket when pipeline stops."""
        await super().stop(frame)
        await self._disconnect_websocket()

    async def cancel(self, frame: CancelFrame):
        """Clean up websocket when pipeline is cancelled."""
        await super().cancel(frame)
        await self._disconnect_websocket()

    async def _handle_interruption(self, frame: InterruptionFrame, direction: FrameDirection):
        """Handle interruption WITHOUT disconnecting the WebSocket.
        """
        await super()._handle_interruption(frame, direction)
        self._current_context_id = None

    async def _connect_websocket(self):
        """Connect to the Qwen3-TTS WebSocket service and start reader."""
        try:
            if self._websocket and self._websocket.state is State.OPEN:
                return
            logger.debug(f"Connecting to Qwen3-TTS Voice Clone at {self._websocket_url}")
            self._websocket = await websocket_connect(
                self._websocket_url,
                open_timeout=120,
                close_timeout=10,
            )
            logger.info("Connected to Qwen3-TTS Voice Clone WebSocket service")
            
        except Exception as e:
            logger.error(f"Failed to connect to Qwen3-TTS Voice Clone: {e}")
            self._websocket = None
            raise

    async def _disconnect_websocket(self):
        """Disconnect from the Qwen3-TTS WebSocket service."""
        try:
            if self._websocket:
                logger.debug("Disconnecting from Qwen3-TTS Voice Clone")
                await self._websocket.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
        finally:
            self._websocket = None
            self._cached_voice_id = None  # Server cache is per-connection
            self._current_context_id = None

    async def _stop_reader(self):
        """Stop the background reader task."""
        if self._reader_task:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except asyncio.CancelledError:
                pass
            self._reader_task = None

    def _build_request(self, text: str, context_id: str) -> dict:
        """Build the WebSocket request message with context_id and voice caching."""
        base = {
            "context_id": context_id,
            "text": text,
            "language": self._settings["language"],
            "chunk_size": self._settings["chunk_size"],
            "speed": self._settings["speed"],
        }

        logger.debug("Using server default voice")
        return base

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        """Generate speech from text using Qwen3-TTS Voice Clone streaming API."""

        logger.debug(f"{self}: Generating TTS [{text}]")

        # whisper_required, text = extract_whisper_block(text)

        try:
            if not self._websocket or self._websocket.state is not State.OPEN:
                await self._connect_websocket()

            context_id = str(uuid.uuid4())
            self._current_context_id = context_id

            await self.start_ttfb_metrics()

            request = self._build_request(text, context_id)
            await self._websocket.send(json.dumps(request))
            await self.start_tts_usage_metrics(text)

            async for message in self._websocket:

                if self._current_context_id != context_id:
                    yield TTSStoppedFrame()
                    return

                # Binary = audio
                if isinstance(message, bytes):

                    if len(message) <= CONTEXT_ID_SIZE:
                        continue

                    msg_context_id = (
                        message[:CONTEXT_ID_SIZE]
                        .rstrip(b"\0")
                        .decode("ascii", errors="ignore")
                    )

                    if msg_context_id != context_id:
                        continue

                    await self.stop_ttfb_metrics()

                    processed = message[CONTEXT_ID_SIZE:]
                    # if whisper_required:
                    #     logger.info(f"Whisper required: True")
                    #     processed = self.processor.process(message[CONTEXT_ID_SIZE:])

                    yield TTSAudioRawFrame(
                        audio=processed,
                        sample_rate=self.sample_rate,
                        num_channels=1,
                    )
                    continue

                # JSON message
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from server: {message}")
                    continue

                msg_context_id = data.get("context_id", "")
                msg_type = data.get("type", "")

                if msg_context_id and msg_context_id != context_id:
                    continue

                if msg_type == "started":
                    yield TTSStartedFrame()

                elif msg_type == "done":
                    yield TTSStoppedFrame()
                    return

                elif msg_type == "interrupted":
                    logger.debug(
                        f"Server confirmed interrupt for context: {msg_context_id[:8]}"
                    )
                    yield TTSStoppedFrame()
                    return

                elif msg_type == "error":
                    error_msg = data.get("message", "Unknown error")
                    logger.error(f"Qwen3-TTS Voice Clone error: {error_msg}")
                    yield ErrorFrame(error=error_msg)
                    yield TTSStoppedFrame()
                    return

        except Exception as e:
            logger.error(f"Qwen3-TTS Voice Clone generation error: {e}")
            yield ErrorFrame(error=f"Unknown error occurred: {e}")
            yield TTSStoppedFrame()
            await self._disconnect_websocket()