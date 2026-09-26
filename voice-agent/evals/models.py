"""Serializable evaluation trace and result models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Event:
    type: str
    content: str | None = None
    name: str | None = None
    arguments: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Event":
        return cls(**value)


@dataclass
class Trace:
    scenario_id: str
    context: dict[str, Any]
    events: list[Event]
    side_effects: list[dict[str, Any]] = field(default_factory=list)
    expected_pass: bool | None = None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Trace":
        return cls(
            scenario_id=value["scenario_id"],
            context=value.get("context", {}),
            events=[Event.from_dict(item) for item in value.get("events", [])],
            side_effects=value.get("side_effects", []),
            expected_pass=value.get("expected_pass"),
        )


@dataclass
class Finding:
    grader: str
    code: str
    message: str
    severity: str = "critical"
    event_index: int | None = None


@dataclass
class EvaluationResult:
    scenario_id: str
    passed: bool
    findings: list[Finding]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
