# 0029 - loot-bot: stack, account linking, and data isolation

Status: accepted

## Context

[docs/domain/client-views.md](../domain/client-views.md) names a Discord bot as the worked example for the inventory-manager vertical slice: players see their own stuff, filtered by whatever the GM chose to make visible. This is the first app under `apps/` other than `apps/api` ([ADR 0007](0007-apps-layout-and-multiplicity.md)), and per [docs/guides/adding-an-app.md](../guides/adding-an-app.md) the language, framework, and scope needed confirming with the user before any code — done: TypeScript/discord.js, one bot process per Discord guild per Lorenzo tenant. Scope for this first slice is read-only: link a Discord user to their real Authgear-verified Lorenzo identity, then list the item instances their characters own. Loot-splitting (writes) needs [RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md), not built yet, and is explicitly a later slice.

Two things made this non-trivial, both confirmed against the current codebase rather than assumed:

- **No shared GM/service token is acceptable.** The bot must call the Lorenzo API as the specific Discord user it's serving, or `information_visibility.py`'s per-player visibility rules (GM-only vs. public vs. per-character `knowledge`) would be silently bypassed for everyone using the bot.
- **Two backend gaps block even a read-only "my inventory" feature today**: nothing resolves "which characters does this authenticated user control" over HTTP, and the existing `GET /tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}` — the exact endpoint this feature needs — is gated by `get_tenant_context`, which requires a tenant-wide `Membership` row that ordinary players never have by design. Both gaps are closeable using tables that already exist (`player`, `character_player`, `being` — no new tables), and are being built separately as part of ongoing `apps/api` CRUD work, not by this app. This ADR only records what `loot-bot` itself needs and assumes, not the backend change.

## Decision

### App: `apps/loot-bot`

Named per [ADR 0007](0007-apps-layout-and-multiplicity.md)'s purpose-not-type rule — already used three times in this repo's own docs as the canonical example of exactly this kind of app ([`adding-an-app.md`](../guides/adding-an-app.md), ADR 0007, [`writing-a-commit-message.md`](../guides/writing-a-commit-message.md)). Differentiated from a hypothetical second, GM-facing bot (session scheduling, dice-rolling) by being specifically the player-facing, linked-identity, personal-inventory one.

### Stack

| Concern | Choice | Why |
| --- | --- | --- |
| Discord | discord.js v14, `GatewayIntentBits.Guilds` only | No message-content/privileged intents needed for slash commands |
| OAuth/OIDC client | `openid-client` | Standard, actively-maintained Node OIDC client — same reasoning [ADR 0009](0009-identity-provider-authgear.md) already gave against hand-rolling auth-critical code |
| OAuth callback server | bare `node:http`, a couple of routes | Matches `apps/api/scripts/get_dev_token.py`'s own precedent; a framework's value-adds don't engage for `/auth/callback` + `/healthz` |
| Bot's own DB access | Drizzle ORM + drizzle-kit, over `pg` | The direct TS equivalent of `apps/api`'s SQLAlchemy+Alembic pairing — a real ORM plus a real migration tool, not hand-rolled SQL |
| Lorenzo API client | `openapi-typescript` + `openapi-fetch`, generated from `apps/api`'s dumped `openapi.json` | [ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md) picked stable `operationId`s specifically for client codegen |
| Build | `tsup` (esbuild) for the shipped bundle; `tsc --noEmit` for type-checking only | Sidesteps Node-ESM relative-import-extension bookkeeping entirely; `tsx` (also esbuild-based) for `dev` needs no such bookkeeping either |
| Config | `zod`-validated env, Node 22's native `--env-file` | No `dotenv` dependency needed |
| Logging | `pino` (structured JSON) | The TS equivalent of `structlog` |
| Tests | Vitest + MSW | Matches the real-toolchain spirit of `pytest`+`pytest-asyncio`+`httpx`; native TS/ESM, first-class HTTP mocking |
| Lint/format | Biome | Already named for this exact purpose in [ADR 0004](0004-static-astro-frontend.md), not wired up until now |

### Account linking: OAuth Authorization Code + PKCE, per Discord user

`apps/api/scripts/get_dev_token.py` already proves the mechanism against this project's Authgear setup (PKCE, discovery-driven endpoints, code exchange) — this extends it into a durable, multi-user, always-on form, with three deltas: scope gains `offline_access` (confirmed required for a refresh token, checked against Authgear's own docs), the single in-memory result closure becomes a keyed map (several Discord users can be mid-flow concurrently), and the token response is persisted (encrypted) instead of printed once.

