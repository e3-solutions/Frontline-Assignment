# LiveKit/Telnyx Integration Review and Test Plan

## Merge status

**Request changes.** The migration has sensible boundaries for signed LiveKit
ingress, typed configuration, and an agent-assisted Room1/Room2 transfer.
It is not safe to deploy or scale until the blocking issues below are fixed and
the associated tests pass.

## Verified observations

### P0: held-call audio is retained and replayed

`voice-agent/livekit_transfer_media.py` calls
`primary.transport.input().pause_processing_frames()` during consultation.
The pinned Pipecat 0.0.95 `LiveKitInputTransport` continues to consume LiveKit
audio and enqueue `UserAudioRawFrame` values; `FrameProcessor` pauses processing
by waiting on its unbounded process queue. It does not discard input.

Consequences:

- Caller audio accumulates for the entire broker consultation (configured up to
  180 seconds).
- A failed transfer calls `restore_primary()`, resumes the queue, and can send
  stale held-call speech to STT/LLM after the caller is back with the bot.
- The retained audio produces per-call memory growth under long consultations.

Required design change: put a bounded, explicit input-drop gate immediately
before STT (or disable transport input at the provider/session layer). Do not
pause Pipecat frame processing as the hold mechanism.

### P1: no distributed call ownership or idempotency

`voice-agent/server.py` uses a process-local `seen_livekit_events` set and adds
an event only after awaiting BotRunner startup. With more than one ingress IP,
two deliveries of the same LiveKit event can be processed by different servers.
Each may start an agent in the same room. Restarts also forget prior events.

Required design change: atomically create a TTL-backed idempotency reservation
and a durable call-owner record before dispatching the bot. Key it by the
LiveKit event ID and provider call ID/room as appropriate. Store a stable worker
ID, endpoint, lease expiry, and lifecycle state. An IP is operational metadata,
not the ownership key.

### P1: one BotRunner process accepts only one call

`voice-agent/bot.py` keeps one global `_active_bot_task` and returns HTTP 409
for another `/start` request. This is valid only when an external dispatcher
assigns exactly one active call to each isolated runner. No such dispatcher or
durable assignment exists in this PR.

Required design change: implement call-keyed task ownership in a runner, or run
one ephemeral/dedicated runner per call behind an assignment service. Publish
capacity and active-call metrics.

### P1: outbound API waits for answer

`LiveKitSdkGateway.create_sip_participant()` unconditionally sets
`wait_until_answered=True`; `/outbound-call` awaits it before responding with
202. Ringing, rejection, or no answer can therefore occupy the client request
and return an error instead of promptly accepting a call job.

Required design change: make wait-for-answer an explicit operation option.
Use it for a broker consultation, but create public outbound calls
asynchronously and expose durable call status.

### P1: outbound caller identity can disagree with tenant context

`/outbound-call` accepts `from_phone` and uses it as `bot_phone`, which drives
organization selection in the bot. The SIP request always uses configured
`LIVEKIT_SIP_OUTBOUND_NUMBER`. A request can therefore run one tenant's context
while presenting a different caller ID.

Required design change: reject the mismatch, or authorize the requested caller
ID and pass the same value into the SIP request.

## Tests to add to the repository

These should be deterministic unit/integration tests using a fake LiveKit API
gateway and fake BotRunner. They do not require a live phone call.

| Test | Setup | Expected result |
| --- | --- | --- |
| Concurrent duplicate webhook | Hold first bot-start awaitable; submit two identical verified events concurrently. | One atomic reservation and one bot start; other response is duplicate/accepted, never 503. |
| Cross-instance duplicate webhook | Create two ingress app instances sharing a fake idempotency store; deliver same event to both. | Exactly one app owns and dispatches the call. |
| Reservation rollback | Make initial bot start fail, then retry same event. | Failed reservation is released; retry can dispatch once. |
| Worker ownership | Dispatch multiple unique rooms across registered workers. | Each call has one durable owner/lease; retries retain owner; capacity is respected. |
| Worker failure | Let owner lease expire before/after bot joins. | Recovery takes only a defined safe action; no blind duplicate agent join. |
| Multi-call runner | Start two unique rooms on a scalable runner/dispatcher. | Both calls run independently; neither gets 409 due to unrelated call. |
| Hold input discard | Begin hold; inject N caller audio frames; restore primary. | No held frame reaches STT/LLM; input buffer remains bounded. |
| Long hold memory bound | Inject audio for the maximum consultation interval under tracemalloc/queue instrumentation. | Memory/queue stays below a defined cap; no backlog is processed after restore. |
| Broker no answer | Fake SIP dial timeout/rejection. | Room2 and hold resources clean up; Room1 resumes without replaying caller audio. |
| Broker early media | Emit presence/media before answer, then answer. | No briefing begins before answer and subscribed broker media. |
| Move races | Simulate success, source retained, delayed destination arrival, and ambiguous provider failure. | One move submission where ambiguous; final state/audit and cleanup match outcome. |
| Outbound delayed/no answer | Fake `wait_until_answered` call that delays/fails. | Public endpoint returns quickly with a job/call ID; status later becomes answered/failed. |
| Caller-ID mismatch | Submit differing configured caller ID and `from_phone`. | Request rejected before room or SIP participant creation. |

## Staging qualification (LiveKit/Telnyx)

Run only with isolated development trunks and test phone numbers:

1. Place two concurrent inbound calls through separate load-balancer paths.
2. Repeat/replay a signed webhook and verify one agent joins the room.
3. Run a successful warm transfer; verify carrier hears only hold music while
   broker is briefed, then carrier and broker can speak after the move.
4. Run broker no-answer, broker rejection, broker disconnect, carrier
   disconnect, and delayed move scenarios.
5. Measure ingress acknowledgement latency, outbound API latency, broker-answer
   time, move-confirmation time, queue depth, memory per active call, and active
   worker capacity.
6. Verify records, transcripts, and recordings are attributed to exactly one
   provider call and tenant.

## Exit criteria

- All deterministic tests above pass in CI.
- Staging qualification has no duplicate bot join, stale-audio replay, leaked
  Room2, or orphaned SIP participant.
- Multi-instance ownership and idempotency are backed by a shared durable store.
- Alerting exists for duplicate-delivery suppression, worker lease loss, failed
  transfer cleanup, call-start latency, and per-call memory/queue limits.
