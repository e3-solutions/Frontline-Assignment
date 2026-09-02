"""DailyTransport factory.

Single Responsibility: Create configured DailyTransport instances.
"""

import os
from pathlib import Path

from pipecat.audio.mixers.soundfile_mixer import SoundfileMixer
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.transports.daily.transport import (
    DailyDialinSettings,
    DailyParams,
    DailyTransport,
)
from dotenv import load_dotenv

load_dotenv(override=True)


class TransportFactory:
    """Creates DailyTransport instances with standard configuration."""

    @staticmethod
    def _audio_asset_path(filename: str) -> str:
        """Resolve audio assets relative to the voice-agent app directory."""
        return str(Path(__file__).parent / "static" / "audio" / filename)

    @staticmethod
    def create(
        room_url: str,
        token: str,
        bot_name: str = "Negotiation Agent",
        daily_dialin_settings: DailyDialinSettings = None,
    ) -> DailyTransport:
        """Create a DailyTransport with standard audio settings.

        Args:
            room_url: Daily room URL to join
            token: Authentication token
            bot_name: Display name for the bot
            dialin_settings: Optional dial-in settings for PSTN calls

        Returns:
            Configured DailyTransport instance

        Parameters
        ----------
        room_url
        token
        bot_name
        daily_dialin_settings
        """
        params = DailyParams(
            api_key=os.getenv("DAILY_API_KEY"),
            audio_in_enabled=True,
            dialin_settings=daily_dialin_settings,
            audio_in_passthrough=True,
            audio_out_enabled=True,
            audio_out_mixer=SoundfileMixer(
                sound_files={
                    "office": TransportFactory._audio_asset_path("office_noise.wav")
                },
                default_sound="office",
                volume=0.1,
                loop=True,
            ),
            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(stop_secs=0.3)
            ),
        )

        return DailyTransport(
            room_url,
            token,
            bot_name,
            params=params,
        )

    @staticmethod
    def create_hold_music(
        room_url: str,
        token: str,
        daily_dialin_settings: DailyDialinSettings = None,
    ) -> DailyTransport:
        """Create a minimal DailyTransport that only plays hold music.

        Args:
            room_url: Daily room URL to join
            token: Authentication token

        Returns:
            DailyTransport configured for hold music only

        Parameters
        ----------
        room_url
        token
        daily_dialin_settings
        """
        return DailyTransport(
            room_url,
            token,
            "Hold Music",
            params=DailyParams(
                api_key=os.getenv("DAILY_API_KEY"),
                dialin_settings=daily_dialin_settings,
                audio_in_enabled=False,
                audio_out_enabled=True,
                audio_out_mixer=SoundfileMixer(
                    sound_files={
                        "hold": TransportFactory._audio_asset_path("hold_music.mp3")
                    },
                    default_sound="hold",
                    volume=0.3,
                    loop=True,
                ),
            ),
        )