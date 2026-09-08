# Negotiation dashboard

This Next.js dashboard displays loads, calls, negotiations, transcripts, and recordings from the configured Supabase project.

## Prerequisites

- Node.js 22 and npm. The checked-in Next.js 16 dependency requires Node.js 20.9 or newer; Node.js 22 is the documented setup target.
- Read access to private GitHub package `@e3-solutions/ui@0.3.6`.
- An isolated Supabase project prepared using [Database setup](../docs/DATABASE_SETUP.md), with a dashboard account and organization.

## Obtain package access

Ask the repository maintainer to grant your GitHub account read access to the existing `@e3-solutions/ui` package. Access to this repository alone may not grant package access. Use an authorized personal access token (classic) with `read:packages`; complete organization SSO authorization if required. See [GitHub's npm registry authentication guidance](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-npm-registry).

The checked-in `.npmrc` maps `@e3-solutions` to GitHub Packages and reads `NODE_AUTH_TOKEN` from the shell. npm does not read `.env.local` during installation. Keep tokens out of committed files and terminal history; in Bash, enter the token interactively:

```bash
read -r -s -p "GitHub Packages token: " NODE_AUTH_TOKEN
export NODE_AUTH_TOKEN
```

An HTTP 401/403 during installation means the token, account permission, or organization authorization needs attention. The private dependency is required; request access before continuing.

## Install and configure

From `web/`:

```bash
npm ci
cp .env.example .env.local
```

Use the same isolated Supabase URL as the voice service, its public anon key, and its server-only service role key. Set `NEXT_PUBLIC_AGENT_PHONE_NUMBER` to the development LiveKit SIP number. Optional server `SUPABASE_URL` and `SUPABASE_ANON_KEY` values override their `NEXT_PUBLIC_` counterparts; if set, they must refer to the same project.

Set `COMPANY_REGISTRATION_SECRET_HASH` to the SHA-256 hash of a development registration code. You can generate the hash without saving the code in shell history:

```bash
python3 - <<'PYCODE'
import getpass
import hashlib
print(hashlib.sha256(getpass.getpass("Development registration code: ").encode()).hexdigest())
PYCODE
```

Use the original code when registering a company at `/register`. Leaving the hash empty allows unrestricted company registration, so use a configured hash for the handoff. Registration and login also need working Supabase Auth and the database setup described above.

## Run and build

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). To check the production build and run it locally instead, stop the development server and run:

```bash
npm run build
cp -R public .next/standalone/
cp -R .next/static .next/standalone/.next/
HOSTNAME=127.0.0.1 PORT=3000 node --env-file=.env.local .next/standalone/server.js
```

This project builds with `output: "standalone"`. The generated server needs the public and static files copied alongside it, and Node loads the isolated runtime configuration from `.env.local` before starting it. The web Dockerfile packages these files automatically.

The build fetches Google fonts used in `app/layout.tsx`, so it requires outbound access to Google Fonts as well as package access during installation. Confirm login and representative load/call views against the isolated database after the server starts; `/api/health` only checks process availability.

## Container build

With `NODE_AUTH_TOKEN` exported as above, build from the repository root. Pass the public settings for your isolated project:

```bash
docker build --secret id=node_auth_token,env=NODE_AUTH_TOKEN \
  --build-arg NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321 \
  --build-arg NEXT_PUBLIC_SUPABASE_ANON_KEY=replace-with-isolated-anon-key \
  --build-arg NEXT_PUBLIC_AGENT_PHONE_NUMBER=+15555550100 \
  --build-arg NEXT_PUBLIC_ENVIRONMENT=local \
  -t negotiation-web ./web
```

The package token is supplied through a BuildKit secret. Supply `SUPABASE_SERVICE_ROLE_KEY` and `COMPANY_REGISTRATION_SECRET_HASH` when running the container, using the isolated project's values from `.env.local`. Server requests need a Supabase URL reachable from inside the container; the injected public URL must also be reachable by the browser. Use an isolated host address reachable by both for a container-backed local setup.

The companion voice server and bot runner are documented in [Local setup](../docs/LOCAL_SETUP.md).
