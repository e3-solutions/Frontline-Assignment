"""Global transport registry.

Single Responsibility: Store and retrieve the current DailyTransport instance.
"""

from pipecat.transports.daily.transport import DailyTransport
from typing import Optional

_transport: Optional[DailyTransport] = None


def set_transport(t: DailyTransport):
    global _transport
    _transport = t


def get_transport() -> Optional[DailyTransport]:
    return _transport