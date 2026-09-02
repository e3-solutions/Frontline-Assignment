"""Audio storage operations for call recordings.

Handles uploading audio files to Supabase Storage and storing URLs in database.
"""

import datetime
import io
import wave

from loguru import logger

from src import SupabaseService


async def save_audio_to_supabase(
    audio: bytes, call_id: str, sample_rate: int, num_channels: int
) -> str | None:
    """Save audio to Supabase Storage and return the public URL.

    Args:
        audio: Audio data bytes
        call_id: Call ID for filename
        sample_rate: Audio sample rate
        num_channels: Number of audio channels

    Returns:
        Public URL of the uploaded audio file, or None if upload fails
    """
    if len(audio) == 0:
        return None

    try:
        supabase = SupabaseService.get_client()
        if not supabase:
            logger.warning("Supabase not available, cannot save audio")
            return None

        # Create WAV file in memory
        with io.BytesIO() as buffer:
            with wave.open(buffer, "wb") as wf:
                wf.setsampwidth(2)
                wf.setnchannels(num_channels)
                wf.setframerate(sample_rate)
                wf.writeframes(audio)
            audio_bytes = buffer.getvalue()

        # Upload to Supabase Storage
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = f"recordings/{call_id}_{timestamp}.wav"

        supabase.storage.from_("call-recordings").upload(
            filepath, audio_bytes, file_options={"content-type": "audio/wav"}
        )

        # Get public URL
        public_url = supabase.storage.from_("call-recordings").get_public_url(filepath)
        logger.info(f"Audio uploaded to Supabase Storage: {public_url}")
        return public_url

    except Exception as e:
        logger.error(f"Error uploading audio to Supabase: {e}")
        return None


async def store_audio_url_in_call(call_id: str, audio_url: str) -> None:
    """Store audio URL in call record.

    Args:
        call_id: Call ID (UUID string)
        audio_url: Public URL of the audio file
    """
    if not audio_url:
        return

    try:
        supabase = SupabaseService.get_client()
        if not supabase:
            return

        # Update the dedicated recording_url column
        supabase.table("calls").update({"recording_url": audio_url}).eq(
            "id", call_id
        ).execute()
        logger.info(f"Stored recording URL in call record: {audio_url}")

    except Exception as e:
        logger.error(f"Failed to store recording URL in database: {e}")
