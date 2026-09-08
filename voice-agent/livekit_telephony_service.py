"""LiveKit server-SDK boundary for rooms, SIP calls, and warm transfers.

The conversational agent only deals in plain Python values.  Keeping LiveKit
objects behind this boundary makes the call lifecycle testable without a
network connection and keeps provider concerns out of the prompt/tool layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
from typing import Any, Protocol
from uuid import uuid4

from telephony_config import LiveKitTelephonyConfig, load_livekit_telephony_config


@dataclass(frozen=True)
class RoomCredentials:
    name: str
    token: str


@dataclass(frozen=True)
class SipParticipant:
    identity: str
    participant_id: str | None
    provider_call_id: str | None


class ParticipantMoveOutcomeUnknown(RuntimeError):
    """Raised when reconciliation cannot prove where the participant landed."""


class LiveKitGateway(Protocol):
    async def create_room(self, room_name: str) -> None: ...

    async def delete_room(self, room_name: str) -> None: ...

    async def create_sip_participant(
        self,
        *,
        room_name: str,
        phone_number: str,
        participant_identity: str,
        participant_name: str,
    ) -> SipParticipant: ...

    async def move_participant(
        self,
        *,
        source_room: str,
        destination_room: str,
        participant_identity: str,
    ) -> None: ...

    async def remove_participant(
        self, *, room_name: str, participant_identity: str
    ) -> None: ...

    async def participant_exists(
        self, *, room_name: str, participant_identity: str
    ) -> bool: ...


class LiveKitSdkGateway:
    """Small adapter over ``livekit-api`` with no SDK values escaping."""

    def __init__(self, config: LiveKitTelephonyConfig) -> None:
        self._config = config

    def _client(self):
        from livekit import api

        return api.LiveKitAPI(
            url=self._config.livekit_url,
            api_key=self._config.livekit_api_key,
            api_secret=self._config.livekit_api_secret,
        )

    async def create_room(self, room_name: str) -> None:
        from livekit import api

        async with self._client() as client:
            await client.room.create_room(api.CreateRoomRequest(name=room_name))

    async def delete_room(self, room_name: str) -> None:
        from livekit import api

        async with self._client() as client:
            try:
                await client.room.delete_room(api.DeleteRoomRequest(room=room_name))
            except Exception as exc:
                if not _is_not_found(exc):
                    raise

    async def create_sip_participant(
        self,
        *,
        room_name: str,
        phone_number: str,
        participant_identity: str,
        participant_name: str,
    ) -> SipParticipant:
        from livekit import api

        async with self._client() as client:
            result = await client.sip.create_sip_participant(
                api.CreateSIPParticipantRequest(
                    sip_trunk_id=self._config.livekit_outbound_trunk_id,
                    sip_call_to=phone_number,
                    sip_number=self._config.livekit_outbound_number,
                    room_name=room_name,
                    participant_identity=participant_identity,
                    participant_name=participant_name,
                    display_name=participant_name,
                    wait_until_answered=True,
                )
            )
        return SipParticipant(
            identity=participant_identity,
            participant_id=_string_attr(result, "participant_id", "participant_sid"),
            provider_call_id=_string_attr(result, "sip_call_id", "call_id"),
        )

    async def move_participant(
        self,
        *,
        source_room: str,
        destination_room: str,
        participant_identity: str,
    ) -> None:
        from livekit import api

        async with self._client() as client:
            await client.room.move_participant(
                api.MoveParticipantRequest(
                    room=source_room,
                    identity=participant_identity,
                    destination_room=destination_room,
                )
            )

    async def remove_participant(
        self, *, room_name: str, participant_identity: str
    ) -> None:
        from livekit import api

        async with self._client() as client:
            try:
                await client.room.remove_participant(
                    api.RoomParticipantIdentity(
                        room=room_name,
                        identity=participant_identity,
                    )
                )
            except Exception as exc:
                if not _is_not_found(exc):
                    raise

    async def participant_exists(
        self, *, room_name: str, participant_identity: str
    ) -> bool:
        from livekit import api

        async with self._client() as client:
            try:
                await client.room.get_participant(
                    api.RoomParticipantIdentity(
                        room=room_name,
                        identity=participant_identity,
                    )
                )
                return True
            except Exception as exc:
                if _is_not_found(exc):
                    return False
                raise


class LiveKitTelephonyService:
    """Application-facing control surface for LiveKit/Telnyx calls."""

    def __init__(
        self,
        config: LiveKitTelephonyConfig | None = None,
        gateway: LiveKitGateway | None = None,
    ) -> None:
        self.config = (config or load_livekit_telephony_config()).require_valid()
        self.gateway = gateway or LiveKitSdkGateway(self.config)

    def issue_room_token(self, room_name: str, identity: str) -> str:
        from livekit import api

        return (
            api.AccessToken(
                self.config.livekit_api_key,
                self.config.livekit_api_secret,
            )
            .with_identity(identity)
            .with_name(identity)
            .with_grants(api.VideoGrants(room_join=True, room=room_name))
            .to_jwt()
        )

    async def create_room(
        self,
        *,
        purpose: str,
        bot_identity: str = "negotiation-agent",
    ) -> RoomCredentials:
        room_name = f"{self.config.room_prefix}-{purpose}-{uuid4().hex[:12]}"
        await self.gateway.create_room(room_name)
        return RoomCredentials(
            name=room_name,
            token=self.issue_room_token(room_name, bot_identity),
        )

    async def delete_room(self, room_name: str) -> None:
        await self.gateway.delete_room(room_name)

    async def dial_phone(
        self,
        *,
        room_name: str,
        phone_number: str,
        role: str,
        display_name: str,
        participant_identity: str | None = None,
    ) -> SipParticipant:
        identity = participant_identity or f"{role}-{uuid4().hex[:12]}"
        return await self.gateway.create_sip_participant(
            room_name=room_name,
            phone_number=phone_number,
            participant_identity=identity,
            participant_name=display_name,
        )

    async def move_participant(
        self,
        *,
        source_room: str,
        destination_room: str,
        participant_identity: str,
    ) -> None:
        await self.gateway.move_participant(
            source_room=source_room,
            destination_room=destination_room,
            participant_identity=participant_identity,
        )

    async def participant_exists(
        self, *, room_name: str, participant_identity: str
    ) -> bool:
        return await self.gateway.participant_exists(
            room_name=room_name,
            participant_identity=participant_identity,
        )

    async def wait_for_participant(
        self,
        *,
        room_name: str,
        participant_identity: str,
        timeout: float,
        poll_interval: float = 0.25,
    ) -> bool:
        """Wait until LiveKit confirms a participant is present in a room."""

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        while True:
            if await self.participant_exists(
                room_name=room_name,
                participant_identity=participant_identity,
            ):
                return True
            remaining = deadline - loop.time()
            if remaining <= 0:
                return False
            await asyncio.sleep(min(poll_interval, remaining))

    async def move_participant_verified(
        self,
        *,
        source_room: str,
        destination_room: str,
        participant_identity: str,
        timeout: float,
    ) -> None:
        """Move once, reconcile, and retry only after a conclusive source state.

        A participant found in neither room is an ambiguous provider outcome. The
        method never repeats that move because a duplicate request could race a
        delayed successful handoff.
        """

        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        for move_number in (1, 2):
            move_error: Exception | None = None
            try:
                await self.move_participant(
                    source_room=source_room,
                    destination_room=destination_room,
                    participant_identity=participant_identity,
                )
            except Exception as exc:
                move_error = exc

            remaining = max(0.0, deadline - loop.time())
            reconcile_window = (
                remaining / 2
                if move_number == 1 and move_error is not None
                else remaining
            )
            try:
                if reconcile_window > 0 and await self.wait_for_participant(
                    room_name=destination_room,
                    participant_identity=participant_identity,
                    timeout=reconcile_window,
                ):
                    return

                in_source = await self.participant_exists(
                    room_name=source_room,
                    participant_identity=participant_identity,
                )
            except Exception as exc:
                raise ParticipantMoveOutcomeUnknown(
                    "Participant reconciliation failed after move submission"
                ) from exc
            if (
                in_source
                and move_number == 1
                and move_error is not None
                and deadline - loop.time() > 0
            ):
                continue
            if in_source:
                if move_error is not None:
                    raise move_error
                raise RuntimeError("Broker remained in the consultation room")

            if move_error is not None:
                raise ParticipantMoveOutcomeUnknown(
                    "Broker move failed and participant location is unknown"
                ) from move_error
            raise ParticipantMoveOutcomeUnknown(
                "Broker did not arrive and participant location is unknown"
            )

    async def remove_participant(
        self, *, room_name: str, participant_identity: str
    ) -> None:
        await self.gateway.remove_participant(
            room_name=room_name,
            participant_identity=participant_identity,
        )


def _string_attr(value: Any, *names: str) -> str | None:
    for name in names:
        candidate = str(getattr(value, name, "") or "").strip()
        if candidate:
            return candidate
    return None


def _is_not_found(exc: Exception) -> bool:
    status = getattr(exc, "status", None) or getattr(exc, "status_code", None)
    text = str(exc).lower()
    return status == 404 or "not found" in text or "not_found" in text
