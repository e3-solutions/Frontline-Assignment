"""Mutable state shared by the multi-room transfer flow."""

from dataclasses import dataclass, field


@dataclass
class TransferState:
    """Provider-neutral room, participant, and negotiation transfer state."""

    # Room 1 (carrier room)
    room1_url: str | None = None
    room1_name: str | None = None
    room1_token: str | None = None
    carrier_participant_id: str | None = None
    carrier_participant_identity: str | None = None
    carrier_session_id: str | None = None

    # Room 2 (human room)
    room2_url: str | None = None
    room2_name: str | None = None
    room2_token: str | None = None
    human_participant_id: str | None = None
    human_participant_identity: str | None = None
    human_session_id: str | None = None

    # Provider-neutral call metadata
    provider_call_id: str | None = None
    telephony_provider: str | None = None

    # Phone numbers
    human_phone_number: str | None = None

    # Preserved context from Room1
    room1_messages: list = field(default_factory=list)

    # Load context from Room1 (pricing and load details for Room2)
    load_context: dict | None = None

    # Transfer metadata
    transfer_reason: str | None = None
    load_number: str | None = None
    price_asked_by_carrier: float | None = None
    best_price_offered_by_bot: float | None = None
