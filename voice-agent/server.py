"""LiveKit SIP webhook and outbound-call API for the negotiation agent."""

from __future__ import annotations

import os
import secrets
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager

import aiohttp
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from livekit_ingress import LiveKitWebhookRejected, LiveKitWebhookService
from livekit_telephony_service import LiveKitTelephonyService
from server_utils import AgentRequest, OutboundCallRequest, start_bot_local
from telephony_config import (
    LiveKitTelephonyConfig,
    load_livekit_telephony_config,
    normalize_e164,
)


load_dotenv(override=True)

BotStarter = Callable[[AgentRequest, aiohttp.ClientSession], Awaitable[None]]


def create_app(
    *,
    config: LiveKitTelephonyConfig | None = None,
    webhook_service: LiveKitWebhookService | None = None,
    telephony: LiveKitTelephonyService | None = None,
    bot_starter: BotStarter | None = None,
) -> FastAPI:
    selected_config = config or load_livekit_telephony_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.http_session = aiohttp.ClientSession()
        try:
            yield
        finally:
            await app.state.http_session.close()

    app = FastAPI(lifespan=lifespan)
    app.state.livekit_config = selected_config
    app.state.telephony = telephony
    app.state.webhook_service = webhook_service
    app.state.seen_livekit_events = set()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["authorization", "content-type"],
    )

    async def start_agent(
        agent_request: AgentRequest, session: aiohttp.ClientSession
    ) -> None:
        if bot_starter is not None:
            await bot_starter(agent_request, session)
            return
        await start_bot_local(
            agent_request,
            session,
            bot_url=os.getenv("LOCAL_BOT_URL", "http://localhost:7860"),
        )

    def provider_services() -> tuple[LiveKitWebhookService, LiveKitTelephonyService]:
        if not selected_config.valid:
            raise RuntimeError(selected_config.readiness_reason or "invalid_config")
        current_telephony = app.state.telephony
        if current_telephony is None:
            current_telephony = LiveKitTelephonyService(selected_config)
            app.state.telephony = current_telephony
        current_webhook = app.state.webhook_service
        if current_webhook is None:
            current_webhook = LiveKitWebhookService(selected_config)
            app.state.webhook_service = current_webhook
        return current_webhook, current_telephony

    @app.get("/")
    async def root():
        return {
            "service": "negotiation-telephony",
            "provider": "livekit",
            "carrier": "telnyx",
        }

    @app.get("/health")
    async def health():
        if not selected_config.valid:
            return JSONResponse(
                {
                    "status": "degraded",
                    "provider": "livekit",
                    "reason": selected_config.readiness_reason,
                },
                status_code=503,
            )
        return {"status": "healthy", "provider": "livekit", "carrier": "telnyx"}

    @app.post("/livekit-webhook")
    async def handle_livekit_webhook(request: Request):
        try:
            current_webhook, current_telephony = provider_services()
        except RuntimeError as exc:
            return JSONResponse({"code": str(exc)}, status_code=503)

        try:
            event = await current_webhook.accept(
                raw_body=await request.body(),
                authorization=request.headers.get("authorization"),
            )
        except LiveKitWebhookRejected as exc:
            return JSONResponse({"code": exc.code}, status_code=exc.status_code)

        if event.event_id in app.state.seen_livekit_events:
            return {"status": "duplicate", "event_id": event.event_id}

        token = current_telephony.issue_room_token(
            event.room_name,
            f"negotiation-agent-{event.event_id}",
        )
        agent_request = AgentRequest(
            livekit_url=selected_config.livekit_url,
            room_name=event.room_name,
            token=token,
            caller_phone=event.caller_number,
            bot_phone=event.called_number,
            provider_call_id=event.telnyx_call_id,
            participant_identity=event.participant_identity,
            participant_sid=event.participant_sid,
        )
        await start_agent(agent_request, request.app.state.http_session)
        app.state.seen_livekit_events.add(event.event_id)
        return JSONResponse(
            {"status": "accepted", "event_id": event.event_id},
            status_code=202,
        )

    @app.post("/outbound-call")
    async def start_outbound_call(payload: OutboundCallRequest, request: Request):
        expected_key = os.getenv("OUTBOUND_CALL_API_KEY", "")
        supplied_key = request.headers.get("x-api-key", "")
        if not expected_key:
            return JSONResponse({"code": "OUTBOUND_CALL_DISABLED"}, status_code=503)
        if not secrets.compare_digest(supplied_key, expected_key):
            return JSONResponse({"code": "UNAUTHORIZED"}, status_code=401)
        try:
            _, current_telephony = provider_services()
            to_phone = normalize_e164(payload.to_phone)
            from_phone = normalize_e164(payload.from_phone)
        except (RuntimeError, ValueError) as exc:
            return JSONResponse({"code": str(exc)}, status_code=422)

        room = await current_telephony.create_room(purpose="outbound")
        try:
            participant = await current_telephony.dial_phone(
                room_name=room.name,
                phone_number=to_phone,
                role="carrier",
                display_name="Carrier",
            )
            agent_request = AgentRequest(
                livekit_url=selected_config.livekit_url,
                room_name=room.name,
                token=room.token,
                caller_phone=to_phone,
                bot_phone=from_phone,
                provider_call_id=participant.provider_call_id,
                participant_identity=participant.identity,
                participant_sid=participant.participant_id,
            )
            await start_agent(agent_request, request.app.state.http_session)
        except Exception:
            await current_telephony.delete_room(room.name)
            raise

        return JSONResponse(
            {
                "status": "accepted",
                "room_name": room.name,
                "participant_identity": participant.identity,
            },
            status_code=202,
        )

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
