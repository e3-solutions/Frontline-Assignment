# Voice-agent evaluations

Run the default suite from `voice-agent/`:

```bash
python3 -m evals.runner --workers 4 --output eval-report.json
python3 -m pytest evals/test_runner.py -q
```

The first command runs independent scenarios in parallel. `--workers` bounds
parallelism; four is the default. It is offline: it uses only deterministic
fixtures, makes no network requests, does not load application credentials,
and cannot write a negotiation, submit a quote, transfer a call, or contact
Slack.

The report has a result for every turn and scenario. `turn_completion_rate`
is the fraction of turns that passed all required/forbidden tool and language
contracts. The latency values in this default report are **synthetic** test
data used to verify the report calculations. They are not service latency and
must not be used as a production SLO.

## Live brain evaluation (explicit opt-in)

`evals/live.py` defines the judge contract. A small-model judge is supplied by
an explicit command, so its model, account, API key, and token cap remain
outside source control. It receives one bounded JSON request per turn and
returns this shape:

```json
{"verdict":"PASS","score":9,"criteria":{"safety_and_confidentiality":2},"evidence":["..."]}
```

Use a cheap approved model, temperature 0, and a 300-token response cap. Run
only changed scenarios, at most five repetitions each, and cap concurrent
judge/model calls separately from the offline `--workers` setting. Judge
results are diagnostic; deterministic hard-safety assertions remain the
release gate.

For a real brain replay, an adapter sends the repository's generated system
prompt, caller transcript, tool schemas, and fixture tool results to the
configured model. It records model first-token/tool-call/final-response times
and passes the observed turn to both deterministic checks and the judge. It
must never use the application's live tool handlers.

## Audio simulation (explicit development integration)

An audio adapter implements `AudioScenarioAdapter`. It can use ElevenLabs TTS
or another approved TTS to play scenario utterances into an isolated Daily
development room, then capture the agent transcript, audio events, tools, and
call outcome. It must deny startup unless all of these are true:

- development Daily room/number is selected;
- tools are fixture-backed or development sandbox endpoints;
- quote submission, real transfer dial-out, Slack, and production Supabase are blocked.

Audio scenarios are independent and may run in parallel, but cap concurrency
to the approved provider quota (normally 1--2 rooms). Text scenarios can run
at higher parallelism. Never run the audio adapter in PR CI.

## Latency definitions

- `brain_first_response_ms`: caller final transcript → first model decision.
- `tool_round_trip_ms`: tool dispatch → mock/provider result.
- `post_tool_response_ms`: tool result → final model response.
- `first_audio_ms`: caller final transcript → first synthesized audio.
- `turn_complete_ms`: caller final transcript → agent stopped speaking.

Report p50/p95 per mode and scenario. Missing timestamps are `NOT_MEASURED`,
not zero. Fail an audio/brain latency budget only after the team sets an SLO
from representative development runs.
