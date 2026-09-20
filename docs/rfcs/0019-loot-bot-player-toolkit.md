# RFC: `apps/loot-bot` — a player toolkit round: notification DMs, safer `/give`, containers, sheets, and discoverability

Status: proposed

## Context

[ADR 0050](../adr/0050-loot-bot-stack-linking-and-isolation.md)–[0053](../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md) and [ADR 0068](../adr/0068-loot-bot-inventory-and-gm-toolkit.md) built the bot's account linking, `/give`, `/drop`, and a GM/inventory-hygiene toolkit. The bot now has 26 commands. Using it against real play surfaced ten gaps, none of which needs a new kind of thing in the domain — each is a better view over, or a safer path through, data `apps/api` already holds:

1. **Notifications never reach Discord.** `apps/api` fans notifications out per recipient (ADR 0058) and `apps/account-hub` shows them, but a player who lives in Discord finds out about an award only by opening a web app.
2. **`/give` is one step from irreversible-feeling.** `/undo` exists, but it is best-effort and time-limited (ADR 0068).
3. **No way to bundle loose items** into a container without leaving Discord.
4. **`/drop`'s `container` field is the one item-picking option with no autocomplete**, although `is_container` is already computed (ADR 0066) and every other container option (`/move`, `/set-current`, `/move-bulk`) narrows on it.
5. **A container prepared in `apps/inventory-web` has a slug** ([ADR 0043](../adr/0043-item-instance-slug.md)) that `/drop` accepts, but nothing in the bot ever shows one.
6. **No character sheet** — resolved stats and the lore a player is cleared to read are only reachable through the API/web.
7. **The bot makes players restate their character** on commands; `/set-current` (ADR 0068) is explicit-only.
8. **No player-facing "what happened to my stuff."**
9. **`/help` is a flat, 26-entry list** — accurate, but not a good first-run experience.
10. **`lorenzo-schema.d.ts` can go stale** against `apps/api`'s OpenAPI schema with nothing to catch it.

This RFC scopes all ten, orders them into independently shippable slices, and records the design decisions already agreed in conversation. Per [ADR 0070](../adr/0070-planning-milestones-issues-and-a-deferred-roadmap.md), each slice becomes an issue under one milestone; ADRs are written as each slice is built, not up front.

## Decision

### Slices, in build order — one PR each, not one branch for all ten

| # | Slice | Depends on |
| --- | --- | --- |
| 1 | CI check for generated-client drift | — |
| 2 | `/drop` container autocomplete + slug surfaced in replies with a copy affordance | — |
| 3 | `/give` confirmation step; last-used-character memory | — |
| 4 | First-run `/help`, grouped by task | — |
| 5 | `/sheet`; `/container new` | — |
| 6 | Notification → Discord DM bridge, with a fallback | Cloud Scheduler setup |
| 7 | `/changes` (bot-recorded only — see below) | — |

Order is smallest-and-least-risky first; slice 6 is the only one needing new infrastructure, so it goes late and can slip without blocking the rest.

### 1. Generated-client drift check

`mise run generate-client` reads `apps/api/openapi.json`, which is **gitignored** and produced on demand by `mise run //apps/api:openapi-schema` (correcting this RFC's original draft, which assumed it was committed). A CI job therefore dumps a fresh schema, regenerates `apps/loot-bot/src/lorenzo-schema.d.ts` from it, and fails on `git diff --exit-code` — the same class of gap `release.yml`'s `sync-lockfile` job exists to catch for `uv.lock`. Built as slice 1; on its first run it found the committed client already ~900 lines behind `apps/api`.

### 2. `/drop` autocomplete and slug surfacing

`/drop container:` gains an autocomplete handler narrowing to `isContainer === true`, identical in shape to `/move`'s. The typed-slug/UUID paths (ADR 0052's addendum) keep working — autocomplete is a convenience, not a replacement. Where a bot reply shows an item or container that has a `slug`, it also shows the slug in a way that can be copied in one tap (a Discord code span, plus a button only if a code span proves insufficient in practice — decided in the slice, not here). This closes the bot half of "prep a container in `apps/inventory-web`, then know its slug to drop it here."

### 3a. `/give` confirmation

A single Confirm/Cancel button pair between choosing the item/target/quantity and `transferItem` running, scoped to the invoking user, expiring with the interaction. One click, not a modal or a typed word. Applies to `/give` only in this slice; `/give-bulk` already has a multi-step flow and `/reassign`/`/confiscate` are GM tools where friction is a different tradeoff — not changed here.

### 3b. Remember which character you meant

`/set-current` (ADR 0068) already stores a per-channel current character with a global fallback. The new behavior is that a command which had to resolve a character *and succeeded with an explicitly-passed one* updates that preference to it — last-used wins — while an explicit option always overrides without needing `/set-current`. Scoped per server (one process = one guild, so this is the existing global-default row) with the per-channel row still taking precedence when present.

### 4. `/help` grouped by task

`/help`'s existing hand-maintained `CATEGORIES` (ADR 0068's addendum) is re-cut around what a player is trying to do ("See what I have", "Give or move things", "Drops and claims", "GM tools", "Account") and gains a short first-run intro at the top. No command is renamed — a 26-command rename would break muscle memory for what is a discoverability problem, not a naming one.

### 5a. `/sheet`

