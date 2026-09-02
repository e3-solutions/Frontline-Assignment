from abc import ABC, abstractmethod
from typing import List, Union, Iterable
import random
import itertools
from threading import Lock


NumberInput = Union[str, Iterable[str]]


def _normalize(numbers: NumberInput) -> List[str]:
    """
    Convert single number or iterable of numbers into a list[str].
    """
    if numbers is None:
        raise ValueError("Phone numbers cannot be None")

    if isinstance(numbers, str):
        return [numbers]

    numbers_list = [str(n) for n in numbers]

    if not numbers_list:
        raise ValueError("Phone numbers list cannot be empty")

    return numbers_list


class NumberSelectionStrategy(ABC):

    @abstractmethod
    def select(self, numbers: NumberInput) -> str:
        pass


class RandomSelectionStrategy(NumberSelectionStrategy):

    def select(self, numbers: NumberInput) -> str:
        numbers_list = _normalize(numbers)
        return random.choice(numbers_list)


class RoundRobinSelectionStrategy(NumberSelectionStrategy):

    def __init__(self):
        self._cycle = None
        self._numbers_snapshot = None
        self._lock = Lock()

    def select(self, numbers: NumberInput) -> str:
        numbers_list = _normalize(numbers)

        with self._lock:
            # Reset cycle if numbers changed
            if self._cycle is None or numbers_list != self._numbers_snapshot:
                self._cycle = itertools.cycle(numbers_list)
                self._numbers_snapshot = numbers_list

            return next(self._cycle)