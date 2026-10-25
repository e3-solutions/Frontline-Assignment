"""Conversation driver shared by offline and optional live evaluations."""
from __future__ import annotations

import os
from copy import deepcopy

from evals._pipecat_shim import install
from evals.fake_tools import FakeTools
from evals.fixtures import build_system_prompt

install()
from tool_definitions import (  # noqa: E402
    END_CALL_FUNCTION, GET_LOAD_CONTEXT_FUNCTION, RECORD_AGREEMENT_FUNCTION,
    TRANSFER_TO_HUMAN_FUNCTION, VERIFY_CARRIER_FUNCTION,
)

TOOLS = [x.to_default_dict() for x in (VERIFY_CARRIER_FUNCTION, GET_LOAD_CONTEXT_FUNCTION,
         RECORD_AGREEMENT_FUNCTION, END_CALL_FUNCTION, TRANSFER_TO_HUMAN_FUNCTION)]


class ScriptedLLM:
    """A deterministic response sequence used to prove harness/checker wiring."""
    def __init__(self, responses): self.responses = deepcopy(responses); self.index = 0
    def __call__(self, messages, tools):
        if self.index >= len(self.responses): return {"role": "assistant", "content": "", "tool_calls": []}
        response = deepcopy(self.responses[self.index]); self.index += 1
        return {"role": "assistant", "content": response.get("content", ""),
                "tool_calls": response.get("tool_calls", [])}


class OpenAILLM:
    """Optional backend; imported only when credentials and package exist."""
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    def __call__(self, messages, tools):
        response = self.client.chat.completions.create(
            model="gpt-4.1", messages=messages, tools=tools, temperature=0.7,
            frequency_penalty=0.6, presence_penalty=0.5,
        ).choices[0].message
        calls = [{"name": c.function.name, "arguments": __import__("json").loads(c.function.arguments)}
                 for c in (response.tool_calls or [])]
        return {"role": "assistant", "content": response.content or "", "tool_calls": calls}


def run_conversation(carrier_turns, llm, fake_tools=None):
    """Run each carrier turn, allowing tool-result follow-up assistant turns."""
    fake_tools = fake_tools or FakeTools()
    messages = [{"role": "system", "content": build_system_prompt()}]
    transcript = deepcopy(messages)
    for carrier in carrier_turns:
        user = {"role": "user", "content": carrier, "tool_calls": [], "tool_results": []}
        messages.append({"role": "user", "content": carrier}); transcript.append(user)
        while True:
            assistant = llm(messages, TOOLS)
            transcript.append(deepcopy(assistant)); messages.append({"role": "assistant", "content": assistant["content"]})
            if not assistant["tool_calls"]: break
            for call in assistant["tool_calls"]:
                result = fake_tools.dispatch(call["name"], call.get("arguments", {}))
                tool_turn = {"role": "tool", "tool_name": call["name"], "tool_result": result,
                             "content": "", "tool_calls": [], "tool_results": [result]}
                transcript.append(tool_turn)
                messages.append({"role": "tool", "tool_call_id": call["name"], "content": __import__("json").dumps(result)})
                if call["name"] == "get_load_context" and result["status"] == "success":
                    messages[0] = {"role": "system", "content": build_system_prompt(result["load_data"])}
    return transcript, fake_tools
