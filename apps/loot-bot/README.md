# apps/loot-bot

Lorenzo's Discord bot. TypeScript, Node, discord.js. One bot process serves exactly one Discord guild, mapped 1:1 to one Lorenzo tenant. See [ADR 0050](../../docs/adr/0050-loot-bot-stack-linking-and-isolation.md) for the design and its reasoning, and [docs/domain/client-views.md](../../docs/domain/client-views.md) for why this bot exists at all.

## What it does

A player links their Discord account to their real Authgear-verified Lorenzo identity (`/link`, `/unlink`), checks which identity/characters/tenant role they're linked to (`/whoami`), posts a curated public introduction (`/introduce`), sets a current character/default container per Discord channel (`/set-current`), lists the item instances their characters own, grouped by container and optionally filtered by name (`/inventory`), displays one in the channel (`/item`), moves one between their own containers (`/move`) or empties a whole container into another in one call (`/move-bulk`), merges two stacks of the same item (`/merge`) or renames one (`/rename`), gives an item — or part of a stack — to another character (`/give`, [ADR 0051](../../docs/adr/0051-loot-bot-give-command.md)), gives several at once (`/give-bulk`), adds a public, private, GM-private, or group-visible note to one (`/note`), creates or joins a group (`/add-to-group`) and lists which groups their characters belong to (`/my-groups`), and can undo their own last give/reassign/move/rename/merge (`/undo`). A GM can award a brand-new item to a character (`/award`), inspect another character's inventory (`/inspect`), take an item away permanently (`/confiscate`), move one between two characters (`/reassign`), or sweep everyone who's recently posted in a channel into a group (`/add-channel-to-group`); a GM can also drop a pre-made loot container into a channel — players take a whole item or part of a stack immediately, or claim one (tagged need or greed — need always resolves first) for the GM to resolve later with "apply claims" or discard with "clear claims" (`/drop`, [ADR 0052](../../docs/adr/0052-loot-bot-loot-drop-and-claims.md)); anyone can check `/pending-claims` for a server-wide summary of what's still outstanding. See [ADR 0068](../../docs/adr/0068-loot-bot-inventory-and-gm-toolkit.md) for this GM-toolkit/inventory-hygiene round, including its own Addendum on consuming `apps/api`'s group-write/bulk-move/`is_container` additions (ADR 0064-0066). No shared GM/service token: every API call is made as the specific Discord user who ran the command (or, for `/add-channel-to-group`'s own read of each poster's characters, that specific poster's own stored token - never the invoking GM's), so [`information_visibility.py`](../api/src/lorenzo_api/information_visibility.py)'s per-player visibility rules and the write API's own self-or-managed authorization apply correctly per person.

## Setup

