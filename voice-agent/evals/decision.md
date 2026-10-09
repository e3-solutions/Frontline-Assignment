# Evaluation decisions

## Scope and priorities

This suite preserves the single-prompt architecture and production code. It
focuses on the most expensive, observable mistakes: selecting the wrong load,
discarding greeting/history when prompt context switches, recording or quoting
an above-limit rate as an agreement, losing a valid agreement's identifiers,
and transferring before policy requirements are known. These handler
boundaries are higher confidence and lower-cost than pretending an offline
fixture can prove a live voice conversation is safe.

Implemented real-handler scenarios are: successful, invalid, and missing load
lookups; normal above-max agreement; above-max follow-up; below-ceiling
agreement; save failure; one transfer fixture; and valid/invalid `end_call`.
Existing mocked carrier-verification/phone-persistence and transfer
load/routing regressions remain in `test_phone_carrier_lookup.py` and
`test_transfer_tool_handler.py`; they are reported separately, not double
counted. Real normalizer/prompt contracts cover ordinary, no-rate, formatted,
and equal opening/goal fixtures. A payload check is evidence for its parent
scenario, not a separate scenario.

## Reasoning and success criteria

- A successful lookup must replace only the system prompt, preserve history,
  store load state, and update the call record. Invalid/missing references must
  return errors without changing the greeting/history; the missing-load probe
  records that the handler passes `org_id` to its lookup boundary.
- A strictly above-max normal agreement must neither save nor quote. This is a
  failing product finding today because mocked calls are observed.
- An above-max follow-up may save its complete load/price/call/contact payload
  only without a quote. A below-ceiling agreement must save the complete
  payload and issue the correct quote payload. If a mocked save returns `None`,
  the handler must return its database error and not quote.
- The transfer fixture observes actual handler behavior, but not a settled
  product requirement: with a routable load and `carrier_identity_confirmed`
  false, the direct handler transfers. Phone-first identity state is gated by
  `HIGHWAY_PHONE_LOOKUP_ENABLED` upstream, so the false flag is not known to be
  authoritative in configurations where that feature is disabled or absent.
  This remains **unresolved**, rather than an asserted product failure.
- `end_call` with `agreement` must set state and queue an `EndFrame`; an invalid
  reason must return an error without either side effect.
- Real prompt contracts show missing rates normalize to `0.0` and use no-rate
  instructions, while formatted rates parse correctly. Equal opening/goal is a
  finding: the prompt both requires the opening amount and forbids the equal
  internal-goal amount.
- The Room1 disclosure grader passes only if it accepts safe planted text and
  rejects planted target/ceiling disclosure. That rejection validates the
  grader; it does not describe a live model failure. Room2 is excluded because
  internal-rate discussion with the broker is legitimate there.

## Assumptions and mocked boundaries

All scenarios use dummy Supabase values, fixture loads, mock database/quote/
transfer boundaries, and a socket-level no-network guard. Results prove handler
control flow and attempted mock calls, not actual database durability, quote
delivery, authentication, or provider behavior. The lookup test documents a
known limitation: `get_load_by_reference` receives `org_id`, but its current
implementation ignores it because the KCH load rows lack tenant ownership.
This is not represented as passing tenant isolation.

## Measurement trade-offs

The CLI and pytest call shared scenario functions so their contracts do not
drift. Pytest reports harness execution; real-handler and synthetic-calibration
counts stay separate in the report. The explicit `--run-count` repeats
deterministic mocks, helping detect run instability but providing no estimate of
live-model reliability. The runner exits nonzero for real-handler failures or
prompt-contract findings or execution/harness errors; unresolved policy is
counted and explained, not silently converted into either a pass or a failure.
Each completed run is retained in JSON; aggregate verdicts derive from that
captured evidence and fail if any run fails. The report identifies both the
evaluated source revision and working-tree changes.

Synthetic behavioral controls pair acceptable and unacceptable scripts for
numeric/spoken confidentiality disclosure, agreement acceptance/contact,
verification/load before transfer, and outcome-to-end-reason mapping. They
calibrate deterministic rules only; no live-model response is inferred.

## Omissions, limitations, and follow-up

This suite does not cover a live LLM, STT/TTS, Daily rooms, audio timing,
concurrency, real credentials, persistence, quote delivery, or end/close-call
ordering. Exact-ceiling behavior remains ambiguous in the prompt and is not
claimed. Follow-up work should decide transfer identity policy across feature
flags, add a real tenant-ownership model before testing isolation, resolve
exact-ceiling and close-ordering business rules, then add controlled model/audio
evaluations with approved non-production infrastructure.
