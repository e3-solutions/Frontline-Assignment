"""Metrics for transcript and carrier-MC extraction evaluation.

These functions intentionally have no provider dependency.  A production run can
write Deepgram transcripts and the MC selected by the agent into JSON, while CI
uses the checked-in synthetic fixtures.
"""

from __future__ import annotations

import re
from collections.abc import Iterable


def normalise_text(text: str) -> list[str]:
    """Return a conservative, case/punctuation-insensitive token sequence."""
    return re.findall(r"[a-z0-9]+(?:'[a-z0-9]+)?", text.lower())


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Calculate WER using token-level Levenshtein distance.

    WER is not capped: insertions can legitimately make it greater than one.
    An empty reference has WER 0 only when the hypothesis is also empty.
    """
    ref = normalise_text(reference)
    hyp = normalise_text(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0

    previous = list(range(len(hyp) + 1))
    for ref_index, ref_token in enumerate(ref, start=1):
        current = [ref_index]
        for hyp_index, hyp_token in enumerate(hyp, start=1):
            current.append(
                min(
                    previous[hyp_index] + 1,
                    current[hyp_index - 1] + 1,
                    previous[hyp_index - 1] + (ref_token != hyp_token),
                )
            )
        previous = current
    return previous[-1] / len(ref)


def normalise_mc(value: str | None) -> str | None:
    """Normalise an MC identifier to digits, matching the service's behavior."""
    if value is None:
        return None
    digits = "".join(character for character in str(value) if character.isdigit())
    return digits or None


def mc_entity_error_rate(cases: Iterable[dict[str, object]]) -> float:
    """Fraction of MC-bearing cases whose selected MC is absent or incorrect."""
    mc_cases = [case for case in cases if normalise_mc(case.get("expected_mc"))]
    if not mc_cases:
        return 0.0
    errors = sum(
        normalise_mc(case.get("expected_mc")) != normalise_mc(case.get("observed_mc"))
        for case in mc_cases
    )
    return errors / len(mc_cases)


def harmonic_mean(scores: Iterable[float]) -> float:
    """Return a zero-safe harmonic mean of bounded positive quality scores."""
    values = list(scores)
    if not values or any(value <= 0 for value in values):
        return 0.0
    return len(values) / sum(1 / value for value in values)


def quality_score(*, wer: float, mc_eer: float) -> float:
    """Safety-weighted positive score: H(max(0, 1-WER), 1-MC-EER).

    The harmonic mean makes a weak component constrain the total.  It is a
    *positive* score (one is best).  Its complement, ``1 - quality_score``, is
    an error score and must not be called a positive quality score.
    """
    transcript_accuracy = max(0.0, 1.0 - wer)
    mc_accuracy = max(0.0, 1.0 - mc_eer)
    return harmonic_mean([transcript_accuracy, mc_accuracy])
