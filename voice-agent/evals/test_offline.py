"""Offline contracts: production prompt text plus deterministic scenario checks."""
from __future__ import annotations

import unittest

from evals._pipecat_shim import install
install()
from tool_definitions import END_CALL_FUNCTION  # noqa: E402
from evals.fixtures import NORMAL_LOAD, build_system_prompt
from evals.harness import ScriptedLLM, run_conversation
from evals.scenarios import SCENARIOS


class PromptContractTests(unittest.TestCase):
    def test_forbidden_amount_section_names_goal_and_ceiling(self):
        prompt = build_system_prompt(NORMAL_LOAD).lower()
        self.assertIn("internal goal", prompt)
        self.assertIn("internal ceiling", prompt)

    def test_every_prompt_end_reason_is_schema_supported(self):
        prompt = build_system_prompt(NORMAL_LOAD)
        for reason in END_CALL_FUNCTION.properties["reason"]["enum"]:
            self.assertIn(f"reason='{reason}'", prompt)

    def test_prompt_uses_only_declared_tool_names(self):
        prompt = build_system_prompt(NORMAL_LOAD)
        declared = {"verify_carrier", "get_load_context", "record_agreement", "end_call",
                    "transfer_to_human", "transfer_human_to_carrier"}
        referenced = {name for name in declared if name in prompt}
        self.assertEqual(referenced, declared)
        self.assertNotIn("confirm_carrier_identity", prompt)


class ScenarioTests(unittest.TestCase):
    """One independently reported test method per scenario/path."""


def _good_path_test(name, scenario):
    def test(self):
        transcript, _ = run_conversation(scenario["carrier_turns"], ScriptedLLM(scenario["good"]))
        checks = scenario["checks"] + [lambda turns, load, e=scenario["expected"]: __import__("evals.checks", fromlist=["end_call_reason"]).end_call_reason(turns, load, e)]
        for check in checks:
            with self.subTest(check=check.__name__):
                passed, detail = check(transcript, NORMAL_LOAD)
                self.assertTrue(passed, detail)
    return test


def _bad_path_test(name, scenario):
    def test(self):
        transcript, _ = run_conversation(scenario["carrier_turns"], ScriptedLLM(scenario["bad"]))
        check = scenario["bad_check"]
        passed, detail = check(transcript, NORMAL_LOAD)
        self.assertFalse(passed, f"{check.__name__} unexpectedly passed: {detail}")
    return test


for _name, _scenario in SCENARIOS.items():
    setattr(ScenarioTests, f"test_{_name}_good_all_checks", _good_path_test(_name, _scenario))
    setattr(ScenarioTests, f"test_{_name}_bad_{_scenario['bad_check'].__name__}", _bad_path_test(_name, _scenario))
