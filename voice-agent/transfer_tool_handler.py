"""LLM tool call handlers for transfer operations.

Single Responsibility: Handle LLM tool calls that trigger room transfers.
"""

import json

from loguru import logger
from src import (
    NegotiationDBService,
    build_transfer_phone_number,
    coerce_e164_transfer_number,
)


class TransferToolHandler:
    """Handles LLM tool calls for transfer_to_human and transfer_human_to_carrier.

    Registered as function handlers on the LLM service.
    """

    def __init__(
        self,
        orchestrator,
        http_session,
        stt,
        tts,
        llm,
        skip_tts_processor,
        transcript,
        speech_sync,
        audiobuffer,
        context_aggregator
    ):
        self._orchestrator = orchestrator
        self._http_session = http_session
        self._stt = stt
        self._tts = tts
        self._llm = llm
        self._skip_tts_processor = skip_tts_processor
        self._transcript = transcript
        self._speech_sync = speech_sync
        self._audiobuffer = audiobuffer
        self._context_aggregator = context_aggregator

    async def handle_transfer_to_human(
        self, function_name, tool_call_id, args, llm, context, result_callback
    ):
        """Handle 'transfer_to_human' tool call from LLM.

        Called when the bot decides it needs to bring a human broker into
        the conversation. Triggers Phase 2 of the transfer.

        Args:
            function_name: Name of the called function
            tool_call_id: ID of the tool call
            args: Arguments from the LLM (reason, load_number, prices)
            llm: LLM service instance
            context: Current LLM context
            result_callback: Callback to return tool result to LLM
        """
        # Guardrail: require load context before transfer
        load_uuid = getattr(context, "load_uuid", None)
        if not load_uuid:
            logger.warning("Transfer blocked: load reference not yet collected")
            await result_callback(
                json.dumps({
                    "status": "error",
                    "message": (
                        "Cannot transfer yet — no load reference has been confirmed. "
                        "Ask the carrier for their load or reference number first, "
                        "then use get_load_context before transferring."
                    ),
                })
            )
            return

        reason = args.get("reason", "")
        load_number = args.get("load_number", "")
        price_asked = args.get("price_asked_by_carrier")
        best_price = args.get("best_price_offered_by_bot")
        raw_load = NegotiationDBService.get_load(load_uuid)
        if not raw_load:
            logger.warning(f"Transfer blocked: no load found for load_uuid={load_uuid}")
            await result_callback(
                json.dumps({
                    "status": "error",
                    "message": (
                        "Cannot transfer this call because the load could not be found. "
                        "Please verify the load and try again."
                    ),
                })
            )
            return

        # KCH `public.loads.carrier_sales_rep_phone` arrives as full E.164 (e.g.
        # `+12058752486`); legacy split format is kept for test fixtures.
        human_phone_number = (
            coerce_e164_transfer_number(raw_load.get("carrier_sales_rep_phone"))
            or coerce_e164_transfer_number(raw_load.get("transfer_call_to"))
            or build_transfer_phone_number(
                raw_load.get("transfer_country_code"),
                raw_load.get("transfer_call_to"),
            )
        )
        if not human_phone_number:
            logger.warning(f"Transfer blocked: missing transfer routing for load_uuid={load_uuid}")
            await result_callback(
                json.dumps({
                    "status": "error",
                    "message": (
                        "Cannot transfer this call because no broker transfer number is configured "
                        "for this load."
                    ),
                })
            )
            return

        logger.info(
            f"Transfer to human triggered. Reason: {reason}, "
            f"Load: {load_number}, Carrier price: {price_asked}, Bot price: {best_price}, "
            f"Human phone number: {human_phone_number}"
        )

        # Set transfer metadata on the orchestrator
        self._orchestrator.set_transfer_metadata(
            reason=reason,
            load_number=load_number,
            price_asked_by_carrier=price_asked,
            best_price_offered_by_bot=best_price,
            human_phone_number=human_phone_number,
        )

        # Return result to LLM so it can speak a hold message to the carrier
        await result_callback(
            json.dumps({
                "status": "transferring",
                "message": (
                    "Tell the carrier you are placing them on a brief hold "
                    "while you connect them with the appropriate person. "
                    "Be warm and professional."
                ),
            })
        )

        # Schedule the actual transfer after the bot finishes speaking
        async def _execute_transfer():
            try:
                await self._orchestrator.execute_transfer_to_room2(
                    http_session=self._http_session,
                    stt=self._stt,
                    tts=self._tts,
                    llm=self._llm,
                    skip_tts_processor=self._skip_tts_processor,
                    transcript=self._transcript,
                    speech_sync=self._speech_sync,
                    audiobuffer=self._audiobuffer,
                    context_aggregator=self._context_aggregator,
                )
            except Exception as e:
                logger.error(f"Transfer to Room2 failed: {e}", exc_info=True)

        await self._speech_sync.schedule_after_speech(_execute_transfer)

    async def handle_transfer_human_to_carrier(
        self, function_name, tool_call_id, args, llm, context, result_callback
    ):
        """Handle 'transfer_human_to_carrier' tool call from LLM.

        Called when the bot and human broker are done discussing in Room2.
        Triggers Phase 3: SIP REFER human to Room1.

        Args:
            function_name: Name of the called function
            tool_call_id: ID of the tool call
            args: Arguments from the LLM (summary)
            llm: LLM service instance
            context: Current LLM context
            result_callback: Callback to return tool result to LLM
        """
        summary = args.get("summary", "")
        logger.info(f"Transfer human to carrier triggered. Summary: {summary}")

        session_id = getattr(context, "session_id", None)

        getattr(context, "call_mode", None)

        # Return result so bot can speak a transition message
        await result_callback(
            json.dumps({
                "status": "transferring",
                "message": (
                    "Tell the human broker you are now connecting them "
                    "directly with the carrier. Wish them well."
                ),
            })
        )

        async def _execute_transfer():
            try:
                await self._orchestrator.execute_transfer_human_to_room1(session_id)
            except Exception as e:
                logger.error(f"Transfer human to Room1 failed: {e}", exc_info=True)

        await self._speech_sync.schedule_after_speech(_execute_transfer)