1. **Discord**: create an application at the [Discord Developer Portal](https://discord.com/developers/applications), add a bot user, invite it to your test server with the `applications.commands` scope. `DISCORD_BOT_TOKEN`/`DISCORD_CLIENT_ID` come from there; `DISCORD_GUILD_ID` is your test server's id (Developer Mode → right-click the server); `DISCORD_PUBLIC_KEY` is on the application's own "General Information" page — verifies inbound interaction webhooks ([ADR 0053](../../docs/adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)). Once the bot is reachable at a public URL, set the application's **Interactions Endpoint URL** to `<that url>/interactions` — Discord sends a `PING` immediately to verify it.
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
| `/set-current` | Pins your current character and/or default container for this channel — what other commands default to. Without one, your default is the character you last gave, moved, renamed, or merged an item as ([ADR 0088](../../docs/adr/0088-loot-bot-give-confirmation-and-last-used-character.md)) |
| `/inventory` | Lists the item instances your linked characters own, grouped by container, optionally filtered by name (`search`) |
| `/give` | Gives an item (or part of a stack) to another character — autocompleted item/target, with one Give/Cancel click before anything moves |
| `/give-bulk` | Gives several of your own items to one character at once (multi-select flow) |
| `/merge` | Combines two of your own stacks of the same item into one |
| `/rename` | Gives one of your own items a custom name |
| `/undo` | Undoes your own last give, reassign, move, rename, or merge (a few minutes' grace) |
| `/drop` | GM-only: drops a pre-made loot container (autocompleted from unowned and your own containers, or paste an id or slug — slugs also show in `/inventory`, `/inspect`, and `/item`, [ADR 0093](../../docs/adr/0093-loot-bot-drop-autocomplete-and-slug-surfacing.md)) into the channel — take/claim (need or greed) /unclaim, then "apply claims" or "clear claims" in one batch |
| `/pending-claims` | Lists every currently-open drop's outstanding claims, across the whole server — not GM-only |
| `/award` | GM-only: awards a brand-new item straight from the catalog to a character |
| `/inspect` | GM-only: looks at another character's inventory |
| `/confiscate` | GM-only: takes an item (or part of a stack) away from a character, permanently |
| `/reassign` | GM-only: moves an item from whichever character owns it to another |
| `/item` | Displays an item's description, stats, and notes in the channel |
| `/move` | Moves one of your items into another container you own |
| `/note` | Adds a public, private, GM-private, or group-visible note to an item |
| `/my-groups` | Lists which groups your characters belong to |
| `/add-to-group` | Adds a character to a group, creating it (with that character as its first member) if it doesn't exist yet |
| `/add-channel-to-group` | GM-only: adds every recently-active poster's characters in this channel to a group, creating it if needed |
| `/move-bulk` | Empties one of your containers into another, in one call |
| `/container-new` | Makes a named sack owned by your character, then lets you pick which of your loose items go inside — no leaving Discord ([ADR 0094](../../docs/adr/0094-loot-bot-container-new.md)). Needs a "Sack" catalog item, set up once by anyone with catalog access |
| `/whoami` | Shows which Lorenzo identity you're linked to, your full profile, tenant role, and your characters here — private |
| `/introduce` | Posts a curated public introduction (name, pronouns, bio, color, picture) to the channel |
| `/ping` | Liveness check |
| `/help` | Lists every command, grouped by what it's for, or (with `command`) one command's full options |

## Architecture

- `src/config.ts` — env loading/validation (zod).
- `src/http-server.ts` — a bare `node:http` server (`/livez`, `/auth/callback`, `/interactions`) — no framework; see ADR 0050 for why.
- `src/interactions-route.ts` — the `/interactions` route: verifies each webhook's Ed25519 signature (`src/discord-signature.ts`), builds this bot's adapter interaction (`src/interaction-adapter.ts`), and answers Discord's original request with whatever a command's first reply/deferReply/deferUpdate/update/showModal/respond call resolves — no `discord.js` Gateway `Client` involved ([ADR 0053](../../docs/adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)).
- `src/discord-rest.ts` — the small set of outbound Discord HTTP calls a deferred response needs (`editReply`/`followUp`), authenticated by the interaction's own token, not a bot token — plus one bot-token-authenticated exception, `getRecentChannelAuthorIds` (`/add-channel-to-group`'s own "who's been active here" source, a plain REST read of channel message history needing no Gateway connection).
- `src/commands/` — one file per slash command, dispatched by `src/commands/index.ts` (chat-input, autocomplete, and — since `/drop`, ADR 0052 — select-menu/button/modal interactions too, routed by a `customId` namespace convention). Every command file is written against `src/commands/types.ts`'s own transport-agnostic interaction types, not `discord.js`'s Gateway-only classes. `dispatchInteraction` also injects the full command list into `ctx.commands` before running any command - `/help`'s own source of truth (ADR 0068), not a second hand-maintained list.
- `src/commands/item-transfer.ts` — the split-vs-whole-transfer decision `/give`/`/reassign`/`/drop`'s take/apply-claims share (`transferItem`), and its destroy-side counterpart `/confiscate` uses (`destroyItem`).
- `src/commands/gm-roster.ts` — `findGmControlledCharacters`: every character in a campaign the caller GMs, shared by `/award`/`/inspect`/`/confiscate`/`/reassign`.
- `src/token-provider.ts` — `getValidAccessToken(discordUserId)`: the seam between commands and the account-linking/refresh machinery.
- `src/preferences.ts` — `resolveCurrentCharacter`/`resolveCurrentContainer`: the seam commands resolve an optional character/container parameter through, falling back to `/set-current`'s stored preference, scoped per Discord channel (ADR 0068) with a global-default fallback for contexts with no channel (e.g. `/link`'s own auto-set-on-single-character behavior).
- `src/undo-actions.ts` — `recordUndo`/`applyPendingUndo`: `/undo`'s own record-then-reverse machinery, backing `/give`/`/reassign`/`/move`/`/rename`/`/merge`.
- `src/pending-bulk-give.ts` — short-lived token storage for `/give-bulk`'s own two-step (pick items, then pick target) select-menu flow, mirroring `src/pending-links.ts`'s shape.
- `src/commands/group-lookup.ts` — `resolveOrCreateGroup`: "an existing group by exact name, or a fresh one with initial members" shared by `/add-to-group`/`/add-channel-to-group`.
- `src/lorenzo-client.ts` — a thin wrapper over a generated (`openapi-typescript`/`openapi-fetch`) typed client for `apps/api`. Regenerate with `mise run generate-client` after `apps/api`'s OpenAPI schema changes — CI's `client-drift` job (`mise run check-client`, which dumps a fresh schema and diffs the result) fails if you forget.
- `src/db-schema.ts`/`src/db.ts` — Drizzle ORM over the bot's own `loot_bot` Postgres schema (`linked_account`, `player_preference`, `loot_drop`, `loot_claim`, `pending_undo`) — entirely separate from `apps/api`'s own tenant-scoped, RLS'd tables. `player_preference` is keyed per `(discord_user_id, discord_channel_id)`; `loot_claim` carries a `claim_type` (need/greed) tier.

## Deployment

Google Cloud Run, same GCP project and CD pipeline as `apps/api` ([ADR 0011](../../docs/adr/0011-deploy-target-cloud-run-neon.md)). This needed a transport change first — a persistent Discord gateway connection doesn't fit Cloud Run's scale-to-zero model, so the bot receives interactions over Discord's HTTP Interactions Endpoint instead of the gateway; see [ADR 0053](../../docs/adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md) for why and how, and [`docs/operations/deployment-setup.md`](../../docs/operations/deployment-setup.md) for the one-time setup.
