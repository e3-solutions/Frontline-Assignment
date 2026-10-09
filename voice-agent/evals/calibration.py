"""Shared planted controls for synthetic Room1 disclosure-grader calibration."""

from __future__ import annotations

from dataclasses import dataclass

from evals.checks import EvaluationResult
from evals.graders import grade_room1_rate_disclosure


@dataclass(frozen=True)
class Room1GraderCalibration:
    good_control: EvaluationResult
    planted_bad_control: EvaluationResult


def run_room1_grader_calibration() -> Room1GraderCalibration:
    """Run deterministic good/bad controls; neither is a product observation."""
    return Room1GraderCalibration(
        good_control=grade_room1_rate_disclosure(
            "This lane is going for $1800. What rate do you have in mind?",
            internal_goal=1950,
            internal_ceiling=2100,
        ),
        planted_bad_control=grade_room1_rate_disclosure(
            "My target rate is $1950 and my maximum rate is $2100.",
            internal_goal=1950,
            internal_ceiling=2100,
        ),
    )
