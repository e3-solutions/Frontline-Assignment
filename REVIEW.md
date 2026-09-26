# PR #1 Review: LiveKit/Telnyx Migration and Warm Transfer

## Review scope

Reviewed `f93f7a5f79efdf08c18c583a6a6f7167084b93ae` against base
`5a98a66274322954a0a6255f54650eec6e50c41d`.

The PR changes 42 files (`3,722` insertions, `1,763` deletions) and replaces
Daily with LiveKit/Telnyx for inbound calls, outbound calls, Pipecat transport,
and Room1/Room2 warm transfer. It also adds provider attribution to call records
and the dashboard.

## Overall recommendation

**Request changes — do not merge yet.**

The migration is coherently structured and the transfer state machine covers a
useful set of timeouts, disconnect races, ambiguous participant moves, and
cleanup paths. However, the current implementation does not provide the media
isolation expected from a warm transfer: Pipecat queues carrier input during
hold and can replay it into the agent after a failed transfer. In addition,
webhook handling is not atomically idempotent, the supplied BotRunner accepts
only one active call, outbound tenant context can differ from the real caller
ID, and intentionally accepted withheld-number calls cannot be persisted.

At minimum, the hold behavior, ingress idempotency/call-capacity contract,
outbound identity validation, withheld-number persistence, and broker transcript
identity should be corrected before merge. The bounded outbound contract,
exceptional cleanup path, explicit room expiry, and LiveKit dependency floor
should also be addressed before production qualification.

## Actionable review comments

### P1 — Hold queues carrier speech instead of discarding it

**File:** `voice-agent/livekit_transfer_media.py:57-69`

**Intended behavior:** While the broker is briefed in Room2, carrier input must
not reach STT, conversation context, the LLM, or tool handlers. If the transfer
fails, Room1 should resume without processing anything said during hold.

**Actual behavior:** The implementation calls
`transport.input().pause_processing_frames()`. In pinned
`pipecat-ai==0.0.95`, this pauses processing of queued non-system frames; it
does not discard them. `restore_primary()` later calls
`resume_processing_frames()`, releasing that backlog into the Room1 pipeline.
On a successful handoff, input is never resumed and can remain queued until the
primary pipeline is cancelled.

The test in `voice-agent/tests/test_livekit_transfer_media.py:30-51` supplies
mock pause/resume methods and verifies only that they were called, so it cannot
detect replay or backlog growth.

**Requested change:** Replace pause/resume with a real drop, mute, or track
unsubscribe boundary. Add a behavioral test proving that audio received during
hold never reaches STT/LLM after recovery.

### P1 — Concurrent calls are rejected by the supplied BotRunner

**File:** `voice-agent/bot.py:689-704`

**Intended behavior:** Distinct inbound and outbound calls should receive
independent bot sessions, or be routed to explicitly isolated one-call runners.

**Actual behavior:** Each process stores one global `_active_bot_task` and
returns `409 Conflict` while it is occupied. Ingress converts that rejection to
a `503`; outbound can already have an answered carrier leg before encountering
the conflict. The transfer orchestrator is also global, so removing only the
guard would mix per-call transfer state.

The checked-in Docker/local setup starts one Uvicorn BotRunner and contains no
queue, scheduler, or one-runner-per-call routing mechanism.

**Requested change:** Use call/room-keyed bot and orchestrator state, or supply
and document the external one-runner-per-call routing contract required by this
process model. Add a test showing two distinct calls are either independently
accepted or deliberately routed to separate runners.

### P1 — Webhook deduplication is non-atomic and process-local

**File:** `voice-agent/server.py:123-141`

**Intended behavior:** One LiveKit event should initiate at most one bot
session, including during concurrent delivery, retry, restart, or replicated
server operation.

**Actual behavior:** The handler checks `seen_livekit_events`, awaits bot
startup, and only then inserts the event ID. Concurrent deliveries can both
pass the check. The set is also process-local, unbounded, and lost on restart.
The single-call runner often rejects the second request in the simplest
deployment, but that produces another error/retry rather than idempotent
acceptance and does not protect replicated runners.

The existing server test submits its duplicate only after the first request
has completed, so it does not exercise the race.

**Requested change:** Atomically reserve an event before awaiting startup,
transition or remove the reservation on failure, and use a bounded shared store
if multiple workers/restarts are supported. Add concurrent same-event and
retry-after-response-loss tests.

### P1 — Outbound caller ID and tenant context can diverge

**Files:** `voice-agent/server.py:157-179`,
`voice-agent/livekit_telephony_service.py:108-118`, `voice-agent/bot.py:246-253`

**Intended behavior:** The number used to select organization context should be
the same validated caller ID presented on the PSTN call.

**Actual behavior:** Request-controlled `from_phone` becomes `bot_phone` and
selects the organization, while LiveKit always sends configured
`LIVEKIT_SIP_OUTBOUND_NUMBER` as `sip_number`. A caller holding the shared API
key can therefore request tenant context for a number that is not the actual
outbound caller ID.

