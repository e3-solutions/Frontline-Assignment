# Frontline voice-agent evaluations

The default evaluation is deterministic, credential-free, and side-effect-free. It grades stored conversation/tool traces and directly tests production handlers with mocked persistence and integrations.

## Run

From `voice-agent/`:

```bash
python3 -m evals.runner --output evals/results/offline-report.json
python3 -m unittest discover -s evals/stdlib_tests -v
python3 -m pytest evals/tests tests ../shared/tests -q
```

Install the test dependencies first when pytest is unavailable:

```bash
python3 -m pip install -r tests/requirements-test.txt
```

The trace runner exits nonzero when a fixture's observed result differs from its declared `expected_pass`. Negative fixtures therefore pass the suite only when the graders reject them for the expected reason. An empty or incomplete trace can never receive a vacuous pass.

## Interpretation

- `grader_pass=true` means the trace has no deterministic findings.
- A line beginning `PASS` means the grader result matched the fixture's expectation. This includes intentionally broken fixtures that were correctly rejected.
- Critical findings include confidential-rate disclosure, ordinary agreement above the ceiling, wrong identity use, accepted-quote side effects for rejected bids, premature MC termination, and inconsistent end reasons.

The checked-in `evals/results/offline-report.json` is evidence from the latest offline run. It contains deliberately failing examples to demonstrate detection, not unresolved production failures.

The human-readable evidence and limitations summary is in [`EVALUATION_REPORT.md`](EVALUATION_REPORT.md).

## Optional model critic

Set both variables to enable a nondeterministic critic from application code:

```bash
export OPENAI_API_KEY=...
export EVAL_CRITIC_MODEL=gpt-5.6-sol
```

`evals.critic.critique(trace)` calls the OpenAI Responses API and asks the configured model to judge implied agreement, subtle confidentiality disclosure, coherence, and conversation quality. The model name is configurable because availability varies by API project. The assessment documents `gpt-5.6-sol`; use `gpt-6-astra` only if the supplied API project exposes that identifier.

Run it with:

```bash
EVAL_CRITIC_RUNS=3 python3 -m evals.runner --critic --output evals/results/critic-report.json
```

The critic is optional, is never invoked by the offline command, and cannot override deterministic safety failures. Its results should be labeled nondeterministic and reviewed with the supporting evidence.

## Safe boundaries

The default suite must mock Supabase, Daily, Highway, the legacy carrier API, KCH/Cognito, Slack, OpenAI, Deepgram, and Cartesia. Handler tests patch side-effecting production methods. No production credential is required. Real LLM behavior, acoustics, PSTN transport, latency, barge-in, and SIP interoperability remain unverified until explicitly exercised in a sandbox.
