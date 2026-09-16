# apps/loot-bot

Lorenzo's Discord bot. TypeScript, Node, discord.js. One bot process serves exactly one Discord guild, mapped 1:1 to one Lorenzo tenant. See [ADR 0042](../../docs/adr/0042-loot-bot-stack-linking-and-isolation.md) for the design and its reasoning, and [docs/domain/client-views.md](../../docs/domain/client-views.md) for why this bot exists at all.

## What it does

A player links their Discord account to their real Authgear-verified Lorenzo identity (`/link`, `/unlink`), sets a current character/default container (`/set-current`), lists the item instances their characters own, grouped by container (`/inventory`), displays one in the channel (`/item`), moves one between their own containers (`/move`), adds a public/private/GM-private note to one (`/note`), and gives an item — or part of a stack — to another character (`/give`, [ADR 0043](../../docs/adr/0043-loot-bot-give-command.md)). A GM can award a brand-new item to a character (`/award`), or drop a pre-made loot container into a channel; players take a whole item or part of a stack immediately, or claim one for the GM to resolve later with "apply claims" (`/drop`, [ADR 0044](../../docs/adr/0044-loot-bot-loot-drop-and-claims.md)). No shared GM/service token: every API call is made as the specific Discord user who ran the command, so [`information_visibility.py`](../api/src/lorenzo_api/information_visibility.py)'s per-player visibility rules and the write API's own self-or-managed authorization apply correctly per person.

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
| `/unlink` | Unlinks your Discord account from your Lorenzo identity |
| `/set-current` | Sets your current character and/or default container — what other commands default to |
| `/inventory` | Lists the item instances your linked characters own, grouped by container |
| `/give` | Gives an item (or part of a stack) to another character — autocompleted item/target |
| `/drop` | GM-only: drops a pre-made loot container into the channel — take/claim/unclaim, then "apply claims" |
| `/award` | GM-only: awards a brand-new item straight from the catalog to a character |
| `/item` | Displays an item's description, stats, and notes in the channel |
| `/move` | Moves one of your items into another container you own |
| `/note` | Adds a public, private, or GM-private note to an item |
| `/ping` | Liveness check |

## Architecture

- `src/config.ts` — env loading/validation (zod).
- `src/http-server.ts` — a bare `node:http` server (`/healthz`, `/auth/callback`) — no framework; see ADR 0042 for why.
- `src/commands/` — one file per slash command, dispatched by `src/commands/index.ts` (chat-input, autocomplete, and — since `/drop`, ADR 0044 — select-menu/button/modal interactions too, routed by a `customId` namespace convention).
- `src/commands/item-transfer.ts` — the split-vs-whole-transfer decision `/give` and `/drop`'s take/apply-claims share.
- `src/token-provider.ts` — `getValidAccessToken(discordUserId)`: the seam between commands and the account-linking/refresh machinery.
- `src/preferences.ts` — `resolveCurrentCharacter`/`resolveCurrentContainer`: the seam commands resolve an optional character/container parameter through, falling back to `/set-current`'s stored preference.
- `src/lorenzo-client.ts` — a thin wrapper over a generated (`openapi-typescript`/`openapi-fetch`) typed client for `apps/api`. Regenerate with `mise run generate-client` after `apps/api`'s OpenAPI schema changes.
- `src/db-schema.ts`/`src/db.ts` — Drizzle ORM over the bot's own `loot_bot` Postgres schema (`linked_account`, `player_preference`, `loot_drop`, `loot_claim`) — entirely separate from `apps/api`'s own tenant-scoped, RLS'd tables.

## Deployment

Google Cloud Run, same GCP project and CD pipeline as `apps/api` ([ADR 0011](../../docs/adr/0011-deploy-target-cloud-run-neon.md)). This needed a transport change first — a persistent Discord gateway connection doesn't fit Cloud Run's scale-to-zero model, so the bot receives interactions over Discord's HTTP Interactions Endpoint instead of the gateway; see [ADR 0045](../../docs/adr/0045-loot-bot-http-interactions-and-cloud-run-deploy.md) for why and how, and [`docs/operations/deployment-setup.md`](../../docs/operations/deployment-setup.md) for the one-time setup.
