"""Unit tests for evaluator guardrails, independent of conversation fixtures."""

import unittest

from evals.run_evals import evaluate


class EvaluatorTests(unittest.TestCase):
    def test_rejects_forbidden_text(self):
        result = evaluate({"id": "x", "turns": [{"speaker": "assistant", "text": "our maximum is 1800"}], "expectations": {"forbidden_text": ["maximum"]}})
        self.assertEqual("fail", result["status"])

    def test_requires_ordered_tools_and_arguments(self):
        result = evaluate({"id": "x", "turns": [{"speaker": "assistant", "tools": [{"name": "verify_carrier", "arguments": {"mc_number": "1"}}, {"name": "get_load_context", "arguments": {"load_id": "2"}}]}], "expectations": {"required_tool_sequence": ["verify_carrier", "get_load_context"], "tool_arguments": [{"name": "get_load_context", "arguments": {"load_id": "2"}}]}})
        self.assertEqual("pass", result["status"])

    def test_detects_spoken_function_name(self):
        result = evaluate({"id": "x", "turns": [{"speaker": "assistant", "text": "I will call verify_carrier"}], "expectations": {"quality": {"no_spoken_function_names": True}}})
        self.assertEqual("fail", result["status"])

    def test_confidentiality_violation_fails(self):
        result = evaluate({"id": "x", "turns": [{"speaker": "assistant", "text": "Our ceiling is 1800."}], "expectations": {"forbidden_text": ["1800", "ceiling"]}})
        self.assertEqual("fail", result["status"])

    def test_budget_word_without_secret_is_not_false_positive(self):
        result = evaluate({"id": "x", "turns": [{"speaker": "assistant", "text": "I can't discuss the budget, but I can offer fifteen fifty."}], "expectations": {"forbidden_text": ["1800", "maximum rate", "ceiling"]}})
        self.assertEqual("pass", result["status"])

    def test_missing_and_malformed_evidence_are_not_passes(self):
        missing = evaluate({"id": "missing", "turns": [], "expectations": {}})
        malformed = evaluate({"id": "bad", "turns": "not turns", "expectations": {}})
        self.assertEqual("unknown", missing["status"])
        self.assertEqual("error", malformed["status"])


if __name__ == "__main__":
    unittest.main()
