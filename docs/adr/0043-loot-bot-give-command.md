# 0043 - loot-bot: `/give`, the first write command (loot-splitting)

Status: accepted

## Context

[ADR 0042](0042-loot-bot-stack-linking-and-isolation.md) scoped `loot-bot`'s first slice to read-only (`/link`, `/inventory`). [docs/domain/client-views.md](../domain/client-views.md)'s own worked example names "mechanical tasks like splitting loot among a party" as the bot's actual reason for existing — this ADR is that slice, now that `apps/api`'s write API is real and confirmed (`feat/rest-api-surface`, 93 operations including a dedicated `POST .../item-instances/{id}/split`, ADR 0041 there).

RFC 0005's own "Not in scope" section (that branch) is explicit that bulk/orchestrated operations like this are a client-side concern: "a client-side loop over the single-item endpoints... not a new REST primitive." This ADR is that orchestration, client-side.

## Decision

### One command, `/give`, not separate `/give` and `/split`

A player thinks "give Sam 5 torches," not "split off 5 torches, then transfer the split's ownership" — two backend calls, one user intent. `/give item:<autocomplete> to:<autocomplete> [quantity:<int>]`:

- No `quantity`, or `quantity >= ` the item's current stack size → the *whole* instance's ownership transfers directly (`PUT .../item-instances/{id}/owner`) — no split. Matches the split endpoint's own documented invariant ("splitting off 'all of it' is a container/owner reassignment of the whole stack, not a split").
- `quantity` less than the current stack size → `POST .../item-instances/{id}/split` (quantity split off into a new sibling instance, same owner/container as the source, per that endpoint's own contract) followed by `PUT .../owner` on the *new* instance, transferring only the split-off portion.
- `quantity` given against a non-stacked item (`quantity` field `null`, i.e. "just one") is rejected client-side with a clear message before calling anything, rather than letting a confusing 422 surface from the backend.

### Item and target selection: Discord autocomplete, not raw UUIDs

Nobody types a UUID into Discord. Both `item` and `to` are autocompleted string options whose `value` is the entity id and whose displayed `name` is human-readable:

- **`item`**: the caller's own inventory — `getMyPlayers()` (new client call, wraps `GET /me`'s `players[]` without discarding `campaign_id` the way `getControlledCharacters` does) resolves every character the caller controls, then `getItemInstancesOwnedBy` per character (already used by `/inventory`) supplies the candidates. Filtered by the text typed so far, capped at Discord's own 25-choice autocomplete limit.
- **`to`**: characters in the *same campaign* as the item chosen for `item` — resolved via the new `getCampaignPlayers()` (`GET .../campaigns/{campaign_id}/players`), which only an actual participant of that campaign (a player, its GM, or a tenant admin) can call, matching who's meant to be pickable here anyway. If `item` hasn't been typed yet when `to` is focused (Discord doesn't guarantee fill order), falls back to every character across every campaign the caller has a `Player` row in — a superset, not a security boundary; the real write call re-validates regardless (see below).

Autocomplete is a UX convenience only, never authoritative — every actual `execute()` call still goes through the real API's own self-or-managed authorization. A stale or manipulated autocomplete `value` just gets the same 403/404 an invalid id would.

### No optimistic concurrency (`If-Match`) in this slice

The real API supports it (`RFC 0005`'s own optional `If-Match`/ETag convention) but it's deliberately not wired up here yet - this bot is low-traffic/personal-scale (matching this whole project's own stated posture, ADR 0011/0027), and a lost-update race on a loot-split is a minor, easily-repeated mistake, not data loss. `execute()` still re-fetches the item fresh (`GET .../item-instances/{id}`) immediately before deciding split-vs-transfer, so the *quantity* decision is based on current state even without a concurrency guard on the write itself. Revisit if this turns out to matter in practice, not preemptively.

### The item's container is left untouched

`PUT .../owner` only ever touches ownership; this command doesn't also call `.../container` to move the item out of the giver's backpack. The domain model already treats ownership and physical containment as independent facts (an owned item can sit in someone else's container) - not touching it is the smaller, more literal application of the primitives the backend exposes, not a new interpretive layer on top. A future `/give` revision could add "also uncontain it" as an explicit opt-in if this turns out to read as surprising in practice - not assumed here.

### Errors surfaced distinctly, not generically

Reusing `LorenzoApiError`'s `status`: `403` ("that's not something you can give away" - the source isn't reachable from the caller's own characters), `404` (item or target doesn't exist or isn't visible to the caller - same non-enumerable convention every other route already uses), `422` (e.g. asking to split more than the stack currently holds - a real race between autocomplete and submission, or just a stale number). Anything else falls through to `commands/index.ts`'s existing generic failure handler, unchanged.

## Consequences

- `commands/types.ts`'s `Command` gains an optional `autocomplete` handler alongside `execute`; `commands/index.ts`'s dispatcher gains an `interaction.isAutocomplete()` branch. Every other existing command is unaffected (the field is optional).
- `lorenzo-client.ts` gains `getMyPlayers`, `getItemInstance`, `splitItemInstance`, `setItemInstanceOwner`, `getCampaignPlayers` - all straightforward wrappers over already-real endpoints, no provisional/guessed shapes this time.
- Not built here: a standalone `/split` (keep-both-halves-yourself) command, `/take` (the inverse of `/give`, pulling an item to yourself), or any container-transfer command - none were asked for; `/give` covers the loot-splitting use case this bot exists for.
