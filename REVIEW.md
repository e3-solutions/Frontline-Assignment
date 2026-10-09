# Review: LiveKit/Telnyx migration and warm transfer

## Recommendation: request changes

The migration has material provider-boundary and warm-transfer correctness failures. In particular, valid inbound SIP calls are rejected, a broker cannot be recognized in Room2, and carrier audio is still processed during hold. Two additional lifecycle races can continue a cancelled transfer and leak Room2 resources. These should be fixed and covered by dependency-surface tests before merge.

## Scope and architecture reviewed

Reviewed base `5a98a66274322954a0a6255f54650eec6e50c41d` against PR head `f93f7a5f79efdf08c18c583a6a6f7167084b93ae`.

The PR replaces Daily call ingress/transport with signed LiveKit webhooks, LiveKit rooms and SIP participants, and a Pipecat `LiveKitTransport`. For a warm transfer, Room1 retains the carrier while a separate Room2 pipeline dials and briefs a broker; the broker is then moved into Room1. `TransferOrchestrator` owns the intended terminal state and Room2 cleanup.

Verification was **static source and dependency-source inspection only**. No tests, scripts, package installation, provider calls, credentials, or live calls were used. The submission workspace contained no reviewed checkout; no reviewed branch was changed.

## Required changes

### P0 — Valid inbound SIP webhooks are rejected

**Changed location:** `voice-agent/livekit_ingress.py:178-187`.

**Triggering sequence**

1. LiveKit sends a verified `participant_joined` webhook for a SIP participant.
2. The generated protobuf represents `participant.kind` as numeric enum value `3` for SIP.
3. `_participant_is_sip()` converts that to `"3"`, which does not match its string cases.
4. Its fallback imports `livekit.protocol.models_pb2`, but the generated protocol module is `livekit.protocol.models`; the caught `ImportError` returns `False`.
5. `parse_verified_sip_event()` rejects the event at `voice-agent/livekit_ingress.py:114-115` as `NOT_SIP_PARTICIPANT`, so the bot is never started.

**Impact:** all real inbound SIP calls can fail after successful signature verification.

**Correction:** identify SIP using the installed generated `livekit.protocol.models.ParticipantInfo` enum/descriptor (or a documented numeric enum comparison), and add a test with the real generated webhook protobuf object—not a string/mock enum.

**Evidence:** the pinned application declares `livekit-api>=1,<2` at `voice-agent/requirements.txt:4`. LiveKit's generated webhook event contains a `ParticipantInfo`, the generated Python module is `livekit.protocol.models`, and the protocol defines `SIP = 3` ([webhook generated source](https://github.com/livekit/python-sdks/blob/main/livekit-protocol/livekit/protocol/webhook.py#L23-L28), [models generated source](https://github.com/livekit/python-sdks/blob/main/livekit-protocol/livekit/protocol/models.py#L0-L25), [protocol definition](https://github.com/livekit/protocol/blob/main/protobufs/livekit_models.proto)).

### P0 — Room2 rejects the expected broker because it looks up an RTC map with a SID

**Changed location:** `voice-agent/room2_pipeline_service.py:226-260`, especially `:227-245`.

**Triggering sequence**

1. Pipecat's LiveKit transport invokes participant and subscribed-track callbacks with `participant.sid`.
2. `track_human()` receives that SID as `participant_id`.
3. It calls `client.room.remote_participants.get(participant_id)` at line 233.
4. In the compatible LiveKit RTC SDK, `remote_participants` is indexed by **identity**, not SID; therefore this returns `None`.
5. Pipecat's preceding `get_participant_metadata(participant_id)` has the same SID-keyed map lookup and returns `{}` on a miss. `identity` remains `None`.
6. The expected broker identity is `broker-...`, so line 244 rejects the participant. Lines 252-255 never record presence; lines 257-260 never record subscribed media.
7. `wait_for_broker()` at `voice-agent/room2_pipeline_service.py:300-310` times out and the transfer fails.

**Impact:** the Room2 consultation cannot recognize the broker, blocking warm transfers before the handoff.

**Correction:** resolve callback SIDs by scanning `remote_participants.values()` for `.sid`, or change the Pipecat boundary to provide identity consistently. Preserve SID and identity as separate values and test with distinct values.

