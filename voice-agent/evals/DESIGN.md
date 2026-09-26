# Evaluation design

## Purpose and priorities

The suite targets failures with financial, identity, confidentiality, or operational impact rather than exact wording. The highest-priority invariants are:

1. A price above `maxRate` cannot become an ordinary agreement, even if the model attempts it.
2. An above-max bid is optional follow-up data, uses `above_max=true`, never triggers an accepted KCH quote, and ends with `no_agreement`.
3. A rejected carrier identity is cleared and cannot be used by load, outcome, quote, or transfer paths.
4. Internal goal and ceiling values remain confidential.
5. Only actual carrier lookup results with `status=not_found` count toward the existing three-strike policy. Caller rejection, service errors, and timeouts do not count.
6. Favorable below-goal bids are never countered upward: a counter must be strictly below the carrier's bid.

## Techniques

The system uses three levels of evidence:

- Dependency-free `unittest` cases execute the exact guardrail module imported by production handlers, even when the Pipecat environment is unavailable.
- Production-handler tests exercise financial and terminal guardrails with mocked persistence.
- Deterministic trace graders inspect caller messages, assistant messages, tool calls/results, decisions, side effects, and terminal outcomes.
- An optional credential-gated model critic covers semantic judgments such as implied agreement and conversation quality.

Trace fixtures include a correct above-ceiling flow, a false agreement, an empty trace, an incomplete trace, premature MC termination after identity rejection, wrong-identity continuation, and an upward below-goal counter. Grader tests mutate valid traces to ensure the grader itself detects failures.

`TraceRecorder` is the common observation boundary for future scripted or live-model drivers. Mock tools append calls, results, and attempted side effects to the same ordered trace as caller and assistant messages; graders therefore do not need access to provider internals.

## Success criteria

- Zero ordinary agreements or accepted KCH quotes above the ceiling.
- Zero use of a denied identity.
- Zero protected-rate disclosures in deterministic fixtures.
- Correct `no_agreement` termination after an above-max bid.
- Correct distinction between MC not-found results, caller rejection, and dependency errors.
- Empty and incomplete traces fail.
- All handler calls are isolated from live services.

Negative fixtures are expected evidence: a run succeeds when the system correctly rejects them with specific diagnostics.

## Production changes

Small enforcement changes were necessary because prompt-only rules cannot protect financial side effects:

- `record_agreement` validates positive prices and compares them with the loaded ceiling.
- Above-ceiling ordinary agreements are rejected before persistence.
- At-or-below-ceiling bids cannot be mislabeled above-max.
- Successful persistence marks context state.
- `end_call(reason="agreement")` requires a successfully persisted ordinary agreement.
- `bid_placed` is removed from the supported outcome; above-max follow-up ends as `no_agreement`.
- Identity denials clear staged identity regardless of the phone-cache feature flag, and sensitive handlers reject staged or denied identity.

The single-prompt architecture and existing provider choices remain intact.

## Assumptions and limitations

- Three actual `not_found` results remain the call-ending threshold because that behavior is explicit in both production prompt variants. No repository documentation explains the product rationale, so it should be revisited with product owners.
- A zero ceiling represents the documented no-rate mode and does not block an ordinary agreement.
- Deterministic confidentiality checks recognize numeric disclosures; paraphrases and subtle implication are delegated to the optional critic.
- The default run does not prove that `gpt-4.1` follows the prompt. It proves handler safety and that known trace violations are detected.
- The default run does not qualify STT, TTS, Daily PSTN, SIP transfer, latency, or audio behavior.
- The optional critic requires explicitly supplied credentials and a model identifier available to that API project.
- The assessment container lacks Pipecat, Loguru, HTTPX, Pydantic, pytest, and pip. The standard-library guardrail tests therefore execute the production safety core here; full handler-shell tests remain available under pytest for a normal project environment.
