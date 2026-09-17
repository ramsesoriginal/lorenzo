# 0068 - loot-bot: inventory hygiene, GM toolkit, claim tiers, per-channel preferences

Status: accepted

## Context

A round of feature requests aimed at two things: giving a GM more day-to-day tools beyond `/award`/`/drop` (inspecting a player, taking an item away, reassigning between characters, clearing a stuck drop's claims), and closing everyday inventory-management gaps (merging stacks, renaming an instance, searching a long inventory, undoing your own mistake, a need-vs-greed claim tier, a bulk give, per-channel current-character/container instead of one global default).

Investigated against the real, already-deployed `apps/api` surface before building anything: take-away (`DELETE /item-instances/{id}`), inspect (`GET .../owned-by/{id}`), GM reassign (`PUT .../owner`), merge (`POST .../merge`), rename (`PATCH .../item-instances/{id}`), bulk give (`POST .../bulk-assign`, already self-or-managed authorized), and "list my characters' groups" (`GET .../characters/{id}/groups`) all already exist server-side and are already permissive enough for every command below - none of this phase touches `apps/api`. Three separate, genuinely-missing API capabilities (an `is_container` flag, group-membership *writes* - ADR 0045 explicitly scoped those out, and a bulk container-move endpoint) were recorded separately in [ADR 0069](0069-item-instance-container-flag-group-writes-bulk-container-move.md) as accepted-but-deferred, owned outside this branch; nothing in this ADR's original scope depended on them - see this ADR's own Addendum for the follow-up once they landed.

Numbered 0064-0065 originally; renumbered to 0068-0069 on merge into `main` - `main` had independently claimed 0064-0067 for the apps/api additions this ADR's own Addendum consumes, in the meantime. Same renumbering precedent as ADR 0050/0054's own history (see [docs/adr/README.md](README.md)).

## Decision

### GM tools reuse the existing GM-authorization conventions, not new ones

`/inspect`, `/confiscate`, and `/reassign` all gate on `isCampaignGm` exactly like `/award`/`/drop` already do, and all source "which characters can this GM act on" from the same roster lookup `/award`'s own `findAwardTargets` already implemented - extracted verbatim into `commands/gm-roster.ts` (`findGmControlledCharacters`) so three commands share one implementation instead of three copies. `/confiscate` (destroy, `DELETE`, with an optional partial-stack `quantity` reusing the same split-then-remove shape `item-transfer.ts`'s `transferItem` already established for `/give`) and `/reassign` (structurally `/give.ts` with both ends widened from "the caller's own stuff" to "any character in a campaign I GM," reusing `transferItem` unchanged) are the two genuinely new writes; `/inspect` is read-only, reusing `format-inventory.ts`'s existing `formatInventoryEmbed` as-is.

### Drop claims gain a "clear" path and a need/greed tier

A GM could already "apply claims"; there was no way to discard a drop's outstanding claims without applying them (e.g. the party changed its mind, or a claim was made in error). A second button (`drop:clear:<dropId>`) reuses the existing `deleteLootClaimsForDrop` - today only ever called immediately after `markLootDropApplied` - called on its own instead, leaving the drop `status: "open"` with a clean slate.

Claims also gain a `claimType: "need" | "greed"` tier (a new `loot_claim` column, default `"greed"` for backward compatibility with any row inserted before this shipped). The claim flow gains one extra step (a Need/Greed button pair) between picking an item and the quantity modal. `applyAllClaims` now sorts each item's claims by `(need before greed, then oldest first)` instead of pure oldest-first - need claims always get first crack at a stack's remaining quantity or a non-stack's ownership, exactly mirroring how a table would resolve it by hand.

