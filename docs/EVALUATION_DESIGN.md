# Frontline voice-agent evaluation design

## Goal

Give engineers regression confidence in the freight agent's most costly
behavioral decisions without changing its single-prompt architecture or
requiring production credentials.

## Chosen scope

The evaluation scenarios cover identity verification, load-reference handling,
confidential rate protection, agreement/above-max recording behavior, correct
end reasons, and transfer prerequisites. These are prioritized because a
mistake can expose internal pricing, create bad operational data, or contact a
human unnecessarily.

The default suite combines prompt/tool contracts with fixture-backed,
deterministic conversation traces. It is parallel by scenario, safe in CI, and
reports per-turn completion and timing fields. Hard rules are deterministic:
an LLM judge cannot waive a confidential-price leak, fabricated lookup,
premature transfer, missing required tool, or invalid terminal reason.

## Measurement

Each turn has required and forbidden tools/phrases plus a terminal-state
expectation where applicable. A turn passes only when all of its hard
requirements pass. Scenario completion is passing turns divided by total
turns; P0 scenarios require 100% in the offline suite.

The report captures decision, tool, first-audio, and full-turn timestamps.
Only live brain/audio modes produce performance measurements; offline timing
is deliberately labelled synthetic and validates aggregation only.

An opt-in small-model judge scores five qualities (next action, tool use,
state progression, safety, and phone quality) from 0--2. It is cost controlled
through a capped response length, bounded repetitions, selected scenarios, and
separate limited concurrency. We use its rationale for diagnosis, not for
safety gating.

## Boundaries and limitations

All default carrier, load, agreement, transfer, quote, and persistence
boundaries are mocked. It does not verify Daily PSTN connectivity, Deepgram
transcription quality, Cartesia audio, OpenAI availability, Supabase writes,
Salesforce quote creation, real transfer dial-out, Slack notification, or
recording storage. Those require approved development credentials and are
explicit release-qualification work, not evidence from this suite.

The optional audio tier uses a scripted synthetic caller (for example,
ElevenLabs TTS) in isolated development rooms. It adds recognition,
interruption, and speech-latency coverage but must block all real side effects.
It runs separately from CI with a low room-concurrency cap.

## Assumptions

The present prompt and tool schemas define intended behavior; there is no
separate product specification for tone, exact latency SLOs, or negotiation
economics. The team should calibrate latency thresholds from development-call
baselines and add scenarios from reviewed call failures.
