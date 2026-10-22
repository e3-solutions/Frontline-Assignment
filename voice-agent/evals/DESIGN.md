# Frontline evaluation design

## Scope and success criteria

This evaluates the prompt-driven voice agent's observable conversation and
function-call contract: identity before load lookup; truthful/retried lookup;
complete load presentation; profitable safe booking; confidential pricing;
above-max bid handling; agreement close; and safe human handoff. A scenario
passes only when every listed hard requirement and requested interaction check
passes. Missing evidence is `UNKNOWN`, malformed evidence is `ERROR`, and both
make the suite exit nonzero.

## What runs what

| Layer | Command | Meaning |
| --- | --- | --- |
| Grader tests | `python -m unittest evals.test_run_evals` | Tests the evidence grader itself: pass, intentional violation, false-positive guard, missing, malformed. |
| Synthetic regression cases | `python evals/run_evals.py` | Grades representative recorded/simulated traces. These are not model results. |
| Application tests | `pytest tests/test_voice_prompt_guardrails.py` | Existing prompt construction regression tests, when project dependencies are installed. |
| Actual model evaluation | `OPENAI_API_KEY=... python evals/live_agent_eval.py` | Calls the configured model with application prompt/tool definitions and mocks every business tool. |

The live runner bounds each case to at most three caller turns and records model
name plus the full observed trace in `evals/results/live-latest.json`. It uses
the bot's `gpt-4.1`, temperature `0.7`, frequency penalty `0.6`, and presence
penalty `0.5` by default. Run it at least three times before treating a result
as a release signal because model output is nondeterministic.

## Application contract exercised

- Initial identity/load flow: [voice_prompt.py](../voice_prompt.py#L304) builds
  the initial prompt; `bot.py` registers the same standard tools at
  [bot.py](../bot.py#L301) and installs the prompt at [bot.py](../bot.py#L339).
- Negotiation flow: `get_load_context` replaces the system prompt with the
  actual load-specific negotiation prompt at [call_helpers.py](../call_helpers.py#L596),
  constructed by [load_context_utils.py](../load_context_utils.py#L15).
- Canonical schemas: [tool_definitions.py](../tool_definitions.py#L13) through
  [tool_definitions.py](../tool_definitions.py#L105). The live runner imports
  these objects; it does not recreate a fake agent or schemas.

## Mocked boundaries and omissions

The live runner returns deterministic in-memory results for all carrier lookup,
load lookup, agreement recording, end-call, and human transfer calls. It never
imports/runs Daily transport, Supabase writes, carrier APIs, dial-out, or audio
services. STT/TTS, latency, interruptions, real database integrity, and actual
human transfer are out of scope. If credentials are absent, live evaluation is
reported `NOT RUN`, never as a pass.

## Reading diagnostics

Every verdict lists its criterion/check, expected behavior, and observed
assistant turn/tool evidence in the Markdown and JSON reports. A failure trace
is the corresponding observed turn list; this makes it possible to inspect a
bad model output without relying on hidden reasoning.

See `EVIDENCE.md` for completed checks, the intentional-failure demonstration,
and explicitly not-run checks in this workspace.
