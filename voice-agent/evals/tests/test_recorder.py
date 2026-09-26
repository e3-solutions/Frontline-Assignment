from evals.recorder import TraceRecorder


def test_recorder_preserves_conversation_tool_order_and_side_effects():
    recorder = TraceRecorder("example", {"ceiling_rate": 1800})
    recorder.caller("I need twenty-two hundred.")
    recorder.assistant("I cannot agree to that rate.")
    recorder.tool_call("end_call", {"reason": "no_agreement"})
    recorder.tool_result("end_call", {"status": "success"})
    recorder.side_effect("call_update", end_reason="no_agreement")

    assert [event.type for event in recorder.trace.events] == [
        "caller",
        "assistant",
        "tool_call",
        "tool_result",
    ]
    assert recorder.trace.side_effects == [
        {"type": "call_update", "end_reason": "no_agreement"},
    ]
