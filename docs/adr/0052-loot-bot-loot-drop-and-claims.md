# 0052 - loot-bot: loot drop, take, claim/unclaim, apply claims

Status: accepted

## Context

The user's own scenario: a GM has already prepared a container item instance holding other item instances (how - out of scope, a separate tool). The GM tells the bot to drop it; the bot displays the contents; players can take a whole item or part of a stack immediately, or just *claim* one (a local, non-authoritative marker, purely so a party can talk out how to split something before anyone actually takes it) and *unclaim* it again; the GM can then "apply claims," turning every outstanding claim into a real transfer at once.

This is the first command in this bot needing more interaction surface than a plain slash command + autocomplete (`/give`, ADR 0051) - a drop needs to stay interactive across an open-ended stretch of real time while a party discusses loot, with several different users clicking on the same message.

## Decision

### Referencing the pre-made container: a raw UUID, not search

`/drop container:<uuid>` takes the entity id directly, however the GM's own separate loot-prep tooling produced it. No search/slug lookup was built for this - considered and explicitly declined (the user's own call): an item-instance search endpoint doesn't exist in the real API, and a slug would be a backend addition; a pasted UUID needs neither.

### New interaction surface: select menus + a modal, not one button per item

Discord caps a message at 5 action rows / 25 components total. One button per item per action (take, claim) blows past that for anything but a tiny drop. Instead, one message gets exactly three components:

