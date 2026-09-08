# Local development

## Install the voice service

Use Python 3.11 and a virtual environment. On Debian/Ubuntu, install the audio dependencies before installing Python packages:

```bash
sudo apt-get update
sudo apt-get install -y build-essential libsndfile1 ffmpeg
```

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
cd voice-agent
python -m pip install -r requirements.txt
python -m pip check
python -m nltk.downloader punkt_tab
cp .env.example .env
```

`requirements.txt` installs `../shared` as an editable package. Keep both directories together. The NLTK download installs Pipecat sentence-tokenizer data in the standard user data location and requires internet access during setup. If you use a custom location, export `NLTK_DATA` before running Python; setting it only in `.env` is too late for imports that initialize NLTK. The default pipeline uses local ONNX-based Silero voice activity detection and Smart Turn v3. Their dependencies come from the Pipecat extras in the requirements; the default Cartesia/ONNX path does not require a separate PyTorch installation. Importing the application and starting an actual pipeline are separate checks.

## Configure development services

Fill in `voice-agent/.env` using isolated resources supplied or approved by the repository maintainer:

| Integration | Required configuration |
| --- | --- |
| LiveKit | `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, the inbound and outbound SIP trunk IDs, inbound dispatch-rule ID, outbound caller ID, and a development webhook |
| Telnyx | A development number and SIP connection linked to the configured LiveKit trunks; Telnyx credentials remain in the provider setup rather than this application `.env` |
| Speech and LLM | `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `CARTESIA_API_KEY`; the runtime uses `nova-3`, `gpt-4.1`, and the Cartesia voice configured in `bot.py` |
| Supabase | `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for the isolated project, schema/data setup, and recording storage |
| Carrier verification | An authorized carrier test service; configure the Highway backend and its base URL/key for isolated MC lookups |
| Quote submission | Matching `KCH_QUOTE_CLIENT_ID`, `KCH_QUOTE_CLIENT_SECRET`, and `KCH_QUOTE_SCOPE` with `KCH_QUOTE_USE_SANDBOX=true` |
| Broker transfer | A test broker phone in the load's routing data and `SLACK_WEBHOOK_URL` for a development channel |

Use [Database setup](DATABASE_SETUP.md) before running a data-backed call. The Telnyx number routed into LiveKit must map to the correct organization, and that organization needs a representative load, stops, and transfer routing. The dashboard uses the same database project. Keep service-role credentials server-side.

The historical `carrier_api` backend uses an external production endpoint. `CARRIER_MC_BACKEND=highway` selects the existing configurable Highway MC path; `HIGHWAY_API_BASE_URL` must point to an authorized development endpoint. USDOT lookup still uses the historical carrier endpoint. Quote sandbox selection affects only quote submission; it is not a global offline mode. Exercise each provider path only after its test access is established.

## Run the two processes

Activate the virtual environment in each terminal and run from `voice-agent/`, so `.env` and static audio paths resolve. Both applications load `.env` with override enabled; values in the file take precedence over existing shell variables.

Webhook server (port 8080):

```bash
source ../.venv/bin/activate
python server.py
```

Bot runner (port 7860), in another terminal:

```bash
source ../.venv/bin/activate
python bot.py
```

Check process health from a third terminal:

```bash
curl --fail http://localhost:8080/health
curl --fail http://localhost:7860/health
```

`LOCAL_BOT_URL` tells the webhook server how to reach the bot runner. Each process also accepts `PORT`; leave it unset in the shared `.env` to use the distinct defaults, or set it separately for each process.

Health responses establish only that the HTTP processes started. They do not validate LiveKit credentials or SIP resources, reach Telnyx, join a room, start the speech pipeline, access Supabase, or execute a tool.

## Connect LiveKit and Telnyx

Use development resources you are authorized to configure. Exact provider-console labels may vary, but the application contract is:

