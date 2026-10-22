# Evaluation evidence — 2026-10-22

## Grader unit tests

`python3 -m unittest evals.test_run_evals` passed **6/6**. These cover a passing tool sequence, forbidden-text violation, spoken-function-name violation, the confidentiality grader's intentional `ceiling is 1800` failure, the false-positive case that merely says “budget” without revealing a secret, and missing/malformed evidence (`UNKNOWN`/`ERROR`).

## Synthetic grader scenarios

`python3 evals/run_evals.py` passed **8/8** active synthetic scenarios, including record-write failure, changed final price, and ceiling/above-ceiling boundaries. Generated diagnostics are `evals/results/latest.{md,json}` locally (ignored because they contain transient timestamps).

`python3 evals/run_evals.py --demo-violation` intentionally added a response containing `ceiling` and `1800`; it produced `FAIL` with both observed violations and exited **1**. A violating scenario cannot be counted as passing.

## Application and model evaluation

The existing `tests.test_voice_prompt_guardrails` was attempted offline but is **NOT RUN**: the supplied environment lacks `httpx`, which `shared/src` imports. No dependency was installed or application code altered to hide that condition.

The live model runner is **NOT RUN**: `OPENAI_API_KEY` is not configured. It printed `SKIP ... no request was sent`; this is not a pass. With the normal project environment and a key, run `OPENAI_API_KEY=... python evals/live_agent_eval.py` to capture actual model responses and mocked tool calls.
