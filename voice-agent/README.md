# Daily freight negotiation voice agent

The agent receives inbound Daily PSTN calls, verifies a carrier, retrieves a load, negotiates from a single prompt, records an agreement, and can transfer the caller to a broker.

## Call flow

1. Daily sends the incoming call to the webhook server at `/daily-webhook`.
2. `server.py` obtains a Daily room and sends the call metadata to the bot runner's `/start` endpoint.
3. `bot.py` joins the room; Daily connects the waiting caller when the bot is ready.
4. The pipeline uses Deepgram `nova-3` for transcription, OpenAI `gpt-4.1` for the conversation, and Cartesia for speech. Voice activity and turn detection run locally.
5. Tools verify the carrier, retrieve load data, record the agreement, end the call, or begin a broker transfer.
6. A transfer uses another Daily room to brief the broker, then connects the broker with the carrier. Call records and audio are written to the configured Supabase project.

## Source map

| File | Purpose |
| --- | --- |
| `server.py`, `server_utils.py` | Webhook handling, request models, and bot startup |
| `room_pool_service.py` | Daily room creation and reuse |
| `bot.py` | Speech pipeline and function registration |
| `voice_prompt.py`, `load_context_utils.py` | Initial greeting and load-specific negotiation prompt |
| `tool_definitions.py`, `call_helpers.py` | Tool schemas and implementations |
| `orchestrator.py`, `transfer_tool_handler.py`, `room2_pipeline_service.py` | Broker transfer and briefing |
| `../shared/` | Database, carrier, quote, and load normalization services |

The carrier conversation exposes `verify_carrier`, `get_load_context`, `record_agreement`, `end_call`, and `transfer_to_human`. The broker briefing uses `transfer_human_to_carrier` to complete the transfer.

## Install and run

Follow [Local setup](../docs/LOCAL_SETUP.md) for system packages, installation commands, `.env` configuration, and database preparation. Run both processes from this directory, with the repository's virtual environment activated in each terminal:

```bash
source ../.venv/bin/activate
python server.py
```

In another terminal:

```bash
source ../.venv/bin/activate
python bot.py
```

The server listens on port 8080 and calls `LOCAL_BOT_URL` (default `http://localhost:7860`). The bot runner listens on 7860 and returns rooms through `LOCAL_SERVER_URL` (default `http://localhost:8080`). Both load `.env` with override enabled, so edit that file to change settings; shell exports of the same variable can be overridden.

The example starts with `ROOM_POOL_SIZE=0` for local health checks. This skips room creation at server startup. Receiving a webhook still attempts to create a Daily room and needs valid credentials. Set a positive pool size after configuring the development Daily account.

For a call, expose the webhook server using a tunnel and configure the development Daily number as described in [Connect a development phone number](../docs/LOCAL_SETUP.md#connect-a-development-phone-number).

## Containers

Use `Dockerfile.server` for port 8080 and `Dockerfile.bot` for port 7860. Both require the repository root as their build context to include `shared/`. See [container commands](../docs/LOCAL_SETUP.md#container-build-contexts).

## Troubleshooting

- **Imports or audio fail:** use Python 3.11, install the full requirements and NLTK tokenizer data from [Local setup](../docs/LOCAL_SETUP.md), and check `ffmpeg` and `libsndfile1`. Run from `voice-agent/` so static assets resolve.
- **Health succeeds but calls fail:** health endpoints only check HTTP process availability. Inspect both process logs for Daily room creation, speech service connections, and database errors.
- **No greeting or load:** check the dialed number's organization mapping, seeded load/stops data, provider credentials, and the selected carrier lookup service.
- **Transfer fails:** check Daily dial-out/SIP permissions, the load's test broker routing and `SLACK_WEBHOOK_URL`. Use test numbers and a development Slack destination.
- **No recording playback:** check the `call-recordings` Storage bucket and its access settings in [Database setup](../docs/DATABASE_SETUP.md).
