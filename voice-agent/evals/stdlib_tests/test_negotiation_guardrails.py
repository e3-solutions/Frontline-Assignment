from types import SimpleNamespace
import unittest

from negotiation_guardrails import (
    identity_is_blocked,
    validate_agreement_end,
    validate_price_outcome,
)


class PriceOutcomeTests(unittest.TestCase):
    def test_above_ceiling_cannot_be_ordinary_agreement(self):
        result = validate_price_outcome(2200, above_max=False, raw_max_rate=1800)
        self.assertEqual(result.code, "PRICE_ABOVE_CEILING")

    def test_above_ceiling_may_be_recorded_as_above_max(self):
        self.assertIsNone(
            validate_price_outcome(2200, above_max=True, raw_max_rate=1800)
        )

    def test_in_range_bid_cannot_be_mislabeled_above_max(self):
        result = validate_price_outcome(1700, above_max=True, raw_max_rate=1800)
        self.assertEqual(result.code, "PRICE_NOT_ABOVE_CEILING")

    def test_in_range_ordinary_agreement_is_allowed(self):
        self.assertIsNone(
            validate_price_outcome(1700, above_max=False, raw_max_rate=1800)
        )

    def test_no_rate_mode_allows_positive_ordinary_bid(self):
        self.assertIsNone(
            validate_price_outcome(1900, above_max=False, raw_max_rate=0)
        )

    def test_nonpositive_price_is_rejected(self):
        result = validate_price_outcome(0, above_max=False, raw_max_rate=1800)
        self.assertEqual(result.code, "INVALID_PRICE")

    def test_invalid_ceiling_fails_closed(self):
        result = validate_price_outcome(
            1700,
            above_max=False,
            raw_max_rate="unknown",
        )
        self.assertEqual(result.code, "INVALID_LOAD_PRICING")


class IdentityAndOutcomeTests(unittest.TestCase):
    def test_pending_identity_is_blocked(self):
        context = SimpleNamespace(awaiting_carrier_identity_confirmation=True)
        self.assertTrue(identity_is_blocked(context))

    def test_rejected_identity_is_blocked(self):
        context = SimpleNamespace(carrier_identity_rejected=True)
        self.assertTrue(identity_is_blocked(context))

    def test_confirmed_identity_is_not_blocked(self):
        context = SimpleNamespace(
            awaiting_carrier_identity_confirmation=False,
            carrier_identity_rejected=False,
        )
        self.assertFalse(identity_is_blocked(context))

    def test_agreement_end_requires_persistence(self):
        result = validate_agreement_end(agreement_recorded=False)
        self.assertEqual(result.code, "AGREEMENT_NOT_RECORDED")

    def test_agreement_end_after_persistence_is_allowed(self):
        self.assertIsNone(validate_agreement_end(agreement_recorded=True))


if __name__ == "__main__":
    unittest.main()
