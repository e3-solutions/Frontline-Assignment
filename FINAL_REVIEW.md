# PR Review — Request Changes

## Recommendation

Do not merge head `f93f7a5f79efdf08c18c583a6a6f7167084b93ae` into base `5a98a66274322954a0a6255f54650eec6e50c41d` yet.

The migration is coherent in scope, preserves the single-prompt architecture, verifies inbound webhook signatures, and includes careful participant-move reconciliation. However, core call correctness, tenant attribution, and webhook reliability defects remain.

## Material findings

### P1 — Room1 hold does not gate caller audio

**Files:** `voice-agent/livekit_transfer_media.py:53-64`, `voice-agent/orchestrator.py:170-186`

The code invokes `transport.input().pause_processing_frames()`. In pinned Pipecat 0.0.95, LiveKit input audio travels through `BaseInputTransport`'s audio queue and is pushed directly downstream, bypassing the processing queue controlled by this method. During hold, caller speech can therefore continue into STT, LLM context, and tools while TTS is suppressed.

Replace this with a gate that demonstrably drops/unsubscribes Room1 audio and add a real dependency-level audio-flow test.

### P1 — Outbound recipients answer before BotRunner starts

**Files:** `voice-agent/server.py:148-169`, `voice-agent/livekit_telephony_service.py:90-116`

The SIP request uses `wait_until_answered=True`; the server awaits it and only then calls BotRunner. An answered recipient gets dead air during runner and pipeline initialization. Runner rejection after answer deletes the room and hangs up. Start and verify the bot before dialing, gate the greeting on participant arrival, and test delayed answer, rejection, no-answer, voicemail, and runner failure.

### P1 — Request-controlled `from_phone` selects tenant context

**Files:** `voice-agent/server.py:134-165`, `voice-agent/livekit_telephony_service.py:100-109`, `voice-agent/db_operations.py:34-50`

`from_phone` becomes `AgentRequest.bot_phone` and drives organization lookup, while the actual SIP caller ID always uses configured `LIVEKIT_SIP_OUTBOUND_NUMBER`. The global API key does not authorize the requested tenant identity. Remove the caller-controlled selector or bind authenticated principals to allowed tenant numbers, use the same authorized identity for SIP and attribution, and add cross-tenant negative tests.

### P1/P2 — Webhook idempotency is non-atomic and non-durable

**File:** `voice-agent/server.py:48,112-129`

The handler checks an in-memory set, awaits BotRunner startup, then inserts the event ID. Concurrent deliveries can both pass. The set is process-local, lost on restart, unshared across replicas, and unbounded. Atomically claim events in a shared bounded store before awaited work, define retryable states, add database uniqueness where appropriate, and test concurrent/multi-worker/restart delivery.

### P2 — Webhook acknowledgement can stall behind BotRunner

**Files:** `voice-agent/server.py:38-43,98-132`, `voice-agent/server_utils.py:27-52`

Ingress waits for an internal HTTP request made with a default aiohttp session; the documented default total timeout is 300 seconds. A stalled runner delays provider acknowledgement and amplifies retries. Durably claim and acknowledge first, dispatch asynchronously, and apply short explicit internal timeouts.

## Assumptions and unresolved questions

- What allocates one BotRunner per call? The runner rejects overlapping calls with 409 and the repository shows one `LOCAL_BOT_URL`.
- Can untrusted clients reach port 7860? `/start` is unauthenticated, though this is inherited and public reachability is not proven.
- Which migration directory is authoritative, and how is schema-before-code ordering enforced?
- Must the carrier-to-broker conversation after handoff be recorded/transcribed?
- Does webhook 202 mean durably accepted or already dispatched?

## Evidence and limitations

Evidence included pinned source traces, changed tests, exact Pipecat 0.0.95 source, LiveKit outbound SIP documentation, aiohttp timeout documentation, and independent security, correctness, and judge reviews.

Corrections from adjudication: Pipecat pause/resume methods exist; the verified defect is failure to gate the transport audio path, not missing methods or stale replay. The BotRunner endpoint is a deployment-dependent inherited risk. Unbounded dashboard queries are inherited debt, not a blocker for this PR.

No live calls or production credentials were used. Provider-boundary tests are mocked and do not validate actual SIP timing, audio gating, transfer recording, or cleanup.
