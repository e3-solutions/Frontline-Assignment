"""Run an offline ASR/MC evaluation from a JSON case file.

Usage:
    python -m evaluations.run_asr_eval
    python -m evaluations.run_asr_eval --cases /secure/spirelight/cases.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluations.asr_metrics import mc_entity_error_rate, quality_score, word_error_rate


DEFAULT_CASES = Path(__file__).parent / "fixtures" / "asr_carrier_cases.json"


def evaluate(cases: list[dict[str, object]]) -> dict[str, object]:
    per_case = [
        {
            "id": case["id"],
            "wer": word_error_rate(
                str(case["reference_transcript"]), str(case["observed_transcript"])
            ),
            "expected_mc": case.get("expected_mc"),
            "observed_mc": case.get("observed_mc"),
        }
        for case in cases
    ]
    wer = sum(row["wer"] for row in per_case) / len(per_case) if per_case else 0.0
    mc_eer = mc_entity_error_rate(cases)
    return {
        "case_count": len(cases),
        "mean_wer": wer,
        "mc_entity_error_rate": mc_eer,
        "quality_score": quality_score(wer=wer, mc_eer=mc_eer),
        "quality_error": 1 - quality_score(wer=wer, mc_eer=mc_eer),
        "cases": per_case,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, help="Optional JSON results path")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text())
    result = evaluate(cases)
    rendered = json.dumps(result, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.write_text(rendered + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
