from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, TextFrame
from loguru import logger


class TTSSkipGateProcessor(FrameProcessor):
    def __init__(self, context):
        super().__init__(name="TTSSkipGateProcessor")
        self.context = context

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # Only intercept text frames
        await super().process_frame(frame, direction)
        if isinstance(frame, TextFrame):
            if self.context.skip_tts:
                logger.debug(f"Skipping TTS")
                frame.skip_tts = True

        await self.push_frame(frame, direction)