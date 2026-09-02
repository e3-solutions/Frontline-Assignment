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

`requirements.txt` installs `../shared` as an editable package. Keep both directories together. The NLTK download installs Pipecat sentence tokenizer data in the standard user data location and requires internet access during setup. If you use a custom location, export `NLTK_DATA` before running Python; setting it only in `.env` is too late for imports that initialize NLTK. The default pipeline uses local ONNX-based Silero voice activity detection and Smart Turn v3. Their dependencies come from the Pipecat extras in the requirements; the default Cartesia/ONNX path does not require a separate PyTorch installation. Importing the application and starting an actual pipeline are separate checks.

## Configure development services

Fill in `voice-agent/.env` using development resources supplied or approved by the repository maintainer:

| Integration | Required configuration |
| --- | --- |
| Daily | `DAILY_API_KEY`, a development phone number with dial-in access, and dial-out/SIP access for transfers |
| Speech and LLM | `DEEPGRAM_API_KEY`, `OPENAI_API_KEY`, `CARTESIA_API_KEY`; the runtime uses `nova-3`, `gpt-4.1`, and the Cartesia voice configured in `bot.py` |
| Supabase | `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` for the isolated project, schema/data setup, and recording storage |
| Carrier verification | An authorized carrier test service; configure the existing Highway backend and its base URL/key for isolated MC lookups |
| Quote submission | Matching `KCH_QUOTE_CLIENT_ID`, `KCH_QUOTE_CLIENT_SECRET`, and `KCH_QUOTE_SCOPE` with `KCH_QUOTE_USE_SANDBOX=true` |
| Broker transfer | A test broker phone in the load's routing data and `SLACK_WEBHOOK_URL` for a development channel |

Use [Database setup](DATABASE_SETUP.md) before running a data-backed call. The dialed Daily number must map to the correct organization, and that organization needs a representative load, stops, and transfer routing. The dashboard uses the same database project. Keep service role credentials server-side.

The historical `carrier_api` backend uses an external production endpoint. `CARRIER_MC_BACKEND=highway` selects the existing Highway MC path; `HIGHWAY_API_BASE_URL` must point to the authorized development endpoint. USDOT lookup still uses the historical carrier endpoint. The configuration is not a global offline mode: quote sandbox selection affects only quote submission. Exercise provider paths after the corresponding test access is established.

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

Expected responses are `{"status":"healthy"}` and `{"status":"ok"}`. With `ROOM_POOL_SIZE=0` in `.env`, server startup skips Daily room precreation. These responses do not test speech, Daily calls, database access, or any tool execution. A webhook still attempts room creation even when the pool size is zero.

`LOCAL_BOT_URL` tells the server how to reach the bot runner; `LOCAL_SERVER_URL` tells the bot how to return rooms. Each process also accepts `PORT`; leave it unset in the shared `.env` to use the distinct defaults, or set it separately for each process.

## Connect a development phone number

1. Finish the service and database setup above. Set `ROOM_POOL_SIZE=1` in `.env` and restart the webhook server. Confirm that its logs report an available Daily room; HTTP health alone does not check the pool.
2. Expose the webhook server:

   ```bash
   ngrok http 8080
   ```

3. Configure the development Daily number's `room_creation_api` as `https://<your-tunnel-host>/daily-webhook`, following the [Daily dial-in documentation](https://docs.daily.co/reference/rest-api/dial-in). The included waiting audio is served at `https://<your-tunnel-host>/static/music/ring-tone-68676.mp3`; configure it through Daily if needed.
4. Call the configured number from a test phone. Verify two-way speech, the organization greeting, an authorized test carrier lookup, and retrieval of the seeded load. Inspect the call record in the isolated database.
5. With quote sandbox access, follow an accepted negotiation through quote submission and confirm its sandbox receipt. With an available test broker and development Slack channel, exercise the transfer and confirm that the broker and caller connect.
6. End the call and check the final call status, transcript, recording, and room cleanup in the isolated services.

Complete each integration step when its prerequisites are available. A successful local health response or mocked functional test does not substitute for these checks.

## Run the dashboard

The dashboard requires Node.js 22 and package read access to private `@e3-solutions/ui@0.3.6`. Follow [the dashboard README](../web/README.md) to obtain access and configure `NODE_AUTH_TOKEN` before running `npm ci`. Use its documented build and standalone server commands to verify the production build locally.

## Container build contexts

The voice images include `shared/`, `ffmpeg`, `libsndfile1`, and NLTK sentence tokenizer data. Build from the repository root:

```bash
docker build -f voice-agent/Dockerfile.server -t negotiation-server .
docker build -f voice-agent/Dockerfile.bot -t negotiation-bot .
```

Use the two explicit Dockerfiles above. Container networking and isolated environment configuration are required before running either image; `localhost` inside one container cannot reach the other container.
