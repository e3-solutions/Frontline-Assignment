"""Layer B: OpenAI scripted conversations; tool boundaries stay in memory."""
import asyncio, json, os, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.request import Request, urlopen
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "voice-agent"), str(Path(__file__).resolve().parents[1] / "shared")]
from stdlib_stubs import install
install()
import call_helpers
from tool_definitions import END_CALL_FUNCTION, GET_LOAD_CONTEXT_FUNCTION, RECORD_AGREEMENT_FUNCTION, TRANSFER_TO_HUMAN_FUNCTION, VERIFY_CARRIER_FUNCTION
from load_context_utils import get_initial_system_prompt

SCRIPTS = {"happy": ["My MC is 123456.", "Yes.", "LOAD-123.", "I accept 1850. Pat, 555-555-0123."], "ceiling": ["My MC is 123456.", "Yes.", "LOAD-123.", "I need 2400."], "max": ["My MC is 123456.", "Yes.", "LOAD-123.", "What is your max?"], "bad_mc": ["MC 111111.", "MC 222222.", "MC 333333."], "human": ["My MC is 123456.", "Yes.", "LOAD-123.", "I need a human broker."]}
LOAD = {"id": "load", "load_id": "LOAD-123", "maxRate": 2000, "bookNowRate": 1800, "startRate": 1500, "origin": {"city": "Dallas", "state": "TX"}, "destination": {"city": "Atlanta", "state": "GA"}}

def complete(messages):
    schemas = [VERIFY_CARRIER_FUNCTION, GET_LOAD_CONTEXT_FUNCTION, RECORD_AGREEMENT_FUNCTION, END_CALL_FUNCTION, TRANSFER_TO_HUMAN_FUNCTION]
    body = json.dumps({"model": os.getenv("EVAL_OPENAI_MODEL", "gpt-4.1"), "temperature": 0, "messages": messages, "tools": [{"type": "function", "function": s.to_default_dict()} for s in schemas]}).encode()
    request = Request("https://api.openai.com/v1/chat/completions", data=body, headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
    with urlopen(request, timeout=60) as response: return json.load(response)["choices"][0]["message"]

@unittest.skipUnless(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY is not set; Layer B is opt-in")
class LayerBOpenAI(unittest.TestCase):
    def run_case(self, case):
        context = SimpleNamespace(messages=[{"role": "system", "content": get_initial_system_prompt("Acme")}], load_uuid="load", call_id="call", caller_mc="123456", caller_phone="+15555550123", org_id="org", call_mode="BOT_ACTIVE", load_context=LOAD)
        messages, calls, result = list(context.messages), [], ""
        async def callback(raw): nonlocal result; result = raw
        async def tool(name, args, tool_id):
            nonlocal result; calls.append(name); result = ""
            if name == "verify_carrier": await call_helpers.verify_carrier(name, tool_id, args, None, context, callback)
            elif name == "get_load_context": await call_helpers.get_load_context(name, tool_id, args, None, context, callback, caller_phone=context.caller_phone)
            elif name == "record_agreement": await call_helpers.record_agreement(name, tool_id, args, None, context, callback)
            elif name == "end_call": await call_helpers.end_call(name, tool_id, args, None, context, callback)
            else: result = json.dumps({"status": "blocked", "message": "transfer simulated"})
            return result
        carrier = {"data": {"legalName": "Pat Carrier", "dotNumber": "987"}}
        with patch.object(call_helpers, "fetch_carrier_by_mc", new=AsyncMock(return_value=None if case == "bad_mc" else carrier)), patch.object(call_helpers.NegotiationDBService, "get_load_by_reference", return_value={"id": "load"}), patch.object(call_helpers, "normalize_load_data", return_value=LOAD), patch.object(call_helpers, "save_agreement", return_value="n"), patch.object(call_helpers.NegotiationDBService, "notify_carrier_quote"), patch.object(call_helpers, "update_call_mc"), patch.object(call_helpers, "update_call_load"):
            for turn in SCRIPTS[case]:
                messages.append({"role": "user", "content": turn})
                for _ in range(4):
                    answer = complete(messages); messages.append(answer)
                    for item in answer.get("tool_calls") or []: messages.append({"role": "tool", "tool_call_id": item["id"], "content": asyncio.run(tool(item["function"]["name"], json.loads(item["function"]["arguments"]), item["id"]))})
                    if not answer.get("tool_calls"): break
        return messages, calls

def _case_test(case, run):
    def test(self):
        messages, calls = self.run_case(case); text = "\n".join(x.get("content") or "" for x in messages if x["role"] == "assistant").lower()
        if case == "happy": self.assertTrue({"verify_carrier", "get_load_context"}.issubset(calls))
        elif case == "ceiling": self.assertNotIn("maximum rate", text)
        elif case == "max": self.assertNotIn("max rate", text)
        elif case == "bad_mc": self.assertGreaterEqual(calls.count("verify_carrier"), 3)
        else: self.assertIn("transfer_to_human", calls)
    return test
for _case in SCRIPTS:
    for _run in range(1, 4): setattr(LayerBOpenAI, f"test_{_case}_{_run}", _case_test(_case, _run))
