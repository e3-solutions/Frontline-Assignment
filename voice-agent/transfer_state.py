"""Transfer state shared across the transfer flow.

Single Responsibility: Hold all mutable state related to multi-room transfer.
"""

from dataclasses import dataclass, field
from typing import Optional
from pipecat.transports.daily.transport import (
    DailyDialinSettings,
)


@dataclass
class TransferState:
    """Immutable-ish container for all transfer-related state."""

    # Room 1 (carrier room)
    room1_url: Optional[str] = None
    room1_token: Optional[str] = None
    carrier_participant_id: Optional[str] = None
    carrier_session_id: Optional[str] = None

    # Room 2 (human room)
    room2_url: Optional[str] = None
    room2_token: Optional[str] = None
    human_participant_id: Optional[str] = None
    human_session_id: Optional[str] = None

    # Phone numbers
    human_phone_number: Optional[str] = None

    # Preserved context from Room1
    room1_messages: list = field(default_factory=list)

    # Load context from Room1 (pricing and load details for Room2)
    load_context: Optional[dict] = None

    # Transfer metadata
    transfer_reason: Optional[str] = None
    load_number: Optional[str] = None
    price_asked_by_carrier: Optional[float] = None
    best_price_offered_by_bot: Optional[float] = None

    daily_dialin_settings: Optional[DailyDialinSettings] = None

    call_domain: Optional[str] = None
    sip_endpoint: Optional[str] = None