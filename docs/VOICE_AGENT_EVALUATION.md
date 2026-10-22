# Frontline voice-agent evaluation

Run from `voice-agent`:
```bash
python3 -m evals.runner
```

The command writes exactly two reports to `eval_results/`: `pricing-eval.json`
for programmatic detail and `pricing-eval.md` for review. Each row shows the
case ID, expected and actual result, check-level pass/fail reason, and the
fixture's observed agent text, tool calls, results, or transfer outcome. A
non-zero exit means an actual result differed from its expected result.

## Scope and success criteria

The current deterministic golden set prioritizes the most expensive errors:
confidential goal/ceiling price leakage, invalid negotiation boundaries,
no-rate handling, lookup-result ordering, agreement persistence before call
end, unsafe contextless transfers, and MC retry termination. Success is that every good fixture
passes and every deliberately bad fixture is detected. The last run had **14
of 14 expectations passed**.

## Boundaries and assumptions

Fixtures model the transcript and tool trace; they do not call the live agent
or providers. All external dependencies (LLM, Daily, STT/TTS, carrier/load
APIs, database, quote API, and Slack) are therefore absent, so no credentials
or side effects are required. This avoids LLM nondeterminism; no model judge is
used. Existing pytest suites are unverified in this container because Python
3.11 has no `pytest` module and no usable pip, uv, or venv.

## Findings, omissions, and remaining work

`record_agreement` does not explicitly reject negative or NaN prices; this is
recorded as a finding and is not changed here. Omitted: load presentation/dates, empty-input coverage, and
LLM quality judging. Next work is to add the retry cases, run retained pytest
in a provisioned environment, and decide whether to fix the money-validation
finding.