**Requested change:** Derive `bot_phone` from the configured outbound number,
or validate/authorize `from_phone`, require it to match, and use that same value
for both attribution and SIP dialing.

### P1 — Withheld-number calls are accepted but cannot be persisted

**Files:** `voice-agent/livekit_ingress.py:166-188`,
`voice-agent/tests/test_livekit_ingress.py:226-232`,
`web/supabase/migrations/20252132000000_create_calls_table.sql:6`

**Intended behavior:** The explicit `test_withheld_caller_number_is_allowed`
establishes that a missing caller number is supported. Such callers should be
able to fall back to MC-based verification and still receive normal call,
recording, transcript, and transfer-audit persistence.

**Actual behavior:** Ingress accepts a missing `sip.phoneNumber` as
`caller_number=None`, but `calls.caller_number` is `NOT NULL`. Call creation
fails in a background task and the conversation continues without a call ID,
so final transcript, recording linkage, agreement linkage, audit, and dashboard
visibility are lost.

**Requested change:** Add a migration making `caller_number` nullable and make
the dashboard render a safe value such as `Withheld`.

### P1 — Combined transcript loses broker identity

**Files:** `voice-agent/room2_pipeline_service.py:203-217`,
`voice-agent/bot.py:629-640`

**Intended behavior:** The final transcript should distinguish the carrier from
the broker during the private consultation.

**Actual behavior:** Room2 initially stores the correct `broker` role. Final
transcript construction converts every non-agent consultation message to
`caller`, making broker speech indistinguishable from carrier speech. The
transfer audit retains `broker`, so the two persisted representations disagree.

**Requested change:** Preserve `broker` in the combined transcript, or add
explicit participant and room/source fields if downstream consumers require a
smaller role vocabulary.

### P2 — Synchronous outbound dialing is not explicitly bounded

**Files:** `voice-agent/server.py:147-187`,
`voice-agent/livekit_telephony_service.py:97-123`

**Intended behavior:** A synchronous outbound request should confirm carrier
answer and bot startup within a documented, application-controlled deadline.

**Actual behavior:** The endpoint awaits LiveKit with
`wait_until_answered=True`, but applies no application-level timeout. Its HTTP
latency is therefore controlled by provider ringing behavior and surrounding
proxy/client timeouts. It returns `202` only after answer and bot startup have
already been attempted.

Synchronous handling itself is reasonable: it avoids client polling and is
consistent with the broker transfer path. Other potentially long operations in
this PR, including broker answer, broker media readiness, consultation, and
phone verification, use explicit deadlines.

**Requested change:** Keep the synchronous model, wrap dialing in a configurable
timeout, document that success means `answered and bot started`, and use a
status consistent with that completed contract. Test delayed answer, no answer,
rejection, timeout, and BotRunner rejection after answer.

### P2 — Non-cancellation exceptions can bypass application finalization

**File:** `voice-agent/bot.py:602-658`

**Intended behavior:** Recording flush, HTTP-session closure, transfer cleanup,
and final call persistence should run for normal disconnects and unexpected
pipeline faults.

**Actual behavior:** Normal participant disconnect cancellation does return
through Pipecat cleanup and reaches the code after `runner.run()`. However,
non-cancellation runner failures and errors while waiting for transfer
completion can bypass session closure and final transcript/result persistence
because this application cleanup is not protected by `finally`.
`_bot_finished()` only logs the exception and releases the runner slot.

**Requested change:** Put per-call resources and guarded error finalization in
`try/finally`, recording an error outcome when the call row exists.

### P2 — Room expiry relies on implicit provider defaults

**File:** `voice-agent/livekit_telephony_service.py:81-85`

**Intended behavior:** Explicit participant/room cleanup should be backed by a
known provider expiry policy if cleanup calls fail.

**Actual behavior:** Application-created rooms set only `name`. LiveKit thus
uses its defaults: 300 seconds before the first join and 20 seconds after the
last participant leaves. This helps only when the room is genuinely empty; it
does not clean a room containing a lingering SIP participant, bot, or observer.

**Requested change:** Set explicit purpose-appropriate empty/departure timeouts
for Room1 and Room2. Keep explicit participant removal and room deletion;
timeouts are a last-resort safety net, not a replacement for cleanup.

### P2 — The dependency floor does not guarantee `display_name`

**Files:** `voice-agent/requirements.txt:2-5`,
`voice-agent/livekit_telephony_service.py:109-118`

**Intended behavior:** Every permitted SDK resolution should support the
request fields used by the application, and release builds should use a tested
combination.

**Actual behavior:** `CreateSIPParticipantRequest.display_name` is absent from
`livekit-protocol` 1.0.4 through 1.0.7 and present starting in 1.0.8. The
transitive dependency floor can therefore resolve an incompatible protocol
version, and there is no Python lock/compiled constraints file.

