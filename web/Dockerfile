# syntax=docker/dockerfile:1.6

FROM node:22-bullseye AS builder

WORKDIR /app

# Build arguments for Next.js env vars (optional)
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
ARG NEXT_PUBLIC_AGENT_PHONE_NUMBER
ARG NEXT_PUBLIC_ENVIRONMENT

# Make them available as environment variables during build
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL \
    NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY \
    NEXT_PUBLIC_AGENT_PHONE_NUMBER=$NEXT_PUBLIC_AGENT_PHONE_NUMBER \
    NEXT_PUBLIC_ENVIRONMENT=$NEXT_PUBLIC_ENVIRONMENT

# .npmrc contains an environment-variable reference, never the package token.
COPY package.json package-lock.json .npmrc ./
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=secret,id=node_auth_token,required=true \
    NODE_AUTH_TOKEN="$(cat /run/secrets/node_auth_token)" npm ci

COPY . .

# Route collection imports the admin client, which requires a nonempty key.
# Supply real server credentials only when running the image.
RUN SUPABASE_SERVICE_ROLE_KEY=build-placeholder npm run build

FROM node:22-bullseye-slim AS runner

WORKDIR /app

ENV NODE_ENV=production \
    PORT=3000 \
    HOSTNAME="0.0.0.0"

RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy standalone build
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
COPY --from=builder --chown=nextjs:nodejs /app/public ./public

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]
