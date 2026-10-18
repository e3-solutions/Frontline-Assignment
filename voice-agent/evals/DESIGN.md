# Evaluation design

## Scope and assumptions

This suite evaluates the highest-consequence text/tool trace decisions in the
single-prompt carrier workflow. It assumes a trace has already been transcribed
and de-identified, and that every tool result is supplied by a local fixture.
`identity_confirmed` is a deliberate evaluator annotation: a carrier lookup is
not sufficient evidence that the caller verbally confirmed that identity.

The suite does not modify or import product code. It does not call Daily,
speech services, the LLM, Supabase, Salesforce, Highway, or quote/transfer
providers. It is therefore safe in CI and without credentials.

## Measurement

Safety gates are binary: any failure rejects the trace. They cover identity and
load ordering, explicit identity confirmation, loaded-max rate protection,
agreement/bid persistence and disposition, retry thresholds, terminal-state
ordering, tool/result completeness, and internal tool-name leakage.

Quality metrics are intentionally non-blocking: expected outcome alignment and
a short holding phrase before carrier/load lookups. Golden traces must score
100% today; future teams can set a lower monitored threshold only with an
explicit product decision. Quality never cancels a safety failure.

## Corpus and success criteria

Seven golden traces cover normal agreement, confirmation after an ambiguous
price, above-max bid, three unknown MCs, three failed load references,
no-agreement, and a requested transfer. Six unsafe traces each target a
different safety gate. The pytest suite asserts all goldens pass with 100%
quality and every unsafe trace fails its named gate.

## Deliberate omissions

This is not an end-to-end voice evaluation. It cannot measure transcription
accuracy, numeric speech normalization, interruption timing, voice quality,
model nondeterminism, live provider behavior, database transactions, or real
broker dialing. Production context snapshots may inform new scenarios only
after PII and secrets are removed; their results must remain local fixtures.
