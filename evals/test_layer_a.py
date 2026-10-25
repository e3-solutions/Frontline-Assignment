"""Always-run offline action-boundary evaluations using unittest only."""
from __future__ import annotations
import asyncio, json, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / "voice-agent"), str(Path(__file__).resolve().parents[1] / "shared")]
from stdlib_stubs import install
install()
import call_helpers
from transfer_tool_handler import TransferToolHandler
from voice_prompt import get_initial_greeting_prompt
from src.negotiation_prompt import get_load_details

class LayerA(unittest.TestCase):
    def context(self):
        return SimpleNamespace(load_uuid="load-uuid", call_id="call-uuid", caller_mc="123456", caller_phone="+15555550123", load_context={"load_id": "LOAD-123", "maxRate": 2000}, call_mode="BOT_ACTIVE")
    def callback(self, results):
        async def collect(raw): results.append(json.loads(raw))
        return collect
    def test_accepted_agreement_notifies_once_with_price_mc_and_load(self):
        results, notified = [], MagicMock()
        with patch.object(call_helpers, "save_agreement", return_value="negotiation-1"), patch.object(call_helpers.NegotiationDBService, "notify_carrier_quote", notified):
            asyncio.run(call_helpers.record_agreement("record_agreement", "tool", {"agreed_price": 1850, "carrier_contact_name": "Pat", "carrier_contact_phone": "+15555550123"}, None, self.context(), self.callback(results)))
        self.assertEqual("success", results[-1]["status"])
        notified.assert_called_once_with(load_name="LOAD-123", agreed_price=1850.0, mc_number="123456", source_type="call", carrier_name="Pat", carrier_phone="+15555550123")
    @unittest.expectedFailure
    def test_finding_above_ceiling_accepted_agreement_must_not_notify_quote(self):
        """FINDING: current handler trusts above_max from the LLM and submits this quote."""
        results, notified = [], MagicMock()
        with patch.object(call_helpers, "save_agreement", return_value="negotiation-1"), patch.object(call_helpers.NegotiationDBService, "notify_carrier_quote", notified):
            asyncio.run(call_helpers.record_agreement("record_agreement", "tool", {"agreed_price": 2200, "carrier_contact_name": "Pat", "carrier_contact_phone": "+15555550123"}, None, self.context(), self.callback(results)))
        notified.assert_not_called()
    def test_unknown_load_cannot_produce_quote(self):
        results, notified = [], MagicMock(); context = SimpleNamespace(load_uuid=None, call_id="call-uuid", caller_mc="123456")
        with patch.object(call_helpers.NegotiationDBService, "notify_carrier_quote", notified):
            asyncio.run(call_helpers.record_agreement("record_agreement", "tool", {"agreed_price": 1800}, None, context, self.callback(results)))
        self.assertEqual("error", results[-1]["status"]); notified.assert_not_called()
    def test_transfer_without_load_is_blocked(self):
        results = []; handler = TransferToolHandler(*([MagicMock()] * 10))
        asyncio.run(handler.handle_transfer_to_human("transfer_to_human", "tool", {}, None, SimpleNamespace(), self.callback(results)))
        self.assertEqual("error", results[-1]["status"])
    def test_end_call_after_transfer_is_ignored(self):
        results = []
        asyncio.run(call_helpers.end_call("end_call", "tool", {"reason": "agreement"}, None, SimpleNamespace(call_mode="HUMAN_ONLY"), self.callback(results)))
        self.assertEqual("ignored", results[-1]["status"])
    def test_prompts_contain_non_disclosure_and_function_name_rules(self):
        prompt = get_load_details({"id": "LOAD-1", "origin": {}, "destination": {}, "startRate": 1000, "bookNowRate": 1500, "maxRate": 2000})
        self.assertIn("NEVER SHARE WITH CARRIER", prompt); self.assertIn("NEVER SPEAK FUNCTION NAMES", get_initial_greeting_prompt())
