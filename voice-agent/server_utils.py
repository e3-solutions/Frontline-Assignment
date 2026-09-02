"""Utilities for Daily PSTN webhook handling and bot management.

This module provides data models and functions for:
- Parsing Daily PSTN webhook data
- Creating Daily rooms for incoming calls
- Starting bots in production (Pipecat Cloud) or local development mode
"""

import os

import aiohttp
from fastapi import HTTPException, Request
from loguru import logger
from pipecat.runner.daily import DailyRoomConfig
from pydantic import BaseModel

from room_pool_service import get_room_pool


class DailyCallData(BaseModel):
    """Data received from Daily PSTN webhook.

    Attributes:
        from_phone: The caller's phone number
        to_phone: The dialed phone number
        call_id: Unique identifier for the call
        call_domain: Daily domain for the call
    """

    from_phone: str
    to_phone: str
    call_id: str
    call_domain: str


class AgentRequest(BaseModel):
    """Request data sent to bot start endpoint.

    Add any custom data here needed for the agent. For example,
    you may add an API call to your backend to get the customer's
    name or other information.

    Attributes:
        room_url: Daily room URL for the bot to join
        token: Authentication token for the Daily room
        call_id: Unique identifier for the call
        call_domain: Daily domain for the call
        caller_phone: Phone number of the caller (optional)
        bot_phone: Phone number the caller dialed (optional)
        room_config: Daily room config for returning to pool (optional)
    """

    room_url: str
    token: str
    call_id: str
    call_domain: str
    caller_phone: str = None
    bot_phone: str = None
    room_config: dict = None
    sip_endpoint: str = None


async def call_data_from_request(request: Request) -> DailyCallData:
    """Parse and validate Daily PSTN webhook data from incoming request.

    Args:
        request: FastAPI request object containing webhook data

    Returns:
        DailyCallData: Parsed and validated call data

    Raises:
        HTTPException: If required fields are missing from the webhook data
    """
    data = await request.json()

    if not all(key in data for key in ["From", "To", "callId", "callDomain"]):
        raise HTTPException(
            status_code=400,
            detail="Missing properties 'From', 'To', 'callId', 'callDomain'",
        )

    return DailyCallData(
        from_phone=str(data.get("From")),
        to_phone=str(data.get("To")),
        call_id=data.get("callId"),
        call_domain=data.get("callDomain"),
    )


async def create_daily_room(
    call_data: DailyCallData, session: aiohttp.ClientSession
) -> DailyRoomConfig:
    """Get a Daily room from the pool or create a new one if pool is empty.

    Uses pre-created rooms from the pool to eliminate room creation latency.

    Args:
        call_data: Call data containing caller phone number and call details
        session: Shared aiohttp session for making HTTP requests

    Returns:
        DailyRoomConfig: Configuration object with room_url and token

    Raises:
        HTTPException: If room retrieval/creation fails
    """
    try:
        pool = get_room_pool()
        if not pool.initialized:
            await pool.initialize(session)

        return await pool.get_room(session, caller_phone=call_data.from_phone)
    except Exception as e:
        logger.error(f"Error getting Daily room: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get Daily room: {e!s}")


async def return_room_to_pool(room: dict | DailyRoomConfig) -> None:
    """Return a room to the pool after a call ends.

    Args:
        room: Room configuration to return to the pool (dict or DailyRoomConfig)
    """
    try:
        pool = get_room_pool()
        # Convert dict to DailyRoomConfig if needed (for bot compatibility)
        if isinstance(room, dict):
            room = DailyRoomConfig(
                room_url=room.get("room_url", ""), token=room.get("token", "")
            )
        await pool.return_room(room)
    except Exception as e:
        logger.warning(f"Failed to return room to pool: {e}")


async def start_bot_local(agent_request: AgentRequest, session: aiohttp.ClientSession):
    """Start the bot via local /start endpoint for development.

    Args:
        agent_request: Agent configuration with room_url, token, and call details
        session: Shared aiohttp session for making HTTP requests

    Raises:
        HTTPException: If LOCAL_BOT_URL is not set or API call fails
    """
    local_bot_url = os.getenv("LOCAL_BOT_URL", "http://localhost:7860")
    body_data = agent_request.model_dump(exclude_none=True)

    async with session.post(
        f"{local_bot_url}/start",
        headers={"Content-Type": "application/json"},
        json={
            "createDailyRoom": False,
            "body": body_data,
        },
    ) as response:
        if response.status != 200:
            error_text = await response.text()
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start bot via local /start endpoint: {error_text}",
            )
