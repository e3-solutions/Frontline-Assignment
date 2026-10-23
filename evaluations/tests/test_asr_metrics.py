import unittest

from evaluations.asr_metrics import (
    mc_entity_error_rate,
    normalise_mc,
    quality_score,
    word_error_rate,
)
from evaluations.run_asr_eval import evaluate


class AsrMetricTests(unittest.TestCase):
    def test_wer_is_case_and_punctuation_insensitive(self):
        self.assertEqual(word_error_rate("Hello, freight!", "hello freight"), 0.0)

    def test_mc_eer_requires_exact_normalised_identifier(self):
        cases = [
            {"expected_mc": "123456", "observed_mc": "MC-123456"},
            {"expected_mc": "765432", "observed_mc": "7654321"},
        ]
        self.assertEqual(normalise_mc("MC-123456"), "123456")
        self.assertEqual(mc_entity_error_rate(cases), 0.5)

    def test_quality_score_is_positive_harmonic_mean_and_penalises_mc_failure(self):
        self.assertEqual(quality_score(wer=0.0, mc_eer=0.0), 1.0)
        self.assertEqual(quality_score(wer=0.1, mc_eer=1.0), 0.0)

    def test_fixture_run_has_diagnostics_and_expected_aggregate(self):
        cases = [
            {
                "id": "a",
                "reference_transcript": "hello there",
                "observed_transcript": "hello there",
                "expected_mc": "123456",
                "observed_mc": "123456",
            },
            {
                "id": "b",
                "reference_transcript": "my MC is 765432",
                "observed_transcript": "my MC is 7654321",
                "expected_mc": "765432",
                "observed_mc": "7654321",
            },
        ]
        result = evaluate(cases)
        self.assertEqual(result["case_count"], 2)
        self.assertEqual(result["mc_entity_error_rate"], 0.5)
        self.assertLess(result["quality_score"], 1.0)
        self.assertEqual(result["cases"][1]["id"], "b")
