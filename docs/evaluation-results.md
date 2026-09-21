# Evaluation run evidence

Date: 2026-09-21  
Command: `cd voice-agent && python3 -m evals.runner --workers 4 --output /tmp/eval-report.json`

Result: **6/6 P0 scenarios passed**; **13/13 turns completed** (100%). The
run completed using four parallel workers. The report recorded a synthetic
p50/p95 first-audio field of 145 ms. This is evidence that the evaluator's
parallel execution and metric aggregation work; it is explicitly not evidence
of production latency because no STT, LLM, TTS, Daily, or network provider ran.

The completed scenarios were happy-path agreement, three invalid MCs, invalid
load-reference rejection, confidential-pricing protection, above-max bid
handling, and premature-transfer prevention. Every external boundary was
fixture-backed; no credentials or production side effects were used.

The environment used for this evidence did not have `pytest` installed, so the
pytest command is documented but was not executed here. Python bytecode
compilation of `evals/` completed successfully. The repository's normal test
requirements include pytest and should be installed before CI execution.
