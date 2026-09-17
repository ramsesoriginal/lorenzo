# Build context is the repo root, not this directory - this app is a pnpm
# workspace member sharing the root lockfile (ADR 0003/0029), not a
# standalone project. See mise.toml's `build` task, which runs
# `docker build -f Dockerfile ../..` from here.
#
# NOTE: written but not built in the environment this was authored in (no
# Docker available there) - deployment itself is out of scope for this
# slice (ADR 0029); smoke-test this before relying on it.

FROM node:22-slim AS build
WORKDIR /workspace

COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps ./apps
RUN corepack enable && pnpm install --frozen-lockfile

WORKDIR /workspace/apps/loot-bot
RUN pnpm run build
# Writes a self-contained directory (package.json + a pruned, non-symlinked
# node_modules for exactly this workspace member's resolved prod
# dependencies) - pnpm's own documented mechanism for a monorepo-to-single-
# image build, instead of hand-rolling a filtered install.
RUN pnpm deploy --filter @lorenzo/loot-bot --prod /deploy

FROM node:22-slim
WORKDIR /app

COPY --from=build /deploy/node_modules ./node_modules
COPY --from=build /deploy/package.json ./package.json
COPY --from=build /workspace/apps/loot-bot/dist ./dist

# node:22-slim already ships a non-root `node` user (uid 1000) for exactly
# this purpose - `useradd` here collided with it instead of adding a new one.
USER node

EXPOSE 8090
# tsup mirrors each entry's source subdirectory under dist/ (src/index.ts ->
# dist/src/index.js) since entries span both src/ and scripts/ - confirmed
# against a real local build, not assumed.
#
# Shell form, not exec form: Cloud Run injects its own $PORT (8080, not this
# image's 8090 default) and expects the container to listen on exactly that
# - same fix apps/api's own Dockerfile already needed (see
# docs/operations/deployment-setup.md's history note) for the same reason.
# config.ts only ever reads LOOT_BOT_HTTP_PORT, never Cloud Run's PORT
# directly, so it has to be forwarded here instead.
CMD ["sh", "-c", "LOOT_BOT_HTTP_PORT=${PORT:-8090} exec node dist/src/index.js"]
