# Voice-agent evaluation suite

This directory is an offline, fixture-driven evaluation harness.  It never
starts the telephony stack or contacts Daily, Supabase, carrier lookup, or an
LLM provider.  A scenario supplies an observed transcript and tool calls; the
runner checks the observable policy contract and writes diagnostics.

## Run

```bash
cd voice-agent
python evals/run_evals.py
python -m unittest evals.test_run_evals
```

The command reads `evals/scenarios.json` and writes `evals/results/latest.json`
and `evals/results/latest.md`.  Planned scenarios are deliberately skipped so
the skeleton stays runnable while cases are added.

## Live agent evaluation (opt-in)

`live_agent_eval.py` calls the same prompt builders and canonical tool schemas
used by `bot.py`; it sends conversation turns to the configured OpenAI model and
evaluates its returned text and function calls. Tool results are in-memory
mocks, so it makes no telephony, database, carrier-lookup, or transfer side
effects.

```bash
cd voice-agent
OPENAI_API_KEY=... python evals/live_agent_eval.py
```

It writes `evals/results/live-latest.json`, including the model transcript and
all observed tool calls. `FRONTLINE_EVAL_MODEL` can override the production
default (`gpt-4.1`). This runner is intentionally opt-in because it has cost
and nondeterministic outputs; the fixture suite remains the credential-free
regression baseline.

## Scenario contract

Each active scenario has `turns` and `expectations`.  An assistant turn may
contain `text` and zero or more `tools`, for example:

```json
{
  "speaker": "assistant",
  "text": "Let me check that.",
  "tools": [{"name": "verify_carrier", "arguments": {"mc_number": "123"}}]
}
```

Hard expectations (`forbidden_text`, `required_text`, `required_tools`,
`forbidden_tools`, `required_tool_sequence`, `tool_arguments`, and `end_reason`)
fail the scenario.  `quality` is intentionally a small,
auditable heuristic score rather than an opaque model judge.  Real LLM and
speech-provider behavior remains out of scope; the fixtures represent their
captured or simulated outputs.

## Adding a case

Change one entry in `scenarios.json` from `planned` to `active`, add its fixture
turns and expectations, then run the command above.  Keep each scenario focused
on one product risk, though it may assert several consequences of that risk.
