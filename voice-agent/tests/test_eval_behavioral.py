"""Calibration controls are deliberately synthetic, not model evaluations."""

from evals.behavioral import run_behavioral_calibration


def test_behavioral_controls_accept_good_and_reject_bad_scripts():
    controls = dict(run_behavioral_calibration().controls)
    assert controls["confidential numeric acceptable"].passed is True
    assert controls["confidential numeric unacceptable"].passed is False
    assert controls["confidential spoken acceptable"].passed is True
    assert controls["confidential spoken unacceptable"].passed is False
    assert controls["agreement contact acceptable"].passed is True
    assert controls["agreement contact unacceptable"].passed is False
    assert controls["agreement contact negated-language unacceptable"].passed is False
    assert controls["verification/load transfer acceptable"].passed is True
    assert controls["verification/load transfer unacceptable"].passed is False
    assert controls["end reason acceptable"].passed is True
    assert controls["end reason unacceptable"].passed is False
