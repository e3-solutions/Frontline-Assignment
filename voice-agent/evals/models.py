from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ExpectedTurn:
    """A caller turn and the invariant(s) the agent must satisfy next."""

    caller: str
    required_tools: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    required_phrases: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    terminal_reason: str | None = None
    required_tool_arguments: dict[str, dict[str, object]] = field(default_factory=dict)
    # Synthetic timing is used only by the offline harness, never reported as
    # production latency. It validates metric calculation and reporting.
    synthetic_ms: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class Scenario:
    id: str
    priority: Literal["P0", "P1"]
    description: str
    boundary: str
    turns: tuple[ExpectedTurn, ...]


@dataclass
class TurnResult:
    caller: str
    passed: bool
    failures: list[str]
    tools: list[str]
    tool_arguments: dict[str, dict[str, object]]
    latency_ms: dict[str, float]
    judge: dict | None = None


@dataclass
class ScenarioResult:
    id: str
    priority: str
    status: Literal["PASS", "FAIL", "NOT_RUN"]
    boundary: str
    turns: list[TurnResult]
    p50_first_audio_ms: float | None
    p95_first_audio_ms: float | None
    completion_rate: float

    def to_dict(self) -> dict:
        return asdict(self)
