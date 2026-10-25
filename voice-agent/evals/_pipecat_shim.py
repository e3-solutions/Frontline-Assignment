"""Provide the tiny Pipecat schema surface needed by offline evaluations.

This is deliberately a mocked boundary: production still uses Pipecat's real
FunctionSchema.  The shim is registered only when Pipecat is unavailable.
"""
from __future__ import annotations

import sys
import types


def install() -> None:
    try:
        from pipecat.adapters.schemas.function_schema import FunctionSchema  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    class FunctionSchema:  # noqa: D101
        def __init__(self, name, description, properties, required):
            self.name = name
            self.description = description
            self.properties = properties
            self.required = required

        def to_default_dict(self):
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description,
                    "parameters": {
                        "type": "object",
                        "properties": self.properties,
                        "required": self.required,
                    },
                },
            }

    modules = ("pipecat", "pipecat.adapters", "pipecat.adapters.schemas")
    for name in modules:
        sys.modules.setdefault(name, types.ModuleType(name))
    module_name = "pipecat.adapters.schemas.function_schema"
    module = types.ModuleType(module_name)
    module.FunctionSchema = FunctionSchema
    sys.modules[module_name] = module


install()