- **A dedicated, confidential OIDC/SAML Client Application** is registered in the Authgear project (separate from `apps/api`'s own dev client — `apps/api` itself registers no client at all, it's a resource server). Scope `openid offline_access`. PKCE used on top of the client secret, belt-and-suspenders.
- **`/link`** generates `state` + a PKCE verifier/challenge pair, stores the pending flow in an in-memory `Map` (not a DB table — single-process bot, short-lived data; a lost in-flight attempt on restart just means re-running `/link`), and replies ephemerally with the Authgear authorization URL built straight from discovery. Always overwrites any existing link on completion — covers re-linking without a separate unlink step.
- **`/auth/callback`** exchanges the code, encrypts the resulting tokens, and upserts `linked_account` keyed by `discord_user_id`. `authgear_subject_id` is stored `UNIQUE`, mirroring `app_user`'s own constraint, so one Lorenzo identity can't silently attach to two Discord users.
- **Refresh** is lazy, triggered by whichever command needs a token: reuse a cached access token until near expiry, otherwise use the refresh grant. The stored refresh token is overwritten only if the response actually includes a new one (correct whether or not Authgear rotates refresh tokens on use — genuinely undocumented behavior, checked directly rather than assumed). `invalid_grant` deletes the row and surfaces "run `/link` again" — never fails silently. In-process single-flight de-duplication avoids two concurrent commands racing the same refresh.
- **Encryption at rest**: AES-256-GCM (Node's built-in `crypto`), one key from an env-provided secret, fresh random IV per encryption, `iv‖ciphertext‖authTag` in one `bytea` column, `key_version` stored per row from day one so a future key rotation costs nothing to have anticipated. No KMS — not justified at this project's already-stated "low-traffic, cost-conscious, personal" scale ([ADR 0011](0011-deploy-target-cloud-run-neon.md)/[ADR 0027](0027-authgear-cloud-not-self-hosted.md)).
- The bot never verifies the Lorenzo access token itself (no `PyJWKClient` equivalent) — it only obtains one from Authgear and passes it through as a bearer token, exactly like `get_dev_token.py`'s own closing `curl` example. `apps/api` remains the sole verifier.

### Data isolation: own role + schema, same Postgres instance — not a second database

A second logical database would isolate more cleanly, but `.github/workflows/ci.yml`'s `services.postgres` block provisions exactly one database with no init-script mechanism to add a second one in CI. Instead: a dedicated Postgres role and schema (`loot_bot`/`loot_bot`) inside the same `lorenzo` database, bootstrapped by the bot's own first Drizzle migration using the same pattern `apps/api/migrations/versions/8aced4b80842_create_restricted_lorenzo_app_role.py` already established (parse the target role/password out of the app's own database URL; `CREATE ROLE`/`CREATE SCHEMA ... AUTHORIZATION`/`GRANT`/`ALTER DEFAULT PRIVILEGES`), run via the same already-privileged bootstrap role `apps/api`'s own migrations use. `drizzle-kit`'s `schemaFilter` keeps it structurally incapable of touching `apps/api`'s tables. No RLS on these tables: one bot instance serves exactly one tenant's Discord users, so there's no cross-tenant row in the same table to isolate against the way `apps/api`'s shared schema needs — the isolation boundary here is the process/schema/role, not a row policy.

One narrow, called-out CI change: `ci.yml`'s `test` job env block gains `LOOT_BOT_DATABASE_URL`/`LOOT_BOT_MIGRATIONS_DATABASE_URL`, reusing the Postgres service container already provisioned there.

## Consequences

- `apps/api` needs a small backend addition before `loot-bot`'s `/inventory` command is fully functional: resolving "which characters does this user control" (extending `GET /me` per [RFC 0004](../rfcs/0004-user-membership-player-character-gm-read-api.md)'s already-recorded direction is the leading option) and loosening `GET /tenants/{tenant_id}/item-instances/owned-by/{owner_entity_id}`'s access check to allow a caller acting on their own controlled character without a tenant-wide `Membership` row. Tracked as part of the ongoing CRUD API work, not this app.
- Root `mise.toml`'s `[monorepo].config_roots` gains `apps/loot-bot`; `release-please-config.json` gains a `node`-type entry; `.github/dependabot.yml` gains `npm`+`docker` entries; `.pre-commit-config.yaml` gains Biome/`tsc` hooks scoped to `apps/loot-bot`. `pnpm-workspace.yaml` needs no change (`apps/*` already covers it) — this is the first real `pnpm install`, so it creates the workspace-root `pnpm-lock.yaml`.
- Deploying this app is deferred, not designed here: a persistent Discord gateway connection doesn't fit Cloud Run's scale-to-zero model `apps/api` relies on ([ADR 0011](0011-deploy-target-cloud-run-neon.md)) — a real future decision.
- Out of scope for this slice: `/unlink` (re-running `/link` already covers realistic cases), loot-splitting/any write, multi-guild or multi-tenant support in one process, rate-limiting.
