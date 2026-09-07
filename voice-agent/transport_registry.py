"""Global registry for the currently active LiveKit transport."""

from pipecat.transports.livekit.transport import LiveKitTransport

_transport: LiveKitTransport | None = None


def set_transport(transport: LiveKitTransport) -> None:
    global _transport
    _transport = transport


def get_transport() -> LiveKitTransport | None:
    return _transport
