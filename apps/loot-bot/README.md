# apps/loot-bot

Lorenzo's Discord bot. TypeScript, Node, discord.js. One bot process serves exactly one Discord guild, mapped 1:1 to one Lorenzo tenant. See [ADR 0029](../../docs/adr/0029-loot-bot-stack-linking-and-isolation.md) for the design and its reasoning, and [docs/domain/client-views.md](../../docs/domain/client-views.md) for why this bot exists at all.

## What it does (this slice)

A player links their Discord account to their real Authgear-verified Lorenzo identity (`/link`), then lists the item instances their characters own, grouped by container (`/inventory`). Read-only — no shared GM/service token: every API call is made as the specific Discord user who ran the command, so [`information_visibility.py`](../api/src/lorenzo_api/information_visibility.py)'s per-player visibility rules (GM-only vs. public vs. per-character knowledge) apply correctly per person.

**Depends on a small `apps/api` addition that isn't part of this app**: resolving "which characters does this user control" and allowing a player to read their own inventory without a tenant-wide `Membership` row. See ADR 0029's Consequences section.

## Setup

1. **Discord**: create an application at the [Discord Developer Portal](https://discord.com/developers/applications), add a bot user, invite it to your test server with the `applications.commands` scope. `DISCORD_BOT_TOKEN`/`DISCORD_CLIENT_ID` come from there; `DISCORD_GUILD_ID` is your test server's id (Developer Mode → right-click the server).
2. **Authgear**: register a new, *separate* OIDC/SAML Client Application (confidential — gets a client secret) in the same Authgear project `apps/api` verifies tokens against — see [`docs/operations/local-authgear-setup.md`](../../docs/operations/local-authgear-setup.md) for the portal walkthrough (this bot needs its own client, not `apps/api`'s dev one). Scope `openid offline_access`. Authorized Redirect URI: `LOOT_BOT_PUBLIC_BASE_URL` + `/auth/callback` (`http://127.0.0.1:8090/auth/callback` for local dev).
3. **Postgres**: reuses `apps/api`'s own instance ([`infra/docker-compose.yml`](../../infra/docker-compose.yml)) — a separate role/schema (`loot_bot`/`loot_bot`), never `apps/api`'s own `lorenzo_app`/`lorenzo` schema. `mise run db-migrate` bootstraps the role/schema on first run.
4. Copy [`.env.example`](.env.example) to `.env` and fill in the above (read relative to this directory, not the repo root — see the root [`.env.example`](../../.env.example)'s own note on this).

## Run

```bash
mise run //apps/loot-bot:db-migrate      # once, and after any schema change
mise run //apps/loot-bot:register-commands  # once, and after any command change
mise run //apps/loot-bot:dev              # with autoreload
```

## Test

```bash
mise run //apps/loot-bot:test
```

Command-formatting and API-client tests are mocked (MSW) or pure-fixture; the account-linking flow is tested against a local fake Authgear-shaped server (real PKCE/JWT mechanics, fake issuer — mirrors [`apps/api/tests/_fake_jwks.py`](../api/tests/_fake_jwks.py)'s own principle); anything touching `loot_bot`'s own tables needs a real local Postgres, same as `apps/api`'s own test suite.

## Commands

| Command | Does |
| --- | --- |
| `/link` | Starts account linking — replies with a one-time Authgear login URL |
| `/inventory` | Lists the item instances your linked characters own, grouped by container |
| `/ping` | Liveness check |

## Architecture

- `src/config.ts` — env loading/validation (zod).
- `src/http-server.ts` — a bare `node:http` server (`/healthz`, `/auth/callback`) — no framework; see ADR 0029 for why.
- `src/commands/` — one file per slash command, dispatched by `src/commands/index.ts`.
- `src/token-provider.ts` — `getValidAccessToken(discordUserId)`: the seam between commands and the account-linking/refresh machinery.
- `src/lorenzo-client.ts` — a thin wrapper over a generated (`openapi-typescript`/`openapi-fetch`) typed client for `apps/api`. Regenerate with `mise run generate-client` after `apps/api`'s OpenAPI schema changes.
- `src/db-schema.ts`/`src/db.ts` — Drizzle ORM over the bot's own `loot_bot` Postgres schema (`linked_account`, the account-linking store) — entirely separate from `apps/api`'s own tenant-scoped, RLS'd tables.

## Deployment

Not yet decided. A persistent Discord gateway connection doesn't fit Cloud Run's scale-to-zero model the way `apps/api` does ([ADR 0011](../../docs/adr/0011-deploy-target-cloud-run-neon.md)) — a real future decision, out of scope for this slice.
