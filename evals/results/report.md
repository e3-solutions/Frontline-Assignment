# Voice-agent evaluation report

> **FINDING — EXPECTED FAILURE:** An above-ceiling accepted agreement can call the external quote notifier when the LLM sends `above_max=false`. See `evals/DESIGN.md`; no product fix was applied.

## unittest run
test_accepted_agreement_notifies_once_with_price_mc_and_load (test_layer_a.LayerA.test_accepted_agreement_notifies_once_with_price_mc_and_load) ... ok
test_end_call_after_transfer_is_ignored (test_layer_a.LayerA.test_end_call_after_transfer_is_ignored) ... ok
test_finding_above_ceiling_accepted_agreement_must_not_notify_quote (test_layer_a.LayerA.test_finding_above_ceiling_accepted_agreement_must_not_notify_quote)
FINDING: current handler trusts above_max from the LLM and submits this quote. ... expected failure
test_prompts_contain_non_disclosure_and_function_name_rules (test_layer_a.LayerA.test_prompts_contain_non_disclosure_and_function_name_rules) ... ok
test_transfer_without_load_is_blocked (test_layer_a.LayerA.test_transfer_without_load_is_blocked) ... ok
test_unknown_load_cannot_produce_quote (test_layer_a.LayerA.test_unknown_load_cannot_produce_quote) ... ok
test_bad_mc_1 (test_layer_b_openai.LayerBOpenAI.test_bad_mc_1) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_bad_mc_2 (test_layer_b_openai.LayerBOpenAI.test_bad_mc_2) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_bad_mc_3 (test_layer_b_openai.LayerBOpenAI.test_bad_mc_3) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_ceiling_1 (test_layer_b_openai.LayerBOpenAI.test_ceiling_1) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_ceiling_2 (test_layer_b_openai.LayerBOpenAI.test_ceiling_2) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_ceiling_3 (test_layer_b_openai.LayerBOpenAI.test_ceiling_3) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_happy_1 (test_layer_b_openai.LayerBOpenAI.test_happy_1) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_happy_2 (test_layer_b_openai.LayerBOpenAI.test_happy_2) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_happy_3 (test_layer_b_openai.LayerBOpenAI.test_happy_3) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_human_1 (test_layer_b_openai.LayerBOpenAI.test_human_1) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_human_2 (test_layer_b_openai.LayerBOpenAI.test_human_2) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_human_3 (test_layer_b_openai.LayerBOpenAI.test_human_3) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_max_1 (test_layer_b_openai.LayerBOpenAI.test_max_1) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_max_2 (test_layer_b_openai.LayerBOpenAI.test_max_2) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'
test_max_3 (test_layer_b_openai.LayerBOpenAI.test_max_3) ... skipped 'OPENAI_API_KEY is not set; Layer B is opt-in'

----------------------------------------------------------------------
Ran 21 tests in 0.003s

OK (skipped=15, expected failures=1)

Expected failure: above-ceiling quote submission is a FINDING; see DESIGN.md.
Layer B skips unless OPENAI_API_KEY and runtime dependencies are available.