- A **"Take an item"** string select menu (up to 25 options, one per item instance in the container - matches Discord's own per-select cap, which happens to be generous enough not to need pagination for a realistic drop).
- A **"Claim / unclaim an item"** string select menu, same option set.
- An **"Apply claims"** button, always present, gated at click time (not by disabling it for non-GMs - see below).

Picking an item from the **take** menu opens a modal (`ModalBuilder`/`TextInputBuilder`, `TextInputStyle.Short`, optional) asking for a quantity - blank means "the whole remaining stack." Submitting it performs the transfer immediately, exactly like `/give` (reusing the same split-vs-transfer decision, `commands/item-transfer.ts`, extracted from `/give`'s own logic rather than copied - `/give` and this modal-submit handler are now both thin callers of one `transferItem` helper).

Picking an item from the **claim** menu is a *toggle*, not always "claim": if the picking user already has an active claim on that item, it's removed (unclaim) with no modal; otherwise a modal (same shape as take's) asks for a quantity - blank means "however much is left when claims get applied," not "the current amount right now" (claims don't reserve anything, see below).

### `Command` gains generic component/modal dispatch

`commands/types.ts`'s `Command` gains three more optional handlers - `onSelectMenu`, `onButton`, `onModalSubmit` - alongside `execute`/`autocomplete`. Every `customId` this bot ever creates is namespaced `"<command-name>:<action>:<...ids>"` (e.g. `drop:take:<dropId>`, `drop:apply:<dropId>`, `drop:take-modal:<dropId>:<itemEntityId>`); `commands/index.ts`'s dispatcher extracts the part before the first `:` and routes to the command already registered under that same slash-command name, the identical `commandsByName` map `execute`/`autocomplete` already use. One dispatcher, one namespacing convention, not a parallel routing table.

### Claims are persisted, not in-memory

Unlike `/link`'s short-lived pending-state map (ADR 0050 - a lost in-flight attempt just means re-running `/link`), a loot-drop conversation can run for a real GM session's length. Losing every claim on a bot restart mid-session would be a visible regression, not a minor inconvenience. Two new `loot_bot` tables:

- `loot_drop`: `id` (uuid, pk), `container_entity_id`, `discord_channel_id`, `discord_message_id`, `created_by_discord_user_id`, `status` (`"open" | "applied"`), `created_at`.
- `loot_claim`: `loot_drop_id` (fk), `item_entity_id`, `discord_user_id`, `character_entity_id` (resolved once, from the claimant's `/set-current` preference, at claim time - not re-resolved when claims are later applied), `quantity` (nullable int - null means "whatever's left"), `created_at`. Primary key `(loot_drop_id, item_entity_id, discord_user_id)` - one active claim per user per item; claiming again updates it in place (the toggle above deletes it instead, for the same user+item).

### Take: immediate, real, re-validated against fresh state every time

Exactly `/give`'s own discipline, reused via `transferItem`: re-`GET` the item (capturing its `ETag`) immediately before deciding split-vs-whole, write with `If-Match`, map a `412` to a friendly retry message. Same known, documented gap as ADR 0051's amendment: owner/container writes don't bump `entity.updated_at`, so `If-Match` catches a race against an intervening rename but not against a second "take" on the same item - unresolved here too, not silently reintroduced as a surprise.

### Claim/unclaim: no API call, confirmed local-only

A `loot_claim` row is bot-local bookkeeping - it never touches `apps/api`. Claiming something does **not** reserve it: nothing stops another player from directly taking the same item while claims are still being discussed, exactly per the user's own description ("that's just local... a temporary client-side marker"). The drop message is edited after every claim/unclaim/take to show current state (`"Torch ×5 (3 left) - claimed by @Alice (2), @Bob (whatever's left)"`), but that display is a snapshot, not a lock.

### Apply claims: resolved one item at a time, oldest claim first, always against fresh state

The one piece of real design work this ADR adds beyond the original plan sketch - "apply claims one at a time" undersells a real correctness question: what happens when two people claimed the *same* item, or claimed more of a stack than actually remains?

For each item with at least one claim, its claims are processed **in `created_at` order** (oldest first - simple, predictable, matches "first dibs" without needing a UI for the party to rank their own claims). For each claim in that order:

1. Re-`GET` the item **right before this specific write** - not once per item, not cached across the loop. A prior claim's own apply (earlier in this same loop) may have just changed what's left; so may an unrelated direct "take" that happened seconds ago.
2. Not a stack (`quantity` is `null`): honor the claim only if the item is still unowned (or already owned by this same claimant - a harmless no-op); otherwise this claim failed ("already taken").
3. A stack: resolve the claim's requested amount (`quantity` field, or "whatever's left" - the item's current remaining quantity) against what's *actually* currently left. `0` or more-than-remaining fails ("not enough left"); otherwise it's `transferItem`'s ordinary split-vs-whole decision, same as a direct take.
4. Every claim's outcome (succeeded-whole, succeeded-partial, or failed-and-why) is collected, never thrown away mid-loop - one failed claim must not abort the rest.

After every claim is processed: `loot_drop.status` → `"applied"`, its `loot_claim` rows deleted, and the original message edited to a final summary (who got what, and which claims couldn't be honored) with its components removed - an applied drop no longer accepts new takes/claims through that message.

### GM authorization: a bot-side gate matching the backend's own permissiveness, not stricter

`/drop` and "Apply claims" both require the caller to hold at least one `CampaignGm` grant (`/me`'s `campaign_gm_grants`, already resolved elsewhere in this bot) - not scoped to *which* campaign, matching `apps/api`'s own accepted design (ADR 0032: an ownerless item's write falls back to `can_manage_campaign` on *any* campaign in the tenant). The bot's gate exists only to give a fast, friendly rejection instead of a raw 403; the real authorization boundary is still the backend's, unchanged and unbypassable by anything client-side.

### Container capability, and the drop's own scope

The dropped container's contents are read once, non-recursively (`GET /item-instances?container_id=&recursive=false`), matching how `/give`/`/set-current` already treat "what's in here" - deep-nested sub-containers inside the drop aren't flattened into the take/claim menus; a GM wanting a flat pile should prepare it flat.

## Consequences

- `commands/types.ts`/`commands/index.ts` gain generic component/modal dispatch, reusable by any future command with its own interactive message (not just `/drop`).
- `commands/item-transfer.ts` is a new shared module; `/give` is refactored to call it instead of inlining the split-vs-transfer decision a second time.
- Two new `loot_bot` tables (`loot_drop`, `loot_claim`), a new migration.
- Not built here: pagination past 25 items in one drop, ranking/prioritizing conflicting claims by anything other than claim order, or reserving an item the moment it's claimed - all explicitly out of scope, matching the user's own description of claiming as non-authoritative.

## Addendum: message refresh runs as the drop's own GM, not the acting player, and shows only what's still available

Two things surfaced only once the read side was actually implemented against ADR 0040's real, merged narrowing rule, not just reasoned about in the abstract:

**Rendering always re-fetches the container listing using the *drop's own creator's* access token** (`getValidAccessToken(drop.createdByDiscordUserId)`), never the token of whichever player happened to trigger the refresh (a take, a claim, an unclaim). ADR 0040 narrows an *owned* item instance's visibility to whoever can reach its owner - self, GM, or orga. Once Alice takes the torch, Bob's own read of the container would simply stop returning it, and if Bob's own token were used to rebuild the shared message, the torch would silently vanish from everyone's view rather than showing "taken." The GM's own read, via ADR 0035/0040's GM-reach (rooted at their campaign's character roster), retains visibility into anything now owned by a character in a campaign they GM - which covers every realistic take/claim target, since those characters come from the same campaign roster the drop's own GM-gate already assumes. Accepted, undocumented-until-now residual gap: a player taking with a character from a campaign the drop's own GM does *not* GM would fall outside even the GM's own reach - the transfer itself still succeeds (it's authorized independently), only this bot's own shared-message rendering for that specific item would degrade.

**A taken item disappears from the message entirely, rather than staying listed as struck-through history.** `availableDropItems` filters to `owner_entity_id === null` before building either the embed or the select menus - once an item (or the last unit of a stack) has an owner, it's gone from view, matching what "still up for grabs" needs to mean for the take/claim menus to stay accurate, at the cost of the message not doubling as a full running log of who got what mid-session (the final apply-claims summary is the actual record of outcomes, not the live message).

## Addendum: apply-claims moved to `bulk-assign`; `/drop`'s container accepts a slug

`apps/api` 0.4.0 closed two gaps this ADR's own plan had explicitly deferred:

- **`POST .../item-instances/bulk-assign`** (its own ADR 0044) replaces `applyAllClaims`'s old one-`GET`-and-one-write-per-claim loop with one read per *distinct* claimed item (not per claim - nothing mutates until the single batch call, so claims sharing an item share a snapshot) followed by one bulk call. Eligibility (already-taken, not-enough-left) is still decided entirely client-side, same as before, for a reason specific to this endpoint: `bulk-assign`'s own authorization has a documented gap (its ADR's own Context section) where reassigning an already-owned instance isn't blocked, so nothing server-side stops a *later* array entry from silently overwriting a same-batch *earlier* entry's claim on a non-stack item - `assignedThisRun`/`remainingByItem` (tracked client-side, in claim order) do the job the old per-claim re-fetch used to do implicitly. Array order still has to match claim order (oldest first) for this to hold, since the server processes same-`entity_id` entries within one batch sequentially, in array order, reproducing the same step-by-step result a loop of real writes would have.
- **`GET .../item-instances/by-slug/{slug}`** (ADR 0043) lets `/drop container:` accept a human-assigned slug instead of a raw entity id - resolved first whenever the input doesn't already look like a UUID. The originally-deferred "maybe a slug later" idea from this bot's own early design conversation is what this is.