1. Provision a development Telnyx number and SIP connection. Restrict credentials and routing to the development environment.
2. In LiveKit, create an inbound SIP trunk for that Telnyx connection and number. Record its `ST_...` identifier as `LIVEKIT_SIP_INBOUND_TRUNK_ID`.
3. Create an inbound dispatch rule for that trunk which places each caller in a LiveKit room. Record its `SDR_...` identifier as `LIVEKIT_SIP_DISPATCH_RULE_ID`. Use `LIVEKIT_ROOM_PREFIX` for rooms the application creates.
4. Create a LiveKit outbound SIP trunk through Telnyx. Set `LIVEKIT_SIP_OUTBOUND_TRUNK_ID` to its `ST_...` identifier and set `LIVEKIT_SIP_OUTBOUND_NUMBER` to an E.164 number owned by that trunk. The application uses it as caller ID for carrier and broker legs.
5. Expose the webhook server through an HTTPS development tunnel:

   ```bash
   ngrok http 8080
   ```

6. Configure a LiveKit project webhook at `https://<your-tunnel-host>/livekit-webhook` for participant events. LiveKit signs the exact request body; the endpoint rejects missing or invalid authorization, non-SIP participants, and SIP events from a different trunk or dispatch rule.
7. Route the Telnyx number to the LiveKit inbound trunk and dispatch rule. Ensure the same E.164 called number is registered against the seeded organization in the isolated database.

The server accepts two call-entry paths:

- `POST /livekit-webhook` handles verified inbound LiveKit SIP participant events and starts the bot runner for the dispatched room.
- `POST /outbound-call` creates a LiveKit room, dials a carrier through the outbound trunk, and starts the bot runner. Supply E.164 values:

  ```bash
  curl --fail -X POST http://localhost:8080/outbound-call \
    -H 'Content-Type: application/json' \
    -H "X-API-Key: ${OUTBOUND_CALL_API_KEY}" \
    -d '{"to_phone":"+12025550102","from_phone":"+12025550100"}'
  ```

Use only development numbers you control. The endpoint requires `X-API-Key` to match `OUTBOUND_CALL_API_KEY` and is disabled when that environment variable is empty. Keep it private even with this shared-secret check; use an authenticated internal gateway before exposing outbound call creation beyond a local exercise environment.

## Qualify a development call

1. Start the two processes and establish an HTTPS route to `/livekit-webhook`.
2. Call the configured Telnyx number from a test phone. Verify two-way speech, the organization greeting, an authorized test carrier lookup, and retrieval of the seeded load. Inspect the call record in the isolated database.
3. With quote sandbox access, follow an accepted negotiation through quote submission and confirm its sandbox receipt.
4. With an available test broker and development Slack channel, request a warm transfer. The carrier remains in Room1 while the bot dials and briefs the broker in Room2. When briefing completes, LiveKit moves the broker participant into Room1 and removes Room2. Confirm the carrier and broker can speak after the move.
5. End the call and inspect final call status, transcript, recording, participant cleanup, and temporary-room cleanup.

Complete each integration step when its prerequisites are available. The repository's automated tests mock LiveKit and the external providers; no real LiveKit, Telnyx, speech-provider, carrier-service, transfer, or quote path is claimed as validated by those tests.

## Run the dashboard

The dashboard requires Node.js 22 and package read access to private `@e3-solutions/ui@0.3.6`. Follow [the dashboard README](../web/README.md) to obtain access and configure `NODE_AUTH_TOKEN` before running `npm ci`. Use its documented build and standalone-server commands to verify the production build locally. Keep the dashboard and voice service pointed at the same isolated database.

## Container build contexts

The voice images include `shared/`, `ffmpeg`, `libsndfile1`, and NLTK sentence-tokenizer data. Build from the repository root:

```bash
docker build -f voice-agent/Dockerfile.server -t negotiation-server .
docker build -f voice-agent/Dockerfile.bot -t negotiation-bot .
```

Use the two explicit Dockerfiles above. Container networking and isolated environment configuration are required before running either image; `localhost` inside one container cannot reach the other container. Set `LOCAL_BOT_URL` to a bot-runner address reachable from the server container.
