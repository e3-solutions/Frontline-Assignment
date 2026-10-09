# Offline voice-agent evaluations

Read the [decision note](decision.md) for scope and trade-offs, and the saved
[Markdown report](report.md) or machine-readable [JSON report](report.json)
for the latest completed evidence.

This suite exercises production handlers with deterministic fixtures only. It
does not change production code, use credentials, contact a network service,
or claim live-model/audio coverage. A socket tripwire fails unexpected network
connections; database, quote, and transfer boundaries are mocks, so a mock
call means a call was attempted, not that persistence or delivery completed.

The report has four separate sections: existing mocked regression tests,
real-handler evaluations, real normalizer/prompt-builder contracts, and
synthetic calibration controls. Existing carrier-verification coverage lives in
`tests/test_phone_carrier_lookup.py`; existing transfer load/routing coverage
lives in `tests/test_transfer_tool_handler.py`. They remain regression tests,
not newly counted evaluation scenarios.

## One setup and run sequence

From a fresh checkout at the repository root, use Python 3.11 and `uv`:

```bash
cd voice-agent
uv venv --seed --python 3.11 .venv
.venv/bin/python -m pip install -r requirements.txt -r tests/requirements-test.txt
SUPABASE_URL=http://test-suite.local SUPABASE_SERVICE_ROLE_KEY=test-key \
  .venv/bin/python -m pytest \
  tests/test_eval_replay.py tests/test_eval_agreement.py \
  tests/test_eval_transfer.py tests/test_eval_prompt_grading.py \
  tests/test_eval_end_call.py tests/test_eval_prompt_contracts.py \
  tests/test_eval_behavioral.py tests/test_eval_runner.py -q
SUPABASE_URL=http://test-suite.local SUPABASE_SERVICE_ROLE_KEY=test-key \
  .venv/bin/python -m evals --run-count 1
```

`--run-count` repeats the same deterministic mocked scenario set. It is useful
for checking runner repeatability, but it is not a sample of model reliability
and must not be interpreted as one. The complete command runs the shared
handler scenarios and the pytest harness, then overwrites `report.md` and
`report.json` with commit, UTC timestamp, duration, run count, exact pytest
exit/output, scenario table, evidence, and its own exit decision.
The report names both the evaluated Git revision and working-tree changes; the
JSON retains each completed run instead of only the last one. An aggregate
scenario fails if any captured run fails.

## Reading results and exit codes

The report separates four different measurements:

- Pytest harness results: whether the shared mocks and assertions execute as
  intended. They are not a product pass percentage.
- Real-handler evaluations: ten distinct handler scenarios. Percentages use
  the explicit resolved denominator (`pass + fail`); unresolved policy cases
  are reported separately rather than folded into that percentage. Multiple
  assertions/payload fields are evidence for one scenario, not additional
  scenarios.
- Prompt contracts: real normalizer/prompt-builder results, with their own
  pass/fail denominator.
- Synthetic grader calibration: planted Room1 and behavioral text controls.
  Bad text correctly being rejected is a calibration pass, not a product
  failure.

Prompt contracts run the real normalizer and negotiation-prompt builder for
ordinary priced, no-rate, formatted-rate, and equal opening/goal fixtures.
Contradictions are reported as findings; expectations are not relaxed to turn a
finding into a pass. Behavioral controls are scripted good/bad traces for
numeric and spoken confidential-rate disclosure, agreement/contact handling,
verification/load-before-transfer ordering, and outcome-appropriate end
reasons. They calibrate deterministic graders only; they are not observed model
behavior.

The runner exits `1` when a real-handler or prompt-contract scenario fails, or
the runner/pytest errors. It reports unresolved policy assumptions separately.
The current saved run exits `1` because the normal above-max agreement path
makes mocked save and quote calls and the equal opening/goal prompt contract
has contradictory required/forbidden instructions. The transfer fixture is
unresolved, not counted as a product failure, because the feature-flag policy
is not settled.
