from typing import Optional
from pipecat.utils.string import match_endofsentence
from pipecat.utils.text.base_text_aggregator import BaseTextAggregator


class ResponseAwareSentenceAggregator(BaseTextAggregator):
    def __init__(self):
        self._buffer = ""
        self._sentence_count = 0

    @property
    def text(self) -> str:
        return self._buffer

    async def aggregate(self, text: str) -> Optional[str]:
        self._buffer += text

        eos_index = match_endofsentence(self._buffer)
        if not eos_index:
            return None

        sentence = self._buffer[:eos_index]
        self._buffer = self._buffer[eos_index:]

        needs_pause = self._sentence_count > 0
        self._sentence_count += 1

        return (sentence, needs_pause)

    async def handle_interruption(self):
        self._buffer = ""
        self._sentence_count = 0

    async def reset(self):
        self._buffer = ""
        self._sentence_count = 0