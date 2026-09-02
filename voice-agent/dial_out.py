import aiohttp
import os
from loguru import logger


async def dial_human_into_room(room_name: str, phone_number: str, daily_api_key: str) -> str:
    """
    Dials a human phone number into an existing Daily room.
    Returns participant ID if successful.
    """

    logger.info(f"Dialing human into room {room_name}")

    if not daily_api_key:
        raise RuntimeError("DAILY_API_KEY not set")

    url = f"https://api.daily.co/v1/rooms/{room_name}/dialOut/start"

    headers = {
        "Authorization": f"Bearer {daily_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "phoneNumber": phone_number
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"dialOut failed: {error_text}")
                raise RuntimeError(error_text)

            data = await response.json()
            participant_id = data.get("id")

            logger.info(f"Human dialed into room {room_name}, participant={participant_id}")
            return participant_id


async def enable_dialout_for_room(room_name: str, daily_api_key: str):
    url = f"https://api.daily.co/v1/rooms/{room_name}"

    logger.info(f"Enabling dialout for room {room_name}")
    headers = {
        "Authorization": f"Bearer {daily_api_key}",
        "Content-Type": "application/json",
    }
    payload = {"properties": {"enable_dialout": True}}

    async with aiohttp.ClientSession() as session:
        async with session.patch(url, json=payload, headers=headers) as response:
            return response.status == 200