"""Multi-room transfer orchestrator.

Single Responsibility: Coordinate the 3-phase transfer flow between rooms.
Delegates to specialized services for each concern.
"""

import asyncio
import os

import aiohttp
from loguru import logger
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.pipeline.task import PipelineTask

from transfer_state import TransferState
from daily_api_client import DailyApiClient
from hold_music_bot import HoldMusicBot
from room2_pipeline_service import Room2PipelineService
from number_strategy import RandomSelectionStrategy
from transfer_notifier import TransferNotifier, NotificationType
from models import TransferMessage


# Configure your Daily SIP domain here
DAILY_SIP_DOMAIN = os.getenv("DAILY_SIP_DOMAIN", "your-domain.daily.co")


class TransferOrchestrator:
    """Orchestrates the 3-phase multi-room transfer.

    Phase 1: Bot + Carrier in Room1 (handled by bot.py)
    Phase 2: Bot + Human Broker in Room2 (this orchestrator)
    Phase 3: SIP REFER human to Room1, carrier + human talk
    """

    def __init__(self):
        self._daily_dialin_settings = None
        self._state = TransferState()
        self._daily_api = DailyApiClient()
        self._hold_music_bot: HoldMusicBot = None
        self._room2_pipeline: Room2PipelineService = None

        # References to Room1 pipeline (set externally)
        self._room1_task: PipelineTask = None
        self._room1_context: LLMContext = None
        self._room1_context_aggregator: LLMContextAggregatorPair = None

        self.call_id = None
        # self.call_domain = None
        self.sip_endpoint = None

        # === Transfer lifecycle tracking ===
        self._transfer_in_progress = False
        self._transfer_complete_event = asyncio.Event()

        # Number selection strategy
        self.number_selection_strategy = RandomSelectionStrategy()

        # Notifier
        self.notifier = TransferNotifier(NotificationType.SLACK)

    @property
    def state(self) -> TransferState:
        return self._state

    def set_state(self, state: TransferState):
        self._state = state

    def is_transfer_in_progress(self) -> bool:
        """Check if a transfer is currently in progress."""
        return self._transfer_in_progress

    async def wait_for_transfer_complete(self):
        """Block until the transfer flow (Phase 2 + Phase 3) is complete.

        Called by run_bot() after Room1 pipeline ends to keep the
        function alive while transfer is running.
        """
        if not self._transfer_in_progress:
            return
        logger.info("Waiting for transfer to complete...")
        await self._transfer_complete_event.wait()
        logger.info("Transfer complete event received.")

    def _mark_transfer_started(self):
        """Mark that a transfer has begun."""
        self._transfer_in_progress = True
        self._transfer_complete_event.clear()
        # Stamp the Room1 context so finish_call labels this call correctly
        # even if the transfer later fails, raises, or never reaches Phase 3.
        if self._room1_context is not None:
            self._room1_context.end_reason = "call_transferred"

    def _mark_transfer_complete(self):
        """Mark that the transfer flow is done."""
        self._transfer_in_progress = False
        self._transfer_complete_event.set()

    def set_room1_references(
        self,
        room1_url: str,
        room1_token: str,
        task: PipelineTask,
        context: LLMContext,
        context_aggregator: LLMContextAggregatorPair,
        _daily_dialin_settings,
        call_id,
        sip_endpoint,
    ):
        """Store references to Room1 pipeline components.

        Called during bot initialization so the orchestrator can
        capture context and cancel the task when transferring.
        """
        self._state.room1_url = room1_url
        self._state.room1_token = room1_token
        self._room1_task = task
        self._room1_context = context
        self._room1_context_aggregator = context_aggregator
        self._daily_dialin_settings = _daily_dialin_settings
        self.call_id = call_id
        # self.call_domain = call_domain
        # self._state.call_domain = call_domain
        self._state.sip_endpoint = sip_endpoint

    def set_transfer_metadata(
        self,
        reason: str,
        load_number: str = None,
        price_asked_by_carrier: float = None,
        best_price_offered_by_bot: float = None,
        human_phone_number: str = None,
    ):
        """Set metadata about the transfer (from tool call args)."""
        self._state.transfer_reason = reason
        self._state.load_number = load_number
        self._state.price_asked_by_carrier = price_asked_by_carrier
        self._state.best_price_offered_by_bot = best_price_offered_by_bot
        if human_phone_number:
            self._state.human_phone_number = human_phone_number

    # -------------------------------------------------------------------------
    # Phase 2: Transfer bot to Room2 and dial-out human
    # -------------------------------------------------------------------------

    async def execute_transfer_to_room2(
        self,
        http_session: aiohttp.ClientSession,
        stt,
        tts,
        llm,
        skip_tts_processor,
        transcript,
        speech_sync,
        audiobuffer,
        context_aggregator,
    ):
        """Execute Phase 2: Move bot to Room2 and dial-out human broker.

        Steps:
        1. Capture Room1 context
        2. Start hold music in Room1
        3. Cancel Room1 pipeline (bot leaves Room1)
        4. Create Room2
        5. Start Room2 pipeline
        6. Dial-out human broker to Room2

        Args:
            http_session: aiohttp session for Daily API calls
            stt, tts, llm, ...: Pipeline components reused from Room1

        Parameters
        ----------
        context_aggregator
        audiobuffer
        speech_sync
        transcript
        llm
        skip_tts_processor
        http_session
        tts
        stt
        """
        logger.info("=== Phase 2: Transfer to Room2 ===")

        self._mark_transfer_started()

        # Copy load context (pricing info) from Room1 for Room2 human agent
        self._state.load_context = getattr(self._room1_context, 'load_context', None)

        try:
            # Step 1: Capture Room1 context BEFORE canceling
            # self._capture_room1_context()

            # Step 2: Start hold music in Room1
            await self._start_hold_music()

            # Step 3: Cancel Room1 pipeline (bot leaves, carrier hears hold music)
            await self._leave_room1()

            # Step 4: Create Room2
            await self._create_room2(http_session)

            # NEED TO SET THESE BEFORE ROOM2 PIPELINE SERVICE
            # room_url = self._state.room2_url,
            # token = self._state.room2_token,
            # bot_name = "Negotiation Agent",
            # daily_dialin_settings = self._state.daily_dialin_settings,

            # Step 5: Start Room2 pipeline
            self._room2_pipeline = Room2PipelineService(self._state, self)

            # Register the transfer_human_to_carrier tool on the LLM
            # (This is done in the handler registration, not here)

            room2_future = await self._room2_pipeline.start(
                stt=stt,
                tts=tts,
                llm=llm,
                skip_tts_processor=skip_tts_processor,
                transcript=transcript,
                speech_sync=speech_sync,
                audiobuffer=audiobuffer,
                context_aggregator=context_aggregator,
            )

            # Send transfer message
            transfer_message = TransferMessage(load_number=self._state.load_number, reason_of_transfer=self._state.transfer_reason,
                                               price_asked_by_carrier=self._state.price_asked_by_carrier, best_price_offered_by_bot=self._state.best_price_offered_by_bot)
            await self.notifier.notify(transfer_message)

            # Step 6: Wait for bot to connect, then dial-out human
            await asyncio.sleep(2)

            # Get human agent phone number
            human_agent_number = self.number_selection_strategy.select(self._state.human_phone_number)
            await self._dialout_human_to_room2(human_agent_number)

            # Wait for Room2 conversation to finish
            # (This blocks until the Room2 pipeline ends)
            logger.info("Waiting for Room2 conversation to complete...")
            await room2_future
            logger.info("Room2 conversation ended.")
        except Exception as e:
            logger.error(f"Phase 2 failed: {e}", exc_info=True)
        finally:
            # Always mark transfer complete so bot.py can finalize the Room1 call record.
            # If Phase 3 already marked complete in its own task (success path),
            # this is an idempotent no-op. If Phase 3 never ran — e.g. the human
            # disconnected in Room2 before the LLM called transfer_human_to_carrier —
            # this prevents bot.py wait_for_transfer_complete() from hanging forever.
            self._mark_transfer_complete()

    def _capture_room1_context(self):
        """Capture conversation messages from Room1 context."""
        if self._room1_context_aggregator:
            context = self._room1_context_aggregator._context
            self._state.room1_messages = context.messages.copy()
            logger.info(
                f"Captured {len(self._state.room1_messages)} messages from Room1"
            )
        else:
            logger.warning("No Room1 context aggregator — Room2 will start fresh")
            self._state.room1_messages = []

    async def _start_hold_music(self):
        """Start hold music bot in Room1."""
        # room1_name = self._state.room1_url.split("/")[-1]

        # get a token for the hold music bot
        hold_token = self._state.room1_token

        self._hold_music_bot = HoldMusicBot(self._state.room1_url, hold_token, self._daily_dialin_settings)
        await self._hold_music_bot.start()

        # Give hold music bot time to connect before main bot leaves
        await asyncio.sleep(1)
        logger.info("Hold music started in Room1")

    async def _leave_room1(self):
        """Cancel Room1 pipeline so bot leaves Room1."""
        if self._room1_task:
            await self._room1_task.cancel()
            logger.info("Bot left Room1")
        else:
            logger.warning("No Room1 task to cancel")

    async def _create_room2(self, http_session: aiohttp.ClientSession):
        """Create Room2 via the room pool or Daily API."""
        from server_utils import create_daily_room, DailyCallData

        # Create a minimal call data object for room creation
        # Room2 doesn't need actual PSTN call data, just a room
        call_data = DailyCallData(
            from_phone="bot",
            to_phone="human",
            call_id="room2-transfer",
            call_domain=os.getenv("DAILY_DOMAIN", ""),
        )

        daily_room_config = await create_daily_room(call_data, http_session)
        self._state.room2_url = daily_room_config.room_url
        self._state.room2_token = daily_room_config.token

        logger.info(f"Room2 created: {self._state.room2_url}")

    async def _dialout_human_to_room2(self, phone_number: str):
        """Dial-out the human broker into Room2."""
        if not phone_number:
            logger.error("No human phone number configured!")
            return

        room2_name = self._state.room2_url.split("/")[-1]
        await self._daily_api.dial_out(
            room_name=room2_name,
            phone_number=phone_number,
            display_name="Broker Line",
        )
        logger.info(f"Dialed out human {phone_number} to Room2")

    # -------------------------------------------------------------------------
    # Phase 3: SIP REFER human from Room2 → Room1
    # -------------------------------------------------------------------------


    def get_transfer_sip_uri(self, sip_uri: str) -> str:
        # Split on @ → ["sip:pipecat-sip-44fc6454.0", "daily-xxx.signalwire.com"]
        local, domain = sip_uri.split("@")

        # Strip the existing .0 (or any .N) suffix
        base = local.rsplit(".", 1)[0]  # "sip:pipecat-sip-44fc6454"

        # Append .1
        return f"{base}.1@{domain}"  # "sip:pipecat-sip-44fc6454.1@daily-xxx.signalwire.com"

    async def execute_transfer_human_to_room1(self, session_id: str):
        """Execute Phase 3: Transfer human's call from Room2 to Room1.

        Uses sipCallTransfer with Room1's SIP endpoint as toEndPoint.
        Daily stays in the call path — human seamlessly moves to Room1.

        Falls back to hangup + redial if sipCallTransfer fails.
        """
        logger.info("=== Phase 3: Transfer human to Room1 ===")

        room2_name = self._state.room2_url.split("/")[-1]
        to_endpoint = self._state.sip_endpoint

        to_endpoint_updated = self.get_transfer_sip_uri(to_endpoint)

        logger.info(
            f"sipCallTransfer: session={session_id} "
            f"from_room={room2_name} "
            f"to_endpoint={to_endpoint_updated}"
        )

        # Step 1: sipCallTransfer
        try:
            await self._daily_api.sip_call_transfer(
                from_room_name=room2_name,
                session_id=session_id,
                to_endpoint=to_endpoint_updated,
            )
            logger.info("sipCallTransfer successful — human moved to Room1")
        except Exception as e:
            logger.error(f"sipCallTransfer failed: {e}")
            await self._fallback_redial_human()
            return

        # Step 2: Stop hold music in Room1
        await self._stop_hold_music()

        # Step 3: Bot leaves Room2
        if self._room2_pipeline:
            await self._room2_pipeline.stop()
            logger.info("Bot left Room2")

        # Step 4: Clean up Room2
        await self._cleanup_room2()

        self._mark_transfer_complete()
        logger.info("Phase 3 complete: Carrier and Human now talking in Room1")

    async def _stop_hold_music(self):
        """Stop hold music in Room1."""
        if self._hold_music_bot:
            await self._hold_music_bot.stop()
            self._hold_music_bot = None
            logger.info("Hold music stopped in Room1")

    async def _cleanup_room2(self):
        """Destroy Room2 after transfer is complete."""
        if self._state.room2_url:
            room2_name = self._state.room2_url.split("/")[-1]
            try:
                await self._daily_api.destroy_room(room2_name)
                logger.info(f"Room2 ({room2_name}) destroyed")
            except Exception as e:
                logger.warning(f"Failed to destroy Room2: {e}")

    async def _fallback_redial_human(self):
        """Fallback: hangup human from Room2 and redial into Room1."""
        logger.warning("Using fallback: hangup + redial")

        # Stop Room2 pipeline (disconnects everyone)
        if self._room2_pipeline:
            await self._room2_pipeline.stop()

        # Destroy Room2
        await self._cleanup_room2()

        # Wait for clean disconnection
        await asyncio.sleep(2)

        # Redial human into Room1
        if self._state.human_phone_number and self._state.room1_url:
            room1_name = self._state.room1_url.split("/")[-1]
            await self._daily_api.dialout(
                room_name=room1_name,
                phone_number=self._state.human_phone_number,
                display_name="Broker Line",
            )
            logger.info(f"Redialed human into Room1")

        # Stop hold music
        await self._stop_hold_music()
        self._mark_transfer_complete()
