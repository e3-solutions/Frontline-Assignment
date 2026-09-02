"""Webhook server to handle Daily PSTN calls and start the voice bot.

This server provides endpoints for handling Daily PSTN webhooks and starting the bot.
The server automatically detects the environment (local vs production) and routes
bot starting requests accordingly:
- Local: Uses internal /start endpoint
- Production: Calls Pipecat Cloud API

All call data (room_url, token, callId, callDomain) flows through the body parameter
to ensure consistency between local and cloud deployments.
"""

import os
from contextlib import asynccontextmanager

import aiohttp
import uvicorn
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from fastapi.staticfiles import StaticFiles

from server_utils import (
    AgentRequest,
    call_data_from_request,
    create_daily_room,
    start_bot_local,
    return_room_to_pool,
)
from pipecat.runner.daily import DailyRoomConfig
from room_pool_service import get_room_pool

load_dotenv(override=True)

_request = None
_room_config = None

def set_request_room_config(request, room_config: DailyRoomConfig):
    global _request, _room_config
    _request = request
    _room_config = room_config

def get_request_room_config():
    return _request, _room_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle and shared resources.

    Creates a shared aiohttp session for making HTTP requests to bot endpoints.
    Pre-initializes the room pool to eliminate room creation latency.
    """
    # Create shared HTTP session for bot API calls
    app.state.http_session = aiohttp.ClientSession()
    logger.info("Created shared HTTP session")

    # Initialize room pool at startup
    pool_size = int(os.getenv("ROOM_POOL_SIZE", "3"))
    room_pool = get_room_pool(pool_size=pool_size)
    await room_pool.initialize(app.state.http_session)
    logger.info(f"Room pool initialized with {pool_size} pre-created rooms")

    yield
    # Clean up: close the session on shutdown
    await app.state.http_session.close()
    logger.info("Closed shared HTTP session")


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def _start_bot_async(agent_request: AgentRequest, session: aiohttp.ClientSession):
    """Start bot asynchronously in background.

    Args:
        agent_request: Agent configuration with room_url, token, and call details
        session: Shared aiohttp session for making HTTP requests
    """
    try:
        await start_bot_local(agent_request, session)
    except Exception as e:
        logger.error(f"Error starting bot asynchronously: {e}")


@app.post("/daily-webhook")
async def handle_incoming_daily_webhook(
    request: Request, background_tasks: BackgroundTasks
) -> JSONResponse:
    """Handle incoming Daily PSTN call webhook.

    This endpoint:
    1. Receives Daily webhook data for incoming PSTN calls
    2. Gets a Daily room from the pool (pre-created for zero latency)
    3. Starts the bot asynchronously (locally or via Pipecat Cloud based on ENV)
    4. Returns room details immediately for the caller

    Args:
        request: FastAPI request containing Daily webhook data
        background_tasks: FastAPI background tasks for async bot startup

    Returns:
        JSONResponse: Success status with room_url and token (returns immediately)

    Raises:
        HTTPException: If webhook data is invalid or room retrieval fails
    """

    logger.debug("Received webhook from Daily")


    call_data = await call_data_from_request(request)

    daily_room_config = await create_daily_room(
        call_data, request.app.state.http_session
    )

    logger.info(f" ****************************** SIP ENDPOINT **************************: {daily_room_config.sip_endpoint}")

    set_request_room_config(request, daily_room_config)

    agent_request = AgentRequest(
        room_url=daily_room_config.room_url,
        token=daily_room_config.token,
        call_id=call_data.call_id,
        call_domain=call_data.call_domain,
        caller_phone=call_data.from_phone,
        bot_phone=call_data.to_phone,
        sip_endpoint=daily_room_config.sip_endpoint,
        room_config={
            "room_url": daily_room_config.room_url,
            "token": daily_room_config.token,
        },
    )

    # Start bot asynchronously in background - don't block webhook response
    background_tasks.add_task(
        _start_bot_async, agent_request, request.app.state.http_session
    )

    # Return immediately - bot will join in background
    # Room will be automatically reused for future calls
    return JSONResponse(
        {
            "status": "success",
            "room_url": daily_room_config.room_url,
            "token": daily_room_config.token,
        }
    )


@app.get("/")
async def root():
    """Root endpoint for testing.

    Returns:
        dict: Simple greeting message
    """
    return {"message": "Opa, boa tarde"}


@app.get("/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Status indicating server health
    """
    return {"status": "healthy"}


@app.post("/return-room")
async def return_room(request: Request):
    """Return a room to the pool when a call ends.

    Called by the bot process to return rooms via HTTP since bot and
    webhook server run in separate processes.

    Args:
        request: FastAPI request containing room_url and token

    Returns:
        dict: Status indicating success
    """
    data = await request.json()
    room = DailyRoomConfig(room_url=data["room_url"], token=data["token"])
    await return_room_to_pool(room)
    logger.info(f"Room returned to pool: {data['room_url']}")
    return {"status": "success"}


if __name__ == "__main__":
    # Run the server
    port = int(os.getenv("PORT", "8080"))
    logger.info(f"Starting server on port {port}")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