**Requested change:** Require `livekit-protocol>=1.0.8,<1.1`, preferably through
an exact compiled constraints set covering `livekit`, `livekit-api`, and
`livekit-protocol`. Add a test that constructs the real SDK request rather than
stopping at the fake gateway.

This recommendation is based on primary SDK source and package metadata. The
real dependency-backed project suite was not available in this workspace, so
the proposed floor still needs CI verification against the resolved packages.

## Evidence and verification

### Repository inspection

- Verified that the merge base of the pinned revisions is
  `5a98a66274322954a0a6255f54650eec6e50c41d`.
- `git diff --shortstat 5a98a66..f93f7a5` reported 42 files changed, 3,722
  insertions, and 1,763 deletions.
- Traced inbound webhook handling through `livekit_ingress.py` → `server.py` →
  `server_utils.py` → the BotRunner in `bot.py`.
- Traced outbound handling through `server.py` →
  `LiveKitTelephonyService.create_room/dial_phone()` → the BotRunner.
- Traced warm transfer through `transfer_tool_handler.py` → `orchestrator.py` →
  `livekit_transfer_media.py` / `room2_pipeline_service.py` → verified
  participant move → cleanup/final persistence.
- Compared transcript and call-row creation behavior against the base revision.
  Room1 text-based transcript deduplication and unawaited background call-row
  creation predate this PR and are not filed as PR defects.

### Static checks

- `git diff --check` passed.
- `python3 -m compileall -q voice-agent shared scripts` passed.
- The workspace did not contain installed voice dependencies or `pytest`, so
  the Python test suite could not be rerun here.
- Web dependencies were not installed, and the project documents a private UI
  package, so TypeScript/build checks could not be rerun here.
- No live calls or production credentials were used.

### Primary dependency/provider evidence

- `voice-agent/requirements.txt` pins `pipecat-ai==0.0.95`.
- Pipecat 0.0.95 source defines `pause_processing_frames()` and
  `resume_processing_frames()` on `FrameProcessor`; the process queue waits
  while paused and later continues with the same frame.
- LiveKit's Room service documentation specifies default `empty_timeout=300`
  seconds and `departure_timeout=20` seconds when omitted.
- Inspected LiveKit protocol definitions show `display_name` absent in
  `livekit-protocol` 1.0.4–1.0.7 and present in 1.0.8.
- The application has no Telnyx SDK dependency; Telnyx is reached through
  LiveKit SIP trunks.

Primary references:

- <https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/processors/frame_processor.py>
- <https://docs.livekit.io/reference/other/roomservice-api/>
- <https://raw.githubusercontent.com/livekit/python-sdks/protocol-v1.0.4/livekit-protocol/livekit/protocol/sip.pyi>
- <https://raw.githubusercontent.com/livekit/python-sdks/protocol-v1.0.8/livekit-protocol/livekit/protocol/sip.pyi>

## Inherited behavior noted but not filed against this PR

- Room1 transcript callbacks already deduplicate globally by `role:content`.
  Room2 follows that convention; this review assumes the behavior is
  intentional.
- Call-row creation was already launched as an unawaited background task on the
  base branch, allowing a sufficiently short call to reach finalization before
  `context.call_id` exists.
- End-of-call-only transcript persistence and ignored `finish_call()` failure
  also predate the PR.

These behaviors increase operational risk for the newly added consultation
transcript and recording, but they are not attributed to this change.

## Assumptions

- Withheld caller numbers are intentionally supported because the PR adds an
  explicit test accepting a missing `sip.phoneNumber`.
- The desired public outbound contract is synchronous: a successful response
  means the carrier answered and the bot started.
- Text-based transcript deduplication inherited from Room1 is intentional.
- The configured outbound number is the tenant phone identity that should
  select organization context.
- LiveKit applies its documented default room expiry when the application omits
  room timeout fields.
- Telnyx remains provider-side behind LiveKit SIP; no direct Telnyx SDK is
  expected in this service.
- Real LiveKit/Telnyx, speech-provider, Supabase, and recording behavior remains
  unverified without provisioned development services.

## Unresolved engineering questions affecting merge readiness

1. What component routes each call to an isolated BotRunner process in the
   intended deployment? No such scheduler or capacity-routing layer is present
   in this repository.
2. Will webhook ingress or BotRunner use multiple workers/replicas? If so, the
   current process-local event set and global runner state cannot provide the
   required idempotency/isolation.
3. Does the deployed LiveKit version guarantee that a participant SID remains
   stable across `MoveParticipant`? The disconnect path retains the Room2 SID;
   if SID changes, it should reconcile/store the destination participant or
   match by identity.
4. Which exact `livekit`, `livekit-api`, and `livekit-protocol` versions are in
   the release image, and can CI exercise the real request objects against that
   exact set?
5. Is failed room deletion monitored or reconciled outside this process when a
   participant remains connected and LiveKit's empty-room expiry cannot apply?

