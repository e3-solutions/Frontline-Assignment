# Offline voice-agent evaluations

Run from `voice-agent/` after installing the existing test dependencies:

```bash
python3 -m pytest evals -v
```

The harness makes no network calls and imports no production service module. It replays de-identified scripted events (`caller`, `assistant`, `identity_confirmed`, `tool_call`, `tool_result`) and supplies every tool result from the fixture. `identity_confirmed` is an explicit evaluator annotation after a successful lookup and caller confirmation; a lookup alone must not authorize a load. Add scenarios to `golden_traces.py`; use opaque/fake phone numbers and load IDs only. See [DESIGN.md](DESIGN.md) for rationale, criteria, and limitations.

Safety gates are binary and must all pass: carrier verification and confirmation before load lookup, successful load before agreement/transfer, no standard agreement above the loaded maximum rate, valid agreement/bid persistence before its terminal outcome, three not-found MC or load results before their terminal reasons, no tool call after `end_call`, no post-transfer bot end, known tools with results, valid end reasons, and no spoken internal tool names.

Quality is reported separately and currently measures outcome alignment plus a holding phrase immediately before carrier/load lookups. It does not override a safety failure. The seven golden scenarios are agreement, ambiguous-price confirmation before agreement, above-max bid, repeated unknown MC, load-not-found, no-agreement, and human transfer. Six deliberately unsafe traces are asserted to fail distinct gates: load-before-identity, agreement without persistence, bot termination after transfer, above-max bid without contact data, standard agreement above the loaded maximum, and a tool call after termination.

This evaluates semantic traces, not STT accuracy, model compliance, audio timing, or live provider integrations. Those remain outside this offline suite.
