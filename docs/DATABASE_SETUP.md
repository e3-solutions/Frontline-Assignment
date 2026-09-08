# Local database setup

Use one disposable local Supabase instance per candidate. The voice backend
needs Supabase's Data API and service-role key; a standalone PostgreSQL server
does not provide those services. The dashboard additionally needs Supabase Auth.

## Start an isolated Supabase instance

Install Docker, Node.js, Python 3.11, and the PostgreSQL client (`psql`). Ensure
Docker is running. The commands below use Supabase CLI 2.116.0 through `npx`.
See the [official local CLI guide](https://supabase.com/docs/guides/local-development/cli/getting-started)
for platform installation prerequisites.

From the candidate repository root, create a separate local Supabase working
directory. Keep it outside this repository: the historical migration files are
split across two directories and require the installer's compatibility steps.

```bash
mkdir ../candidate-supabase-local
npx --yes supabase@2.116.0 init --workdir ../candidate-supabase-local
docker network create --driver bridge \
  --opt com.docker.network.bridge.host_binding_ipv4=127.0.0.1 candidate-supabase-loopback
npx --yes supabase@2.116.0 start --workdir ../candidate-supabase-local \
  --network-id candidate-supabase-loopback \
  --exclude realtime,edge-runtime,logflare,vector,supavisor,imgproxy
```

This starts the database, Auth, Data API, Storage, local mail catcher, and Studio.
The dedicated network binds published ports to loopback using Docker's
[bridge binding option](https://docs.docker.com/engine/network/drivers/bridge/#default-host-binding-address).
Use the same `--network-id` each time you start this instance. The excluded
services are not required by this application's local setup. Do
not link this directory to an existing Supabase project. If default ports are
already occupied, choose free ports in that directory's `supabase/config.toml`
before starting, and pass the chosen database port to the installer.

## Initialize and seed

Still from the candidate repository root:

```bash
python3 scripts/setup_local_database.py init
python3 scripts/setup_local_database.py seed
```

Each command prompts for the local database password (the default CLI setup uses
`postgres`). The installer only connects to `127.0.0.1`; it has no remote-host or
connection-URL option. `init` refuses a nonempty application schema and requires
existing Supabase Auth objects and API roles. For a different local database
port, add `--port 56322` (substitute the actual port) to both commands.

The installer replays all 39 supplied SQL files in filename order. It supplies
two missing historical transition steps: removing dependent SELECT policies
before the UUID-to-text load conversion, and retaining the old empty load table
as `loads_legacy` before creating the current load-number catalog. It then adds
local access policies and explicit Data API grants. The historical migrations,
including the email-related schema, remain unchanged.

If initialization stops partway through, do not rerun it over the partial schema.
Recreate only this disposable local instance using the cleanup command below,
start it again, and rerun `init` and `seed`. This installer does not manage a
remote migration ledger and is not a deployment workflow.

The synthetic seed contains:

| Item | Value |
| --- | --- |
| Organization | `Candidate Sandbox` / `00000000-0000-4000-8000-000000000001` |
| Inbound bot number | `+12025550100` |
| Load reference | `DEMO-1001` |
| Stops | Chicago pickup and Indianapolis delivery |
| Transfer number | `+12025550101` |

The default numbers are placeholders. The load includes equipment, cargo,
rates, stop windows, and a transfer destination so the existing load lookup can
read a complete record. The seed does not populate carrier-verification caches,
calls, quotes, or negotiations. It creates no Auth account.

## Add a local dashboard user

Run the following to find the local Studio URL and API keys:

```bash
npx --yes supabase@2.116.0 status --workdir ../candidate-supabase-local
```

In local Studio, open **Authentication → Users** and create a development user.
Copy its UUID, then link that existing Auth account to the seeded organization:

```bash
python3 scripts/setup_local_database.py seed --auth-user-id YOUR_LOCAL_AUTH_USER_UUID
```

The command verifies the Auth row exists and refuses to move a user who already
belongs to another organization. Sign in to the dashboard with that development
account after completing the package-access and environment steps in
[LOCAL_SETUP.md](LOCAL_SETUP.md).

The current load catalog has no `org_id`. In this local setup, authenticated users
with an application profile share the synthetic catalog. Calls remain scoped by
their recorded organization. Use a separate local instance per candidate; this
configuration is not intended for a shared hosted database. Historical email
tables are retained, and only the existing dashboard thread/interaction reads
are granted to authenticated users.

## Create the recording bucket

In local Studio, open **Storage** and create a bucket named `call-recordings`.
Enable **Public bucket** for this disposable instance's synthetic test audio.
The existing recording uploader uses the server-side service-role key to upload
WAV files and stores a public URL; a private bucket would make that URL unusable.
No browser upload policy is required. Keep production recordings out of this
local public bucket.

## Configure the applications

Copy the API URL and legacy `anon` / `service_role` keys from your local instance:

- Voice: `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Dashboard: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `SUPABASE_URL`, and `SUPABASE_SERVICE_ROLE_KEY`.

Keep both applications pointed at the same local instance. The service-role key
is server-only; never put it in a `NEXT_PUBLIC_` variable. Containerized
applications must use an address that reaches the host's local Supabase API;
`localhost` inside an application container points at that container.

For a real development LiveKit SIP call, register your assigned inbound number against
the seeded organization and use a transfer destination you control:

```bash
python3 scripts/setup_local_database.py seed \
  --phone-number +YOUR_DEVELOPMENT_LIVEKIT_NUMBER \
  --transfer-phone +YOUR_DEVELOPMENT_TRANSFER_NUMBER
```

These arguments require E.164 digits, for example `+12025550100`. Match the
inbound number to the trunk number LiveKit sends as `bot_phone`. The runtime looks up
organization identity through `phone_numbers → organizations`, reads the load
through `loads.load_number`, embeds stops through `stops_load_number_fkey`, and
uses `loads.carrier_sales_rep_phone` for transfers. There is no global transfer
fallback. Repeating `seed` preserves existing load details and updates only this
sample load's transfer phone when `--transfer-phone` is explicitly supplied.
Linking a user or rerunning `seed` without that argument preserves existing
transfer routing.

Provider credentials, a reachable LiveKit webhook, development phone provisioning,
carrier lookups, and quote authorization are separate prerequisites. Local
database setup alone does not establish a working provider call or transfer.

## Stop or recreate this local instance

To stop while retaining its local data:

```bash
npx --yes supabase@2.116.0 stop --workdir ../candidate-supabase-local
```

To delete **only this disposable instance's** local data before a fresh setup:

```bash
npx --yes supabase@2.116.0 stop --workdir ../candidate-supabase-local --no-backup
```

Run the `start`, `init`, and `seed` commands again after deleting its data. Do not
use `--all`, `link`, or `db push` for this local candidate setup.

After stopping all containers for this instance, remove its dedicated network
when it is no longer needed:

```bash
docker network rm candidate-supabase-loopback
```
