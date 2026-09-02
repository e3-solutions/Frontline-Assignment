"""Daily REST API client.

Single Responsibility: All HTTP calls to Daily's REST API.
Handles SIP REFER, dialout, room creation/destruction.
"""

import os
import aiohttp
from loguru import logger
from typing import Optional


DAILY_API_URL = "https://api.daily.co/v1"


class DailyApiClient:
    """Thin wrapper around Daily's REST API."""
    BASE_URL = "https://api.daily.co/v1"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("DAILY_API_KEY")
        if not self.api_key:
            raise ValueError("DAILY_API_KEY is required")

    async def _request(self, method: str, endpoint: str, payload: dict = None) -> dict:
        """Make an authenticated request to Daily's REST API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{DAILY_API_URL}{endpoint}"

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, json=payload, headers=headers) as resp:
                body = await resp.text()
                if resp.status not in (200, 201):
                    logger.error(f"Daily API error {resp.status} {endpoint}: {body}")
                    raise Exception(f"Daily API error {resp.status}: {body}")
                import json
                return json.loads(body)

    # -------------------------------------------------------------------------
    # sipCallTransfer — Move SIP leg, Daily stays in call path
    # -------------------------------------------------------------------------

    async def sip_call_transfer(
        self,
        from_room_name: str,
        session_id: str,
        to_endpoint: str,
    ) -> dict:
        """Transfer a SIP call leg to another endpoint. Daily stays in call path.

        Use this for moving calls between Daily rooms via their SIP URI,
        or to another phone number while keeping Daily in the media path.

        POST /rooms/:name/sipCallTransfer
        {"sessionId": "...", "toEndPoint": "..."}

        Args:
            from_room_name: Room the participant is currently in
            session_id: SIP session ID of the participant to transfer
            to_endpoint: Target SIP URI or phone number
                - For room-to-room: "sip:<room-name>@<sip-domain>"
                - For phone: "+1234567890"

        Returns:
            API response dict
        """
        payload = {
            "sessionId": session_id,
            "toEndPoint": to_endpoint,
        }

        logger.info(
            f"sipCallTransfer: session={session_id} "
            f"from={from_room_name} to={to_endpoint}"
        )

        result = await self._request(
            "POST",
            f"/rooms/{from_room_name}/sipCallTransfer",
            payload,
        )

        logger.info(f"sipCallTransfer result: {result}")
        return result

    async def sip_refer(self, room_name: str, session_id: str, to_endpoint: str) -> dict:
        """Transfer a SIP call leg to another endpoint via SIP REFER.

        Args:
            room_name: The room the participant is currently in
            session_id: The SIP session ID of the participant to transfer
            to_endpoint: SIP URI or phone number to transfer to

        Returns:
            API response dict
        """
        payload = {
            "sessionId": session_id,
            "toEndPoint": to_endpoint,
        }
        logger.info(f"SIP REFER: room={room_name}, session={session_id}, to={to_endpoint}")
        result = await self._request("POST", f"/rooms/{room_name}/sipRefer", payload)
        logger.info(f"SIP REFER result: {result}")
        return result

    def _headers(self):
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    async def dial_out(
            self,
            room_name: str,
            phone_number: str,
            caller_id: str | None = None,
            display_name: str | None = None,
    ):
        url = f"{self.BASE_URL}/rooms/{room_name}/dialOut/start"

        logger.info(f"Dial-out start: {phone_number}")
        logger.info(f"BASE_URl: {self.BASE_URL}")
        logger.info(f"room_name: {room_name}")

        payload = {
            "phoneNumber": phone_number,
        }

        if caller_id:
            payload["callerId"] = caller_id

        if display_name:
            payload["displayName"] = display_name

        async with aiohttp.ClientSession() as session:
            async with session.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    timeout=30,
            ) as response:
                if response.status != 200:
                    text = await response.text()
                    raise RuntimeError(
                        f"Dial-out failed ({response.status}): {text}"
                    )

                return await response.json()

    async def destroy_room(self, room_name: str) -> dict:
        """Destroy a Daily room.

        Args:
            room_name: Name of the room to destroy

        Returns:
            API response dict
        """
        logger.info(f"Destroying room: {room_name}")
        return await self._request("DELETE", f"/rooms/{room_name}")

    async def create_meeting_token(self, room_name: str, is_owner: bool = True) -> str:
        """Create a meeting token for a room.

        Args:
            room_name: Room to create token for
            is_owner: Whether the token grants owner permissions

        Returns:
            Meeting token string
        """
        payload = {
            "properties": {
                "room_name": room_name,
                "is_owner": is_owner,
            }
        }
        resp = await self._request("POST", "/meeting-tokens", payload)
        return resp["token"]