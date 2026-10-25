"""Import-only substitutes for unavailable third-party packages; test-only."""
from __future__ import annotations
import sys
import types

def _module(name):
    module = types.ModuleType(name); sys.modules[name] = module; return module

def install():
    if "loguru" not in sys.modules:
        loguru = _module("loguru")
        loguru.logger = types.SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None, debug=lambda *a, **k: None)
    if "httpx" not in sys.modules:
        httpx = _module("httpx"); httpx.Client = type("Client", (), {}); httpx.AsyncClient = type("AsyncClient", (), {})
        httpx.TimeoutException = type("TimeoutException", (Exception,), {}); httpx.RequestError = type("RequestError", (Exception,), {})
    if "supabase" not in sys.modules:
        supabase = _module("supabase"); supabase.Client = type("Client", (), {}); supabase.create_client = lambda *a, **k: None
    if "pydantic" not in sys.modules:
        pydantic = _module("pydantic"); pydantic.BaseModel = type("BaseModel", (), {}); pydantic.Field = lambda default=None, **kwargs: default
    if "pipecat" not in sys.modules:
        _module("pipecat"); _module("pipecat.frames"); frames = _module("pipecat.frames.frames")
        frames.EndFrame = type("EndFrame", (), {}); frames.FunctionCallResultProperties = type("FunctionCallResultProperties", (), {})
        _module("pipecat.adapters"); _module("pipecat.adapters.schemas")
        schema = _module("pipecat.adapters.schemas.function_schema")
        class FunctionSchema:
            def __init__(self, name, description, properties, required): self.name, self.description, self.properties, self.required = name, description, properties, required
            def to_default_dict(self): return {"name": self.name, "description": self.description, "parameters": {"type": "object", "properties": self.properties, "required": self.required}}
        schema.FunctionSchema = FunctionSchema
