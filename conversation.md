# Conversation — PR #1 review

This is an **edited reconstruction of my questions to Codex and the code-backed answers**, not a verbatim chat transcript. It is sized for a one-hour review. The comparison is exactly base `5a98a66274322954a0a6255f54650eec6e50c41d` and head `f93f7a5f79efdf08c18c583a6a6f7167084b93ae`. No source branch was changed; no production credentials or live provider calls were used.

## The questions I worked through

**Me:** Before looking for bugs, what does the existing call path do, and what does this PR replace?

**Codex:** Daily's webhook checks out a precreated SIP room, starts a Pipecat bot, and identifies the carrier after dial-in connection plus participant join (`base: server.py:100–163`, `bot.py:522–606`). The PR accepts a signed LiveKit SIP participant event, checks trunk/rule/phone attributes, issues a room token, and starts BotRunner (`head: livekit_ingress.py:64–188`, `server.py:108–145`). LiveKit rooms and SIP control move behind `livekit_telephony_service.py`; Telnyx is the carrier behind the configured SIP trunks, with no direct Telnyx API call in this flow.

**Me:** How does a warm transfer keep the carrier on hold, reach the broker, and decide that handoff is complete?

**Codex:** The LLM's `transfer_to_human` tool asks the bot to announce a hold, then `speech_sync.py` schedules the transfer after speech. Daily cancels Room1's bot, starts a separate hold bot, dials into Room2, and uses `sipCallTransfer` to route the broker SIP session to Room1 (`base: orchestrator.py:147–253,337–383`). The PR keeps Room1's pipeline gated, publishes hold audio through a separate LiveKit participant, creates Room2, dials with `wait_until_answered=True`, and waits for the expected broker media before briefing. It moves the broker's participant identity to Room1 and marks success only after destination presence is checked (`head: orchestrator.py:130–307,369–405`; `livekit_telephony_service.py:283–351`).

**Me:** What happens on disconnect, and where do the recordings and audit end up?

**Codex:** The PR's orchestrator owns hold media, Room2 teardown, failed-handoff recovery, and post-handoff cleanup (`orchestrator.py:309–540`). The bot owns Room1 recording, transcript capture, and final `calls` update (`bot.py:423–463,577–658`). Room2 consultation transcript and recording URL are folded into the transfer audit (`room2_pipeline_service.py:203–230,343–367`; `transfer_state.py:104–118`). The migration adds `telephony_provider` and `provider_call_id`, defaulting historical rows to Daily (`web/supabase/migrations/20260907000000_add_livekit_call_attribution.sql`).

**Me:** Which production rules should I keep in mind while deciding whether this can merge?

**Codex:** Eight essentials: one bot and call record per call; trusted caller/trunk/tenant attribution; broker routing from the confirmed load; carrier isolation during hold; briefing only after the intended broker answers with usable media; handoff only after verified Room1 arrival; one terminal outcome across disconnect and timeout races; and complete cleanup with matching recordings, transcripts, and audit state.

**Me:** I have about one hour. What should the separate deliverable contain?

**Codex:** A short overall review, a clear merge recommendation, comments on changed lines, evidence, and the assumptions that affect the decision. The separate PR is stacked on PR #1's head and changes only this review file.

**Me:** There might be more. Does a second sweep change the recommendation?

**Codex:** Yes. It confirmed two more high-impact code paths: a Room2-creation/caller-departure race, and outbound tenant attribution based on a requested number that the SIP dial does not use. The recommendation remains **request changes before merging PR #1**. The first three findings below are the merge blockers; the two P2 findings need a bounded fix or an explicit rollout constraint.

## Actionable review comments

1. **[P1] Broker identity lookup prevents consultation.** Anchor `voice-agent/room2_pipeline_service.py:254`. Pipecat 0.0.95 passes a participant **SID** to the connected and audio callbacks, but LiveKit RTC stores `remote_participants` by **identity**. Both this fallback and Pipecat's metadata helper look up the map by SID, so the generated `broker-...` identity is not recovered. `track_human` rejects the participant; broker readiness never completes (`room2_pipeline_service.py:246–285,330–341`). **Fix:** find the remote participant by `.sid`, compare its `.identity`, and test with an identity-keyed fake map and both answer/media event orders. Check the analogous Room1 fallback at `bot.py:484–495`.

2. **[P1] Caller departure can lose the Room2-creation race.** Anchor `voice-agent/orchestrator.py:171–177`. The attempt is active when `create_room()` is awaited. A carrier disconnect can concurrently mark the attempt `CANCELLED` and finish cleanup before `room2_name` exists (`orchestrator.py:316–324,471–513`). When room creation returns, the original task stores the new room and continues without checking the terminal state; later failure cleanup returns immediately because the attempt is already inactive. This can leave Room2 behind and may continue toward broker dialing after the caller left. **Fix:** recheck/cancel after each provider await, reconcile any newly created room or broker leg, and test carrier departure while `create_room` and dial are pending.

3. **[P1] Outbound call attribution can use the wrong tenant.** Anchor `voice-agent/server.py:175`. `/outbound-call` accepts `from_phone` and passes it as `bot_phone` for organization lookup and call creation (`bot.py:250–253,539–557`; `db_operations.py:112–118`), but the actual SIP request always uses `config.livekit_outbound_number` (`livekit_telephony_service.py:109–117`). Two different valid numbers can place a call from one organization and record it under another. **Fix:** reject a mismatch, or select and authorize a per-request outbound number and use that same number for both SIP caller ID and database attribution. Test with two distinct organization numbers.

4. **[P2] Webhook admission is not atomic.** Anchor `voice-agent/server.py:123–141`. The event ID is checked before `await start_agent` and added afterward, so concurrent deliveries can both pass; the set is local to one process. **Fix:** atomically reserve a stable call/participant key before startup, define retry behavior during startup/failure, use shared state if ingress is replicated, and test concurrent delivery.

5. **[P2] Notification latency sits outside the broker deadline.** Anchor `voice-agent/orchestrator.py:215`. The caller is already on hold when `_notify_best_effort()` is awaited, and the broker deadline begins only afterward. `transfer_notifier.py:55–56` uses an aiohttp session without a short explicit timeout; a stalled Slack endpoint can delay dialing for the client's default timeout (300 seconds in the inspected aiohttp 3.11.18). **Fix:** time-box or detach the notification so broker dialing and hold duration obey the transfer deadline; test a notifier that never returns.

## Evidence and remaining questions

I compared the exact Git objects with `git diff 5a98a66274322954a0a6255f54650eec6e50c41d f93f7a5f79efdf08c18c583a6a6f7167084b93ae` and traced the cited source paths. For finding 1, I downloaded package source only: Pipecat 0.0.95's `pipecat/transports/livekit/transport.py:508–538` passes `.sid` to the callbacks, while LiveKit RTC 1.0.13's `livekit/rtc/room.py:934` stores participants under `.identity`. The current Room2 test fakes a SID-keyed map (`voice-agent/tests/test_room2_pipeline_service.py:11–16`), so it misses this mismatch. No runtime suite was run because this environment lacks the pinned Pipecat/LiveKit packages; no live call was made.

Open deployment questions: Is there one BotRunner per call? The checked-in runner admits one active call per process (`bot.py:689–704`). What is the deployed SDK/protocol version, and how are LiveKit dispatch and room expiration configured? LiveKit's [SIP API documentation](https://docs.livekit.io/reference/telephony/sip-api/) says `wait_until_answered=True` includes voicemail; what human-answer gate should precede a broker-only briefing? Who deletes Room1 after a normal call without transfer? These affect rollout, but the review does not present them as proven defects.