A character's resolved stats (the existing effective-stat resolution, [ADR 0037](../adr/0037-effective-stat-resolution.md)/[0039](../adr/0039-generic-effective-stat-view.md)) plus whatever information payloads the caller is cleared to see, as the calling user (ADR 0050's per-user-token rule — visibility is enforced by `information_visibility.py`, not filtered client-side). Ephemeral by default. Reuses `/inspect`'s and `format-item.ts`'s formatting conventions.

### 5b. `/container new`

Bundles loose items the caller owns into a new container without leaving Discord. It creates an item instance of a reusable, per-tenant "sack" prototype, then moves the chosen items into it with the existing `bulk-move` endpoint ([ADR 0065](../adr/0065-bulk-item-instance-container-move.md)). The sack prototype is created lazily on first use and found again by slug. **Open question, to be verified against `apps/api`'s item/item-instance write authorization at slice time, not assumed here:** whether a player (not just a GM) may create the prototype item and an instance of it. If only a GM may, the first `/container new` in a tenant needs a GM to have run it once (or a documented one-time setup), and players' later use of an existing sack prototype must be checked separately.

### 6. Notification → Discord DM bridge

Bridge each linked user's own unread Lorenzo notifications into Discord DMs. The bot already holds each user's own token, so this needs no `apps/api` change: `GET /me/notifications?unread_only=true` as that user.

**Transport: Cloud Scheduler, not `min-instances: 1`.** The bot scales to zero on Cloud Run ([ADR 0053](../adr/0053-loot-bot-http-interactions-and-cloud-run-deploy.md)); an in-process poll loop would only run while a request happened to keep an instance warm. A Cloud Scheduler job calls a new authenticated bot endpoint on a fixed interval, keeping ADR 0053's scale-to-zero, $0-at-idle property. The endpoint authenticates the scheduler (OIDC token from a dedicated service account, verified against Cloud Run's own identity — never an unauthenticated route, since it triggers outbound DMs). Adds one-time GCP setup to `docs/operations/deployment-setup.md`.

**Bot-side cursor, not `/read`.** Marking a notification read via the API would empty it out of `apps/account-hub`'s inbox behind the user's back. The bot instead tracks per-user "delivered" state in its own `loot_bot` schema (a new table keyed by `(discord_user_id, notification_id)`, or a high-water `created_at` — decided in the slice's ADR) and treats API-side `read_at` only as "no need to DM this anymore."

**Fallback when DMs are closed — the part that matters.** Creating a DM channel or sending to it can fail (Discord error 50007, "Cannot send messages to this user"). A failed delivery is never dropped: the notification is kept in a `pending_notice` queue (again, the bot's own table), and on that user's **next command of any kind**, the bot prepends an ephemeral banner — marked "couldn't DM you" — listing what was missed, then clears it once shown. The result is "found out, just not by DM," instead of "missed an award silently." Not built in this slice, deliberately: a channel-post fallback, retry-with-backoff beyond the next scheduler tick, or per-user opt-out of DMs — each an easy follow-up once the base path is real.

**Scoping questions to settle in the slice's ADR, not here:**
- One bot process serves one tenant, but `GET /me/notifications` spans every scope and tenant the user has rows in. Default proposal: DM only notifications whose `tenant_id` is the bot's own tenant, plus platform-scope (null `tenant_id`) ones.
- Message shape and length (notification `title`/`body` vs. Discord's message limits) and how batches sharing a `batch_id` are grouped.

### 7. `/changes` — bot-recorded only, for now

A player-facing "what happened to my own stuff since I last looked," distinct from the GM's tenant-wide activity log ([ADR 0063](../adr/0063-tenant-activity-log.md), tenant-admin-only, and deliberately limited to seven mutation points — none of which are gives, moves, or awards). `apps/api` has no per-player change feed, so this slice can only report what the bot itself already records: gives and moves the player made or received through the bot, drop takes and claim outcomes, and undo history (`pending_undo`, `loot_drop`, `loot_claim`), plus a per-user "last looked" marker. This is an honest, visibly partial view — anything done through `apps/inventory-web` or the API directly will not appear — and `/changes` says so. The complete version is [RFC 0020](0020-player-facing-change-feed-api.md); this slice deliberately builds nothing the API RFC would have to unpick.

## Alternatives considered

- **Keep the Gateway connection for DMs/notifications, on `min-instances: 1`.** Rejected for the same reason ADR 0053 rejected it: it forfeits scale-to-zero for a benefit Cloud Scheduler delivers at no idle cost.
- **Mark notifications read from the bot.** Rejected: it would silently drain the user's `apps/account-hub` inbox.
- **Open a channel/DM-less fallback (post in a shared channel) first.** Rejected as the default: it leaks a private notification to the channel. Kept as a possible opt-in follow-up only.
- **One big branch for all ten.** Rejected in conversation: slices 1–5 are independent and small; slice 6 needs infrastructure and shouldn't hold them back.

## Consequences

- One milestone with an issue per slice (created alongside this RFC, per ADR 0070); this RFC's slices, not this text, are the live status.
- Slice 6 adds one-time GCP setup (a Cloud Scheduler job, a service account, an invoker binding) and new `loot_bot` tables; slices 3b/7 also touch the bot's own schema.
- No `apps/api` change is required by any slice. The one place that would benefit from one — `/changes` — has its own RFC.

## Not in scope

- Renaming or restructuring existing commands.
- A channel-post, email, or push fallback; DM opt-out; DM delivery for notification scopes outside the bot's tenant.
- Any change to `apps/api` (see RFC 0020 for the one deliberately deferred).
