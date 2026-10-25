# Voice-agent evaluations

This is a credential-free behavioural evaluation harness. It evaluates prompt
contracts, tool-call sequencing, pricing confidentiality, and closing safety.
Production APIs are never called: `fake_tools.py` is an in-memory boundary and
`_pipecat_shim.py` supplies only `FunctionSchema` when Pipecat is unavailable.

Run with the standard library (from `voice-agent/`):

```bash
python3 -m evals
```

In CI environments that install pytest, the equivalent command is:

```bash
python3 -m pytest evals -v
```

Optional live sampling (requires both package and key) is `python3 -m
evals.run_live --runs 3`. It writes timestamped JSON under `evals/results/`.
Each `scenario x check` rate is reported. Safety checks must pass 100%; other
checks need 67%. Missing credentials/package produces `SKIPPED` and success.

The scripted good and intentionally bad paths prove the plumbing and checker
sensitivity, not model quality. Live results remain the model-behaviour
measurement; no live run is possible without an API key.
