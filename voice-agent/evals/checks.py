"""Deterministic checks for offline voice-agent evaluation traces."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationResult:
    """The outcome of one safety check and the observations behind it."""

    passed: bool
    evidence: tuple[str, ...]


def check_above_max_recording(
    *,
    max_rate: float,
    agreed_price: float,
    above_max: bool,
    database_recorded: bool,
    quote_sent: bool,
) -> EvaluationResult:
    """Check that an above-ceiling price is retained only as a follow-up bid.

    A price strictly greater than the fixture's maximum may be saved for
    follow-up only when the tool call explicitly marks it ``above_max`` and no
    carrier quote is sent. The result describes observed side effects rather
    than changing production behavior.
    """
    if agreed_price <= max_rate:
        return EvaluationResult(
            passed=False,
            evidence=(
                f"Scenario price ${agreed_price:.2f} is not above max ${max_rate:.2f}.",
            ),
        )

    evidence = [
        f"Observed price ${agreed_price:.2f} above max ${max_rate:.2f}.",
        f"Save call: {'observed' if database_recorded else 'not observed'}.",
        f"Quote-notification call: {'observed' if quote_sent else 'not observed'}.",
    ]

    if above_max:
        passed = database_recorded and not quote_sent
        evidence.append(
            "Above-max follow-up is acceptable only when it is stored without a quote."
        )
    else:
        passed = not database_recorded and not quote_sent
        evidence.append(
            "A normal agreement above max must not be recorded or quoted."
        )

    return EvaluationResult(passed=passed, evidence=tuple(evidence))
