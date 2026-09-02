"""
Room Pool Service for Daily PSTN Calls

Pre-creates and manages a pool of Daily rooms to eliminate room creation latency.
All rooms in the pool share the same expiration time for simple management.
"""

import asyncio
import time
from collections import deque

import aiohttp
from loguru import logger
from pipecat.runner.daily import DailyRoomConfig, configure
from pipecat.transports.daily.utils import DailyRoomProperties, DailyRoomSipParams

# Room expiry configuration
ROOM_EXPIRY_HOURS = 3
ROOM_EXPIRY_SECONDS = ROOM_EXPIRY_HOURS * 60 * 60


class RoomPool:
    """Manages a pool of pre-created Daily rooms for faster call handling.

    Pre-creates rooms at startup and reuses them to eliminate room creation latency.
    All rooms expire together, so we track one timestamp for the entire pool.
    """

    def __init__(self, pool_size: int = 3):
        """Initialize the room pool.

        Args:
            pool_size: Number of rooms to pre-create and maintain in the pool
        """
        self.pool_size = pool_size
        self.available_rooms: deque[DailyRoomConfig] = deque()
        self.pool_created_at: float | None = None
        self.lock = asyncio.Lock()
        self.initialized = False
        # Track which pool generation each room belongs to (by room_url)
        # This prevents returning expired rooms from old pools
        self.room_pool_origin: dict[str, float] = {}

    async def initialize(self, session: aiohttp.ClientSession) -> None:
        """Pre-create rooms and populate the pool.

        Args:
            session: aiohttp session for making API calls
        """
        if self.initialized:
            return

        await self._create_new_pool(session)
        self.initialized = True

    def _is_pool_expired(self) -> bool:
        """Check if the entire pool has expired.

        Returns:
            bool: True if pool expired or expires soon (5min buffer)
        """
        if self.pool_created_at is None:
            return True

        time_until_expiry = (self.pool_created_at + ROOM_EXPIRY_SECONDS) - time.time()
        return time_until_expiry < 300  # 5-minute safety buffer

    async def _create_new_pool(self, session: aiohttp.ClientSession) -> None:
        """Create a fresh pool of rooms.

        Args:
            session: aiohttp session for making API calls
        """
        self.available_rooms.clear()
        self.room_pool_origin.clear()  # Clear stale room tracking
        self.pool_created_at = time.time()
        expiration_time = self.pool_created_at + ROOM_EXPIRY_SECONDS

        logger.info(
            f"Creating new room pool ({self.pool_size} rooms, expiry: {ROOM_EXPIRY_HOURS}h)"
        )

        for i in range(self.pool_size):
            try:
                room = await self._create_room(session, expiration_time)
                self.available_rooms.append(room)
            except Exception as e:
                logger.error(f"Failed to create room {i + 1}: {e}")

        logger.info(f"Pool created with {len(self.available_rooms)} rooms")

    async def _create_room(
        self,
        session: aiohttp.ClientSession,
        expiration_time: float,
        caller_phone: str | None = None,
    ) -> DailyRoomConfig:
        """Create a new Daily room configured for PSTN dial-in.

        Args:
            session: aiohttp session for making API calls
            expiration_time: Unix timestamp when room expires
            caller_phone: Optional caller phone number for display name

        Returns:
            DailyRoomConfig: Configuration object with room_url and token
        """
        # Create custom room properties optimized for voice-only PSTN calls
        room_properties = DailyRoomProperties(
            exp=expiration_time,
            eject_at_room_exp=True,
            enable_dialout=True,
            start_video_off=True,
            enable_chat=False,
            enable_emoji_reactions=False,
            enable_prejoin_ui=False,
            sip=DailyRoomSipParams(
                display_name=caller_phone or "Pool Room",
                video=False,
                sip_mode="dial-in",
                num_endpoints=3,
            ),
        )

        return await configure(
            session,
            sip_caller_phone=caller_phone,
            room_properties=room_properties,
            # Token must match room expiration to avoid exp-token errors
            token_exp_duration=float(ROOM_EXPIRY_HOURS),
        )

    async def get_room(
        self, session: aiohttp.ClientSession, caller_phone: str | None = None
    ) -> DailyRoomConfig:
        """Get a room from the pool, creating new pool if expired.

        Args:
            session: aiohttp session for making API calls
            caller_phone: Optional caller phone number (unused, for compatibility)

        Returns:
            DailyRoomConfig: Room configuration ready for use
        """
        async with self.lock:
            # If pool expired, create entirely new pool
            if self._is_pool_expired():
                logger.info("Pool expired, creating new pool")
                await self._create_new_pool(session)

            # Get room from pool
            if self.available_rooms:
                room = self.available_rooms.popleft()
                # Track which pool this room belongs to
                self.room_pool_origin[room.room_url] = self.pool_created_at
                return room

        # Should never happen, but fallback to creating single room
        logger.error("Pool empty after creation - creating emergency room")
        expiration_time = time.time() + ROOM_EXPIRY_SECONDS
        return await self._create_room(session, expiration_time)

    async def return_room(self, room: DailyRoomConfig) -> None:
        """Return a room to the pool if not expired.

        Args:
            room: Room configuration to return to the pool
        """
        async with self.lock:
            # Check if this room belongs to the current pool generation
            room_origin = self.room_pool_origin.pop(room.room_url, None)
            if room_origin != self.pool_created_at:
                logger.debug(f"Discarding room from old pool: {room.room_url}")
                return

            # Don't return if pool expired (room is stale)
            if self._is_pool_expired():
                return

            # Don't exceed pool size
            if len(self.available_rooms) < self.pool_size:
                self.available_rooms.append(room)


# Global room pool instance
_room_pool: RoomPool | None = None


def get_room_pool(pool_size: int = 3) -> RoomPool:
    """Get or create the global room pool instance.

    Args:
        pool_size: Number of rooms to maintain in the pool

    Returns:
        RoomPool: The global room pool instance
    """
    global _room_pool
    if _room_pool is None:
        _room_pool = RoomPool(pool_size=pool_size)
    return _room_pool
