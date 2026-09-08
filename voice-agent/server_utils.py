"""Transport-neutral models and BotRunner client for LiveKit calls."""

from __future__ import annotations

import aiohttp
from fastapi import HTTPException
from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Everything the BotRunner needs to join one LiveKit call."""

    livekit_url: str
    room_name: str
    token: str
    caller_phone: str | None = None
    bot_phone: str | None = None
    provider_call_id: str | None = None
    participant_identity: str | None = None
    participant_sid: str | None = None


class OutboundCallRequest(BaseModel):
    """Request to place a carrier call through the outbound SIP trunk."""

    to_phone: str = Field(min_length=2)
    from_phone: str = Field(min_length=2)


async def start_bot_local(
    agent_request: AgentRequest,
    session: aiohttp.ClientSession,
    *,
    bot_url: str,
) -> None:
    """Start the local BotRunner and surface a bounded ingress error."""

    try:
        async with session.post(
            f"{bot_url.rstrip('/')}/start",
            headers={"Content-Type": "application/json"},
            json={"body": agent_request.model_dump(exclude_none=True)},
        ) as response:
            if response.status not in {200, 202}:
                detail = (await response.text())[:500]
                raise HTTPException(
                    status_code=503,
                    detail=f"BotRunner rejected the call: {detail}",
                )
    except HTTPException:
        raise
    except (aiohttp.ClientError, TimeoutError) as exc:
        raise HTTPException(
            status_code=503,
            detail="BotRunner is unavailable",
        ) from exc
