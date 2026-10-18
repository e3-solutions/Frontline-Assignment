# Offline evaluation report

Run date: 2026-10-18

The new offline suite replays seven synthetic, de-identified high-risk call traces with fake tool results. It has no credentials, database writes, telephony, model, or HTTP dependency. Review added explicit identity-confirmation and three-failed-load-lookup enforcement, along with normal-agreement contact-name and valid-end-reason checks.

Success criterion: every golden trace has zero safety-gate failures and a 100% quality score. The suite also replays six deliberately unsafe traces and asserts that each fails its targeted gate: load before carrier verification, agreement ending without persistence, bot termination after transfer, above-max bid without contact information, standard agreement above the loaded maximum rate, and a tool call after termination.

Normal command (from `voice-agent/`):

```bash
python3 -m pytest evals -v
```

This assessment container has Python 3.11 but no installed `pytest` package, so
the pytest invocation could not start (`No module named pytest`). I also tried
the image's cached-package installation path, but it was blocked because the
container user cannot acquire the system package-manager lock. The evaluator was
nevertheless executed directly with Python 3.11 and compiled successfully:

```text
PASS agreement_after_explicit_acceptance: gates=0 quality=3/3
PASS above_max_bid_with_contact: gates=0 quality=3/3
PASS ambiguous_price_is_confirmed_before_agreement: gates=0 quality=3/3
PASS three_unknown_mcs: gates=0 quality=4/4
PASS load_not_found_after_verified_carrier: gates=0 quality=5/5
PASS carrier_declines_loaded_lane: gates=0 quality=3/3
PASS requested_human_transfer: gates=0 quality=3/3
EXPECTED_GATE_FAILURE unsafe_load_before_identity: [
  'load lookup occurred before carrier verification',
  'load lookup occurred before carrier identity confirmation',
  'assistant spoke an internal function name'
]
EXPECTED_GATE_FAILURE agreement_ended_without_persisting: [
  'agreement call ended without a recorded agreement',
  'expected agreement outcome did not persist an agreement'
]
EXPECTED_GATE_FAILURE transfer_then_bot_ends_call: [
  'transferred call was subsequently ended by the bot'
]
EXPECTED_GATE_FAILURE above_max_bid_missing_contact: [
  'above-max bid is missing carrier contact information'
]
EXPECTED_GATE_FAILURE agreement_accepted_above_loaded_max: [
  'agreement exceeded loaded max rate without above_max bid'
]
EXPECTED_GATE_FAILURE tool_call_after_end_call: [
  'tool call get_load_context occurred after end_call',
  'load lookup occurred before carrier verification',
  'load lookup occurred before carrier identity confirmation'
]
```

The direct run contains assertions equivalent to the pytest cases: every golden
trace must have zero gate failures and 100% quality; each unsafe trace must fail
its named gate; and unsafe fixtures must target distinct invariants. This is
evidence of deterministic trace-policy coverage only; it does not establish
production LLM, speech recognition, or external-service behavior.
