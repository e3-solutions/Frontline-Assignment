"""Calibration tests for synthetic Room1 disclosure grading controls."""

from evals.calibration import run_room1_grader_calibration


def test_room1_disclosure_grader_accepts_good_and_rejects_planted_bad_control():
    """These are planted traces, not observed live-model product behavior."""
    calibration = run_room1_grader_calibration()

    assert calibration.good_control.passed is True
    assert calibration.planted_bad_control.passed is False
    assert "Synthetic Room1 trace contains confidential-rate material." in (
        calibration.planted_bad_control.evidence
    )