**Evidence:** `pipecat-ai==0.0.95` is pinned at `voice-agent/requirements.txt:1`; its livekit extra constrains `livekit~=1.0.13` and `livekit-api~=1.0.5` ([dependency metadata](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/pyproject.toml#L65-L72)). Pipecat forwards `participant.sid` ([transport source](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/transports/livekit/transport.py#L464-L492)); its metadata helper performs `.get(participant_id)` and returns `{}` on a miss ([lines 367-383](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/transports/livekit/transport.py#L367-L383)). The compatible LiveKit 1.0.13 source documents and inserts `remote_participants` by identity ([room.py:189-197](https://github.com/livekit/python-sdks/blob/28573d03856347647d46595d16d7e91d5e21ad53/livekit-rtc/livekit/rtc/room.py#L189-L197), [room.py:867-875](https://github.com/livekit/python-sdks/blob/28573d03856347647d46595d16d7e91d5e21ad53/livekit-rtc/livekit/rtc/room.py#L867-L875)).

### P0 — Hold gating does not stop carrier audio from reaching STT/LLM

**Changed locations:** `voice-agent/livekit_transfer_media.py:53-64`; called before hold startup at `voice-agent/orchestrator.py:184-185`.

**Triggering sequence**

1. `gate_primary_media(True)` calls `pause_processing_frames()`.
2. LiveKit continues converting incoming carrier audio into `UserAudioRawFrame` and calls `BaseInputTransport.push_audio_frame()`.
3. `push_audio_frame()` checks only `BaseInputTransport._paused`; `pause_processing_frames()` does not set it. The PR does not send a `StopFrame`, which is what sets `_paused`.
4. The separate audio task continues VAD and turn analysis, then calls `push_frame(frame)`.
5. `UserAudioRawFrame` is an `InputAudioRawFrame`, and `InputAudioRawFrame` is a `SystemFrame`. `pause_processing_frames()` blocks only the non-system queue, so this audio is immediately forwarded through the Room1 pipeline to STT and onward to LLM.

**Impact:** callers are not actually isolated while on hold; hold-period speech can alter the agent state or trigger work while the caller hears hold music.

**Correction:** use a transport/input mechanism that disables or discards audio at capture/ingress for the carrier during hold, and explicitly drain/drop already accepted audio. Test that hold-period `UserAudioRawFrame`s do not reach STT, turn analysis, transcript, or LLM.

**Evidence:** Pipecat 0.0.95 exposes the pause API, but it gates non-system frame processing ([frame processor](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/processors/frame_processor.py#L803-L839)). `UserAudioRawFrame` is a `SystemFrame` ([frames](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/frames/frames.py#L1166-L1222)). The input audio path and `_paused` check are in [base input](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/transports/base_input.py#L200-L245) and its VAD/push loop is [here](https://github.com/pipecat-ai/pipecat/blob/v0.0.95/src/pipecat/transports/base_input.py#L419-L444).

### P1 — A cancellation while Room2 creation awaits can resume into hold, broker dialing, and a leaked room

**Changed locations:** `voice-agent/orchestrator.py:145-165`, `:166-214`, `:295-302`, `:438-495`.

**Triggering sequence**

1. The transfer begins in `PREPARING` at line 145 (`TransferState.start()` sets that phase at `voice-agent/transfer_state.py:66-80`) and awaits provider room creation at lines 159-162.
2. While that await is outstanding, the independent carrier-disconnect path calls `_terminal_failure(... cancelled=True, restore_primary=False)` at lines 295-302.
3. `_terminal_failure()` sets state `CANCELLED`, invokes `_cleanup_room2()`, and marks the transfer complete at lines 447-479.
4. Because creation has not returned, there is no `_room2_pipeline` and no `room2_name`; `_cleanup_room2()` has nothing to stop or delete (lines 480-495).
5. If the provider creation succeeds after cancellation, the original coroutine stores the late room at lines 163-165. It never rechecks terminal state or `_transfer_in_progress`.
6. It proceeds to gate Room1/start hold (184-185), start Room2 (189-199), and dial a broker (201-214). Future `_terminal_failure()` calls return immediately because line 448 sees no transfer in progress.

**Impact:** a disconnected caller can leave an unowned Room2 and trigger unnecessary hold/media and broker-dial activity after the transfer has been cancelled.

**Correction:** make cancellation own or cancel the in-flight room-creation task; after every externally awaited operation, recheck a per-attempt generation/terminal state before persisting or advancing. If a room arrives after cancellation, delete it immediately. Ensure only the current attempt may start hold, Room2, or dialing.

**Evidence:** this is a new/reworked LiveKit path, not a claim that the Daily implementation was race-free. The base orchestrator used a different Daily sequence and did not contain this terminal-state/LiveKit-room lifecycle path ([base `execute_transfer_to_room2`](https://github.com/e3-solutions/Frontline-Assignment/blob/5a98a66274322954a0a6255f54650eec6e50c41d/voice-agent/orchestrator.py#L170-L229)).

### P1 — Post-arrival media-recovery leaks Room2 and its pipeline

**Changed locations:** `voice-agent/orchestrator.py:345-378`, `:399-427`, cleanup owner `:480-495`.

**Triggering sequence**

1. After verified broker movement, state is `HANDOFF_REQUESTED` at `voice-agent/orchestrator.py:264-286`.
2. `_complete_handoff()` calls `stop_hold(retain_observer=True)` and `detach_primary_publisher()` at lines 350-354.
3. If either raises, lines 355-358 call `_recover_after_arrived_broker()` and return before the normal-success cleanup at line 378.
4. Recovery removes the broker from Room1, restores or quarantines primary media, sets state `FAILED`, and marks the transfer complete at lines 399-427.
5. It never calls `_cleanup_room2()`, the only helper that stops the Room2 pipeline and deletes Room2 (lines 480-495).

**Impact:** a recoverable handoff-media error leaves the Room2 pipeline running and its LiveKit room allocated; this can retain audio/session resources and continue work after the transfer is terminal.

**Correction:** make recovery invoke `_cleanup_room2()` before terminal completion, including the ambiguous-handoff branch where safe. Keep retry/reporting semantics, and add tests for failures from both `stop_hold()` and `detach_primary_publisher()` that assert pipeline stop and Room2 deletion.

**Evidence:** the base did stop/clean Room2 on its ordinary Daily success path ([base lines 335-346](https://github.com/e3-solutions/Frontline-Assignment/blob/5a98a66274322954a0a6255f54650eec6e50c41d/voice-agent/orchestrator.py#L335-L346)), but it had no equivalent LiveKit post-move recovery path. This finding concerns the new PR recovery branch, not an assertion about all base failure behavior.

## Assumptions and unresolved questions

- LiveKit/Telnyx provisioning, webhook delivery, SIP caller attributes, Room2 move behavior, and real media behavior still require integration qualification after source fixes.
- `livekit-api>=1,<2` is not reproducibly pinned. Pipecat narrows its own compatible `livekit`/`livekit-api` extras to 1.0.x, but the application should lock the resolved dependency set used in deployment and test against it.
- The destination participant SID after `MoveParticipant` is not established by this review. Disconnect/observer behavior should be checked using distinct Room2 and Room1 SIDs after the blocking defects are fixed.
