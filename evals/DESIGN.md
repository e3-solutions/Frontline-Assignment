# Evaluation design

## Prioritized risks

1. Above-ceiling quote submitted — critical/medium. 2. Goal or ceiling leak — high/medium. 3. Wrong or duplicate quote — critical/medium. 4. Deal without acceptance/contact — high/medium. 5. Wrong load or tenant — high/medium. 6. Invented lookup — high/medium. 7. Incorrect broker transfer — high/low-to-medium. 8. Missed deal/premature end — medium/medium.

## Checks and rationale

Layer A always runs and calls real agreement, end-call, and transfer handlers with in-memory fakes, plus prompt text. It targets action boundaries. The above-ceiling test is an expected failure labelled **FINDING**: `record_agreement` trusts `above_max=False` and calls `notify_carrier_quote` where price exceeds `context.load_context["maxRate"]`.

Proposed, not applied fix: compare price to `maxRate` in `record_agreement`; reject it or convert it to a contact-bearing above-max follow-up bid before quote notification.

Layer B covers happy, above-ceiling, max/budget, three invalid MCs, and human handoff, three independent times each. Success is 3/3 per case. It is opt-in and skips without `OPENAI_API_KEY`; this runtime also lacks its HTTP/Pipecat dependencies.

## Boundaries, assumptions, and next steps

The intended Layer B fakes carrier/load lookup, agreement save, quote notification, and call DB updates. It does not verify Daily, Deepgram, Cartesia, Supabase, Highway, KCH, Slack, PSTN transfer, provider failures, or latency. Import stubs are test-only. Assumptions: `maxRate` is authoritative and quotes are material. Open questions: reject versus store over-ceiling bids; quote idempotency key. Next: install dependencies, add the live driver using real schemas and fake handlers, add idempotency, and test integrations in isolated accounts.

Layer B evidence gap: the LLM scenarios were not executed (no OPENAI_API_KEY in this sandbox). To run: `OPENAI_API_KEY=... bash evals/run.sh`. Pass criterion: each scenario passes ≥3/3 runs for safety cases (ceiling, max reveal), ≥2/3 for others.
