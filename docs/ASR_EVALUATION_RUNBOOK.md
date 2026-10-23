# ASR and carrier-MC metric runbook

This guide reproduces the repository's offline ASR evaluation.  It calculates
transcript Word Error Rate (WER), carrier MC Entity Error Rate (MC EER), and a
single safety-weighted quality score.  It does **not** send audio to Deepgram,
Cartesia, Highway, Supabase, or any production system.

## 1. Verify the metric implementation

From the repository root, use Python 3.11 or newer:

```bash
python3 -m unittest discover -s evaluations/tests -v
python3 -m evaluations.run_asr_eval
```

The second command runs the synthetic fixture at
`evaluations/fixtures/asr_carrier_cases.json` and prints JSON.  The included
wrong-digit case is intentional: its nonzero MC EER proves that an otherwise
good transcript score cannot conceal an incorrect carrier identifier.

## 2. Obtain and protect the licensed corpus

1. Obtain Spirelight data under the organization's approved agreement.
2. Store audio and any identifying metadata in an access-controlled location
   outside this checkout, for example `/restricted/spirelight/`.
3. Select a fixed holdout before running any benchmark. Record its corpus
   version, selection query, and creation date in your restricted experiment
   record.
4. Never commit raw audio, real carrier identifiers, provider credentials, or
   unredacted output manifests to Git.

The selected holdout should include separate slices for caller accents,
background noise, overlap/interruptions, short utterances, digit-by-digit MC
numbers, company names, load references, and prices.  If the licensed corpus
does not contain freight terminology or spoken MCs, add separately consented
test recordings; do not invent a claim that generic conversation evaluates the
freight domain.

## 3. Produce a manifest

Create a UTF-8 JSON array in the restricted location.  Each item is one caller
turn. `reference_transcript` must be the human-verified transcript; do not use
the ASR output as its reference.

```json
[
  {
    "id": "spirelight-v1-0001",
    "audio_path": "/restricted/spirelight/0001.wav",
    "reference_transcript": "Hello, I'd like to move some freight.",
    "observed_transcript": "Hello, I'd like to move some freight."
  },
  {
    "id": "spirelight-v1-0002",
    "audio_path": "/restricted/spirelight/0002.wav",
    "reference_transcript": "My MC number is 123456.",
    "observed_transcript": "My MC number is 123456.",
    "expected_mc": "123456",
    "observed_mc": "MC-123456",
    "stt_latency_ms": 420
  }
]
```

Required fields are `id`, `reference_transcript`, and `observed_transcript`.
`expected_mc` and `observed_mc` are required for every MC-bearing turn. The
current offline runner does not read `audio_path` or `stt_latency_ms`; retain
them for restricted provenance and latency analysis.

Populate `observed_transcript` by replaying the caller channel through the
approved Deepgram integration, using the same Nova-3/en-US/8 kHz settings as
the service. Populate `observed_mc` with the final MC value selected by the
agent's extraction/tool-call path—not a human correction made after the fact.

## 4. Run the evaluation

```bash
python3 -m evaluations.run_asr_eval \
  --cases /restricted/spirelight/holdout-v1.json \
  --output /restricted/spirelight/results/holdout-v1.json
```

The command performs only local JSON processing. The saved output contains an
aggregate plus per-case WER diagnostics. Keep it in restricted storage if case
IDs are sensitive.

## 5. Interpret the scores

For each case, text is lowercased and punctuation-insensitively tokenized.

```text
WER = (substitutions + deletions + insertions) / reference-word-count
MC EER = incorrect-or-missing normalized MCs / MC-bearing cases
```

MC values are normalized to digits only, so `MC-123456` and `123456` match.
They must otherwise match exactly; one wrong digit is an error.

The positive summary score is:

```text
transcript_accuracy = max(0, 1 - mean_WER)
mc_accuracy         = 1 - MC_EER
quality_score       = harmonic_mean(transcript_accuracy, mc_accuracy)
quality_error       = 1 - quality_score
```

`quality_score` ranges from 0 (bad) to 1 (best). It is deliberately not an
average: a poor MC result constrains the total even if ordinary words are
transcribed well. `quality_error` is its complement and must not be presented
as a positive score.

Do not ship from the composite alone. Review the individual gates: MC EER,
unsafe false-verification rate, mean WER, and p95 STT latency. The proposed
initial gates are documented in [the evaluation design](EVALUATION_DESIGN.md).

## 6. Assumptions and limitations

This is intentionally an **ASR-to-carrier-identifier** evaluation, not an
end-to-end certification of the voice agent.

- It assumes the human reference transcript and the expected MC label are
  correct. Sampled double annotation and adjudication are needed to establish
  that assumption for a production holdout.
- General WER is a weak proxy for the terms that matter most here. Carrier
  company names are proper nouns, while freight-domain terms may be uncommon
  vocabulary; both can be misrecognized even when ordinary conversational WER
  looks good. The holdout must therefore include named carriers and realistic
  freight terminology, and results should be sliced into MC, carrier-name,
  freight-vocabulary, and general-conversation subsets.
- MC EER checks the final MC selected by the agent, not just ASR text. It
  includes failures from ASR, LLM number interpretation, and tool-argument
  construction. It cannot by itself localize which of those stages caused an
  error; retain the raw restricted transcript and tool-call trace for diagnosis.
- Digit-only normalization deliberately treats formatting differences such as
  `MC-123456` and `123456` as equivalent. It will not catch a formatting issue
  that matters to a future downstream API, so downstream contract tests remain
  necessary.
- The harness does not call Highway/the legacy Carrier API, verify a returned
  company name, test phone-first cache precedence, or prove that a carrier is
  legally authorized. Those are separate mocked tool-contract and controlled
  integration evaluations.
- The offline runner does not replay audio, invoke Deepgram, calculate p95
  latency, test VAD/endpointing/interruptions, or measure TTS quality. Those
  require a credentialed, instrumented integration job using the same 8 kHz
  PSTN path as production.
- WER is case- and punctuation-insensitive by design. It does not measure
  semantic understanding, appropriate LLM dialog policy, confirmation wording,
  negotiation quality, safety, privacy, or caller experience.
- The harmonic composite is a dashboard summary only. It has two components
  and can conceal distributional failures unless the mandatory per-slice gates
  are reviewed alongside it. A release must not pass when MC EER or unsafe
  false-verification rate fails, regardless of the composite score.
- Spirelight is conversational data, not proof of freight-specific or actual
  PSTN performance. Audio channel, codec, demographics, and task distribution
  must be documented; synthetic 8 kHz degradation does not replace real call
  coverage.

## 7. Make a run reproducible

For each reported result, record:

- repository commit and Python version;
- corpus agreement/version and holdout selection definition;
- Deepgram model and all live options;
- exact agent prompt/model revision and MC extraction logic;
- manifest checksum, case count, slice counts, and run timestamp;
- aggregate and per-slice WER, MC EER, false-verification rate, and p50/p95
  latency.

Compare equivalent frozen holdouts only. A new holdout, changed audio
preprocessing, or a different Deepgram model is a new benchmark, not directly
comparable evidence.
