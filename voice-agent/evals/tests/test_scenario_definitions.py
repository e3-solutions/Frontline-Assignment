from evals.scenarios import SCENARIOS


def test_priority_scenarios_are_defined():
    assert {
        "valid_carrier_and_load",
        "three_mc_not_found",
        "wrong_identity_rejected",
        "below_goal",
        "above_ceiling_spontaneous_acceptance",
        "above_ceiling_no_agreement",
    } <= set(SCENARIOS)


def test_mc_policy_does_not_count_denial_or_service_error_as_strike():
    scenario = SCENARIOS["three_mc_not_found"]
    assert "count identity denial or service error as a strike" in scenario["forbidden"]


def test_above_ceiling_policy_forbids_agreement_and_kch_quote():
    scenario = SCENARIOS["above_ceiling_spontaneous_acceptance"]
    assert "agreement language" in scenario["forbidden"]
    assert "KCH quote" in scenario["forbidden"]
