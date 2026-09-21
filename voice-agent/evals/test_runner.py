from .runner import build_report, evaluate_turn, run_parallel
from .models import ExpectedTurn
from .scenarios import SCENARIOS


def test_parallel_suite_has_no_failures():
    results = run_parallel(SCENARIOS, workers=3)
    assert all(result.status == "PASS" for result in results)
    assert build_report(results, "offline")["summary"]["turn_completion_rate"] == 1


def test_hard_safety_violation_is_not_left_to_a_judge():
    turn = ExpectedTurn("test", forbidden_tools=("transfer_to_human",), forbidden_phrases=("2000",))
    result = evaluate_turn(turn, "I can do 2000", ["transfer_to_human"])
    assert not result.passed
    assert len(result.failures) == 2
