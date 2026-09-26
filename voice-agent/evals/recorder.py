"""In-memory recorder shared by scripted conversations and mocked handlers."""

from __future__ import annotations

from typing import Any

from .models import Event, Trace


class TraceRecorder:
    def __init__(self, scenario_id: str, context: dict[str, Any] | None = None):
        self.trace = Trace(scenario_id=scenario_id, context=context or {}, events=[])

    def caller(self, content: str) -> None:
        self.trace.events.append(Event(type="caller", content=content))

    def assistant(self, content: str) -> None:
        self.trace.events.append(Event(type="assistant", content=content))

    def tool_call(self, name: str, arguments: dict[str, Any]) -> None:
        self.trace.events.append(Event(type="tool_call", name=name, arguments=arguments))

    def tool_result(self, name: str, result: dict[str, Any]) -> None:
        self.trace.events.append(Event(type="tool_result", name=name, result=result))

    def decision(self, name: str, arguments: dict[str, Any]) -> None:
        self.trace.events.append(Event(type="decision", name=name, arguments=arguments))

    def marker(self, event_type: str) -> None:
        self.trace.events.append(Event(type=event_type))

    def side_effect(self, effect_type: str, **details: Any) -> None:
        self.trace.side_effects.append({"type": effect_type, **details})
