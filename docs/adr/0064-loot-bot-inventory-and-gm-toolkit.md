# 0064 - loot-bot: inventory hygiene, GM toolkit, claim tiers, per-channel preferences

Status: accepted

## Context

A round of feature requests aimed at two things: giving a GM more day-to-day tools beyond `/award`/`/drop` (inspecting a player, taking an item away, reassigning between characters, clearing a stuck drop's claims), and closing everyday inventory-management gaps (merging stacks, renaming an instance, searching a long inventory, undoing your own mistake, a need-vs-greed claim tier, a bulk give, per-channel current-character/container instead of one global default).

Investigated against the real, already-deployed `apps/api` surface before building anything: take-away (`DELETE /item-instances/{id}`), inspect (`GET .../owned-by/{id}`), GM reassign (`PUT .../owner`), merge (`POST .../merge`), rename (`PATCH .../item-instances/{id}`), bulk give (`POST .../bulk-assign`, already self-or-managed authorized), and "list my characters' groups" (`GET .../characters/{id}/groups`) all already exist server-side and are already permissive enough for every command below - none of this phase touches `apps/api`. Three separate, genuinely-missing API capabilities (an `is_container` flag, group-membership *writes* - ADR 0045 explicitly scoped those out, and a bulk container-move endpoint) are recorded separately in [ADR 0065](0065-item-instance-container-flag-group-writes-bulk-container-move.md) as accepted-but-deferred, owned outside this branch; nothing in this ADR depends on them.

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
- Not built here (see ADR 0065 instead): marking an item as a container, GM group-membership management, bulk container moves.
