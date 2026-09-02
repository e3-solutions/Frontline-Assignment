"""Regression tests for prompt-level carrier-confirmation guardrails."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_VOICE_AGENT = Path(__file__).resolve().parent.parent
if str(_VOICE_AGENT) not in sys.path:
    sys.path.insert(0, str(_VOICE_AGENT))

from voice_prompt import (  # noqa: E402
    get_initial_greeting_prompt,
    get_known_carrier_greeting_prompt,
)


class KnownCarrierPromptGuardrails(unittest.TestCase):
    """Phone-verified greeting must keep the deny-and-reverify guardrails
    while keeping identity persistence backend-owned.

    When the caller denies the pre-verified carrier and
    re-verifies a different MC, the new identity must be treated as fresh
    and verbally confirmed before asking for a reference number.
    """

    def setUp(self):
        self.prompt = get_known_carrier_greeting_prompt(
            "Wallin Transport LLC", "KCH"
        )

    def test_phone_verified_block_has_identity_replacement_rule(self):
        # The IDENTITY REPLACEMENT RULE is what tells the LLM that a
        # successful verify_carrier in the fallback path INVALIDATES the
        # original phone-verified identity. Without this clause the LLM
        # treats the phone pre-verification as still authoritative and
        # skips the new identity's verbal confirmation.
        self.assertIn("IDENTITY REPLACEMENT RULE", self.prompt)
        self.assertIn("REPLACED", self.prompt)
        self.assertIn("brand-new identity", self.prompt)

    def test_worked_deny_then_reverify_example_present(self):
        # Worked examples are the highest-leverage way to get LLM
        # compliance on a step the prompt's CRITICAL notes alone failed
        # to produce.
        self.assertIn("EXAMPLE — DENY THEN REVERIFY", self.prompt)
        self.assertIn("verify_carrier(mc_number=\"555555\")", self.prompt)
        self.assertIn("ABC Trucking LLC", self.prompt)
        self.assertIn("Text only", self.prompt)

    def test_worked_example_substitutes_carrier_name(self):
        # The example references the DENIED original identity by the
        # carrier_name placeholder. Substitution is what makes the
        # example concrete to the LLM in this call.
        self.assertIn("Wallin Transport LLC", self.prompt)
        # The example explicitly contrasts the original with the new one.
        self.assertIn("original phone-verified identity", self.prompt)
        self.assertIn("(Wallin Transport LLC) was DENIED", self.prompt)

    def test_critical_notes_still_present(self):
        # The LLM still owns the spoken confirmation flow, but not the
        # persistence side effect.
        self.assertIn(
            "Step 3a's \"Is this [name]?\" question is mandatory",
            self.prompt,
        )
        self.assertIn(
            "backend records the confirmed identity automatically",
            self.prompt,
        )
        self.assertNotIn("confirm_carrier_identity", self.prompt)


class UnknownCarrierPromptParityCheck(unittest.TestCase):
    """The unknown-carrier flow doesn't have the deny-and-reverify hazard
    (no phone pre-verification to override), but it should also avoid the
    old identity-confirmation tool in the prompt."""

    def test_identity_confirmation_tool_absent_when_flag_on(self):
        prompt = get_initial_greeting_prompt("KCH", phone_first_enabled=True)
        self.assertNotIn("confirm_carrier_identity", prompt)
        self.assertIn("backend records the confirmed identity automatically", prompt)

    def test_confirm_carrier_identity_absent_when_flag_off(self):
        # With phone-first off, the tool isn't registered, so the prompt
        # must not reference it (otherwise the LLM hallucinates a
        # function call).
        prompt = get_initial_greeting_prompt("KCH")
        self.assertNotIn("confirm_carrier_identity", prompt)


if __name__ == "__main__":
    unittest.main()
