# Status

No live model run was possible in this sandbox (no `OPENAI_API_KEY`, `openai`/`pipecat`/`pytest`/`pip`), so the evidence provided is the offline suite (15 tests) and the live tier is designed and SKIP-tested but unexecuted.

# Scope and why

Risks, in order: confidential pricing leaks; countering above a below-goal bid or recording above ceiling without `above_max`; invented lookup outcomes; closing sequence (contact before `record_agreement`, correct `end_call` reason); three-strike MC handling; dead air or spoken tool names. These can lose money, create bad records, or damage calls. Tone and naturalness matter, but need a live judge and are lower priority than these deterministic safety failures.

# How it works

Tier 1 tests the real prompt builders, then checker self-tests run a good and a bad scripted path for every scenario. The harness accepts a pluggable LLM backend. Fake handlers mirror `call_helpers` return shapes. A `FunctionSchema` shim and an `src` namespace shim are mocked boundaries. Tier 2, `run_live.py`, uses `gpt-4.1` with production sampling settings, runs each scenario N times, requires 100% for safety checks and 67% for others, and writes per-run JSON results.

# Success criteria and nondeterminism

Temperature 0.7 matches production, so repeated runs measure sampled behavior rather than hiding variance with temperature 0. Safety failures are unacceptable in any run; non-safety behavior needs a majority threshold while more samples accumulate.

# Mocked boundaries and unverified behavior

Highway, Supabase, KCH, Slack, Daily, Deepgram, Cartesia, and Pipecat aggregation/turn-taking are mocked. Unverified: audio ASR errors on MCs/dollar amounts, transfer/Room2, phone-verified greeting, Zone-2 counter count and $25–100 increments, and real DB writes.

# Assumptions

“Same turn” for the third MC strike means before the next carrier message. The $1,650 scripted counter avoids confidential $1,600. Fakes must track `call_helpers` shapes, creating maintenance risk.

# Review findings

Review found the contact regex could be satisfied by an MC turn and the leak check hardcoded fixture values; both were fixed and covered by a new bad path. The leak check still misses loose verbal forms such as “sixteen-fifty-ish”; the live tier should add an LLM leak judge calibrated against the deterministic check.

# Recommended small repo change

`shared/src/__init__.py` eagerly imports `httpx`, blocking the pure prompt module in a bare environment. A lazy import would remove the `src` shim. This was not changed to keep the agent untouched.

# Questions for the team

Which failure has cost real money? Are stored transcripts available for replay? What is the budget for nightly live runs and model-snapshot pinning? Is `above_max` success or soft failure? Are counter increments hard rules?

# Next steps in priority order

1. Run Tier 2 with credentials and retain JSON baselines.
2. Add anonymized transcript replay cases.
3. Calibrate a live leak judge for loose verbal forms.
4. Decide reporting treatment for `above_max` and counter rules.

# Evidence

```text
test_every_prompt_end_reason_is_schema_supported ... ok
test_forbidden_amount_section_names_goal_and_ceiling ... ok
test_prompt_uses_only_declared_tool_names ... ok
test_budget_probe_bad_no_confidential_leak ... ok
test_budget_probe_good_all_checks ... ok
test_contact_required_bad_record_agreement_guard ... ok
test_contact_required_good_all_checks ... ok
test_mc_three_strikes_bad_lookup_outcomes_grounded ... ok
test_mc_three_strikes_good_all_checks ... ok
test_zone1_accept_bad_record_agreement_guard ... ok
test_zone1_accept_good_all_checks ... ok
test_zone2_negotiate_bad_no_confidential_leak ... ok
test_zone2_negotiate_good_all_checks ... ok
test_zone3_above_max_bad_record_agreement_guard ... ok
test_zone3_above_max_good_all_checks ... ok

----------------------------------------------------------------------
Ran 15 tests in 0.004s

OK

SKIPPED: OPENAI_API_KEY is not set
```
