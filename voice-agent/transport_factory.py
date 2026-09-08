"""LiveKit transport factory used by the voice pipelines."""

from pathlib import Path

from pipecat.audio.mixers.soundfile_mixer import SoundfileMixer
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.transports.livekit.transport import LiveKitParams, LiveKitTransport


class TransportFactory:
    """Create consistently configured LiveKit transports."""

    @staticmethod
    def _audio_asset_path(filename: str) -> str:
        return str(Path(__file__).parent / "static" / "audio" / filename)

    @staticmethod
    def create(
        url: str,
        token: str,
        room_name: str,
        bot_name: str = "Negotiation Agent",
    ) -> LiveKitTransport:
        """Create the full duplex transport used by a negotiation pipeline."""
        params = LiveKitParams(
            audio_in_enabled=True,
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
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3)),
        )

        # LiveKit obtains the participant identity from the access token. The
        # descriptive name is still useful for Pipecat processor names.
        return LiveKitTransport(
            url,
            token,
            room_name,
            params=params,
            input_name=f"{bot_name} input",
            output_name=f"{bot_name} output",
        )

    @staticmethod
    def create_hold_music(
        url: str,
        token: str,
        room_name: str,
        bot_name: str = "Hold Music",
    ) -> LiveKitTransport:
        """Create an output-only LiveKit transport for a hold-music pipeline."""
        return LiveKitTransport(
            url,
            token,
            room_name,
            params=LiveKitParams(
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
            input_name=f"{bot_name} input",
            output_name=f"{bot_name} output",
        )
