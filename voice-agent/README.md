# LiveKit/Telnyx freight negotiation voice agent

The agent receives inbound or initiates outbound SIP calls through LiveKit and Telnyx, verifies a carrier, retrieves a load, negotiates from a single prompt, records an agreement, and can warm-transfer the caller to a broker.

## Call flow

### Inbound

1. Telnyx sends the development PSTN call through the configured LiveKit inbound SIP trunk.
2. A LiveKit dispatch rule places the caller in Room1. LiveKit sends the signed SIP participant event to `POST /livekit-webhook`.
3. `server.py` verifies the signature, event type, SIP participant attributes, inbound trunk, and dispatch rule, then sends a transport-neutral request to the bot runner's `/start` endpoint.
4. `bot.py` joins Room1 through LiveKit. The pipeline uses Deepgram `nova-3` for transcription, OpenAI `gpt-4.1` for the conversation, and Cartesia for speech. Voice activity and turn detection run locally.

### Outbound

1. An authorized caller sends E.164 `to_phone` and `from_phone` values to `POST /outbound-call`, with `X-API-Key` matching `OUTBOUND_CALL_API_KEY`.
2. The server creates Room1, asks LiveKit to dial the carrier through the configured Telnyx outbound trunk, and starts the bot runner in the room.
3. The same prompt and tool path handles the negotiation after the SIP participant answers.

The endpoint is disabled when `OUTBOUND_CALL_API_KEY` is empty and rejects a missing or incorrect `X-API-Key`. Keep it private for this exercise or place it behind an authenticated internal gateway before exposing outbound dialing.

## Prompt and tools

The negotiation remains a single-prompt agent. The system prompt and load-specific context guide one LLM context; the telephony migration does not introduce a graph or flow-based agent architecture.

The carrier conversation exposes `verify_carrier`, `get_load_context`, `record_agreement`, `end_call`, and `transfer_to_human`. The broker briefing uses `transfer_human_to_carrier` to complete the transfer.

During a warm transfer, the carrier remains in Room1 while the bot creates Room2, dials the broker through LiveKit SIP, and briefs the broker with the captured negotiation context. LiveKit then moves the broker participant from Room2 into Room1. The bot stops the Room2 briefing pipeline and deletes the temporary room.

## Source map

| File | Purpose |
| --- | --- |
| `server.py`, `server_utils.py` | Inbound webhook, outbound request, bot-runner routing, and health endpoints |
| `livekit_ingress.py` | Signed LiveKit webhook verification and SIP event validation |
| `telephony_config.py` | Typed LiveKit/SIP configuration and readiness validation |
| `livekit_telephony_service.py` | LiveKit room, SIP participant, and participant-move SDK boundary |
| `bot.py` | Speech pipeline and function registration |
| `voice_prompt.py`, `load_context_utils.py` | Initial greeting and load-specific negotiation prompt |
| `tool_definitions.py`, `call_helpers.py` | Tool schemas and implementations |
| `orchestrator.py`, `transfer_tool_handler.py`, `room2_pipeline_service.py` | Room1/Room2 broker transfer and briefing |
| `../shared/` | Database, carrier, quote, and load-normalization services |

## Install and run

Follow [Local setup](../docs/LOCAL_SETUP.md) for system packages, installation, `.env` configuration, LiveKit/Telnyx provisioning, and database preparation. Run both processes from this directory, with the repository virtual environment activated in each terminal:

```bash
source ../.venv/bin/activate
python server.py
```

In another terminal:

```bash
source ../.venv/bin/activate
python bot.py
```

The server listens on port 8080 and calls `LOCAL_BOT_URL` (default `http://localhost:7860`). The bot runner listens on port 7860. Both load `.env` with override enabled, so edit that file to change settings; shell exports of the same variable can be overridden.

`POST /livekit-webhook` is the signed inbound event path. `POST /outbound-call` is the programmatic outbound path. The `/health` endpoints report local process availability only.

## Containers

Use `Dockerfile.server` for port 8080 and `Dockerfile.bot` for port 7860. Both require the repository root as their build context to include `shared/`. See [container commands](../docs/LOCAL_SETUP.md#container-build-contexts).

## Troubleshooting

- **Configuration reports not ready:** check every LiveKit URL, API credential, SIP trunk ID, dispatch-rule ID, outbound number, and E.164 value. The inbound IDs must match the attributes in the signed event.
- **Webhook is rejected:** confirm LiveKit targets `/livekit-webhook`, preserves its authorization header and body, emits SIP `participant_joined` events, and uses the configured inbound trunk and dispatch rule.
- **Imports or audio fail:** use Python 3.11, install the full requirements and NLTK tokenizer data from [Local setup](../docs/LOCAL_SETUP.md), and check `ffmpeg` and `libsndfile1`. Run from `voice-agent/` so static assets resolve.
- **Health succeeds but calls fail:** inspect both process logs and provider consoles. Health does not check LiveKit, Telnyx, speech services, Supabase, or SIP routing.
- **No greeting or load:** check the called-number organization mapping, seeded load/stops data, provider credentials, and carrier-lookup service.
- **Outbound call fails:** check the outbound trunk, its Telnyx credentials and allowed destinations, caller ID ownership, E.164 formatting, and the broker/carrier test number.
- **Transfer fails:** check Room1/Room2 participant state, the load's test broker routing, outbound trunk, and `SLACK_WEBHOOK_URL`. Use test numbers and a development Slack destination.
- **No recording playback:** check the `call-recordings` Storage bucket and its access settings in [Database setup](../docs/DATABASE_SETUP.md).

Automated tests exercise deterministic logic with fakes and mocks. They do not claim a successful real call, provider connection, SIP transfer, database write, recording, or quote submission.
