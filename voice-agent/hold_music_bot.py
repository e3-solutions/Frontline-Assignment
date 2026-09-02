"""Hold music bot that plays music in a room while carrier waits.

Single Responsibility: Join a room and play hold music until stopped.
"""

import asyncio

from loguru import logger
from pipecat.frames.frames import MixerEnableFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask
from pipecat.transports.daily.transport import DailyDialinSettings

from transport_factory import TransportFactory


class HoldMusicBot:
    """Minimal bot that joins a room and plays hold music."""

    def __init__(self, room_url: str, token: str, daily_dialin_settings: DailyDialinSettings):
        self.room_url = room_url
        self.token = token
        self._transport = None
        self._task = None
        self._runner = None
        self._run_future = None
        self.daily_dialin_settings = daily_dialin_settings

    async def start(self):
        """Join the room and start playing hold music."""
        self._transport = TransportFactory.create_hold_music(
            room_url=self.room_url,
            token=self.token,
            daily_dialin_settings=self.daily_dialin_settings
        )

        pipeline = Pipeline([
            self._transport.output(),
        ])

        self._task = PipelineTask(pipeline)
        self._runner = PipelineRunner()

        logger.info(f"Hold music bot joining {self.room_url}")
        self._run_future = asyncio.create_task(self._runner.run(self._task))

    async def stop(self):
        """Stop playback without leaving the room."""
        if self._task:
            await self._task.queue_frame(MixerEnableFrame(enable=False))
            logger.info("Hold music playback disabled")