`/pending-claims` is new and deliberately **not** GM-gated - unlike every other new command here, seeing what's still outstanding on open drops is useful to the whole party, not just the GM (a long-running drop's own message can scroll out of view). It lists every currently-`"open"` drop (`db.ts`'s new `listOpenLootDrops`) with its outstanding claims.

### Inventory hygiene: reuse, don't reinvent

`/merge` and `/rename` are thin wrappers around endpoints that already exist and were simply never wrapped client-side (`mergeItemInstance`/`renameItemInstance`, new to `lorenzo-client.ts`). Merge's surviving stack keeps its own pre-existing container untouched - the request that "a merge has to end up in a container" is already satisfied by this, not a new mechanism worth building. `/inventory` gains an optional `search` option, filtering already-fetched results client-side by title substring - the same "no server-side search endpoint, so filter what we already listed" convention `/award`'s catalog autocomplete already established. `/give-bulk` is new (a multi-select-driven interaction, since Discord slash-command options can't repeat) but calls the existing `bulk-assign` endpoint exactly as `/drop`'s own apply-claims already does, just for a player's own items instead of claim resolution.

### Self-service undo is best-effort, not a general transaction log

A new `pending_undo` table holds exactly one row per Discord user (overwritten by each new undoable action, not a stack/history) - `give`, `move`, `merge`, and `rename` each record enough state to reverse themselves; `/undo` checks a short TTL, dispatches on the stored `actionType`, and clears the row either way. `/confiscate` is deliberately excluded: a destroyed instance's id is gone, so there is no real inverse, only "create a new one" - not honest to call that "undo." Merge's own "undo" is similarly approximate (a fresh split back out, not literally resurrecting the consumed instance's original id) and is documented as such rather than oversold.

### Preferences become per-Discord-channel, with a global fallback

`player_preference`'s primary key becomes `(discord_user_id, discord_channel_id)` - a player active in more than one channel (a "downtime" channel vs. the main table channel, for instance) can have a different current character/container in each, matching how these commands are actually used across a real server. A reserved empty-string channel id holds the "global default" row, consulted whenever no channel-specific preference exists yet - this is what `/link`'s new auto-set-on-single-character behavior writes to, since an OAuth callback has no Discord channel context at all to scope to.

## Consequences

- `commands/types.ts`'s `BaseInteraction` gains `channelId`, populated by `interaction-adapter.ts` for every interaction kind, not just chat-input - a small, mechanical widening (the raw Discord payload already carries `channel_id` on everything).
- Three tables gain columns/rows (`player_preference`'s new composite key, `loot_claim.claim_type`, the new `pending_undo` table) - one Drizzle migration.
- Not built here (see ADR 0069, and this ADR's own Addendum, instead): marking an item as a container, GM group-membership management, bulk container moves.

## Addendum: consuming ADR 0064/0065/0066 once they landed for real

The three capabilities [ADR 0069](0069-item-instance-container-flag-group-writes-bulk-container-move.md) deferred shipped on `main` while this branch was in flight, shaped somewhat differently than guessed there - regenerated `lorenzo-schema.d.ts` against the merged schema and built against the real thing rather than the speculative one.

**`is_container`** turned out to be a read-only computed field (ADR 0066), not a migrated, PATCH-able column - so "mark an item as a container" was never built; there's no clean write path for it from this bot (the underlying signal is a tenant-defined `tags`-group `stat_definition`, catalog-authoring territory, not a casual per-instance Discord toggle). Instead, `getMyItemInstances` now carries `isContainer`, and `/move`'s, `/set-current`'s, and the new `/move-bulk`'s own container options all narrow their autocomplete to `isContainer === true` - closing the exact gap `/move`'s own docstring used to name directly, just via the read side rather than a write command.

**Group-membership writes** (ADR 0064) landed far richer than the two-primitive sketch in ADR 0069: `POST /groups` accepts initial members in the same call as creation, plus rename/delete/duplicate that were never asked for here and aren't consumed. New `commands/group-lookup.ts`'s `resolveOrCreateGroup` (exact-name match against `listGroups`'s first page, else `createGroup` with members attached) is the one shared "create it, if not yet present" primitive both new commands need:

- `/add-to-group` - not GM-gated. The real authorization (`can_manage_character`: self, that character's GM, or orga/owner) already permits a player adding their own character, matching this bot's established "gate matches the backend's own permissiveness, not stricter" precedent (`/give`/`/move`/`/merge`/`/rename`) rather than an invented stricter rule.
- `/add-channel-to-group` - GM-gated, since sweeping in *other* players' characters only ever succeeds for someone with real standing over them. "Recently active in this channel" resolved as "posted a message here recently": `discord-rest.ts` gained its first bot-token-authenticated call, `getRecentChannelAuthorIds` (a plain REST read of channel message history - this bot has no Gateway connection, ADR 0053, but message history needs none). Each poster's own controlled characters are resolved using *their own* stored token (`token-provider.ts`'s `getValidAccessToken`, keyed by any Discord user id - the same trick `/drop`'s own message-refresh already uses for its drop's creator, `refreshDropMessage`); only the final group-membership write runs as the invoking GM's own token, keeping "every API call is made as the specific Discord user who [authorized] it" intact even though this command touches several users' data.

**Bulk container move** (ADR 0065) landed as `POST .../item-instances/bulk-move`, not `bulk-set-container` as guessed - a from-container-or-explicit-item-list choice, not a bare list. `/move-bulk` uses the from-container mode only (empty container A into container B) - no interactive multi-select needed, unlike `/give-bulk`, since the API itself resolves "everything in here" server-side; the explicit-list mode isn't consumed, nothing in this round needed it.
