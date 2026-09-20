# 0093 - loot-bot: `/drop` container autocomplete and slug surfacing

Status: accepted

Numbered 0087 originally; renumbered to 0093 on merge into `main`, which had independently claimed 0087 for account-hub's own pictures ADR in the meantime (0084-0092 were by then all taken across other open branches, so the next free number was used). Same renumbering precedent as ADR 0050/0054's own history (see [docs/adr/README.md](README.md)).

## Context

[RFC 0021](../rfcs/0021-loot-bot-player-toolkit.md) slice 2. [ADR 0052](0052-loot-bot-loot-drop-and-claims.md)'s addendum let `/drop container:` take a slug ([ADR 0043](0043-item-instance-slug.md)) instead of a raw entity id, but two gaps remained: `container` was the one item-picking option with no autocomplete, and nothing in the bot ever *showed* a slug, so a GM who prepared a container in `apps/inventory-web` still had to already know its slug to drop it.

The obvious autocomplete source doesn't work. Every other container option (`/move`, `/set-current`, `/move-bulk`) narrows `getMyItemInstances` — what the caller's own characters *own* — to `isContainer === true` ([ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)). A GM's pre-made loot pile is typically **ownerless**, so that list can never contain it: the one container `/drop` exists for would be exactly the one missing from its own suggestions.

## Decision

### `/drop container:` autocompletes from unowned containers plus the caller's own

- Sources: `GET .../item-instances/unowned` (added to `apps/api` for GMs browsing unclaimed loot, and unpaginated like `owned-by`) plus `getMyItemInstances`, narrowed to `isContainer === true` and de-duplicated by entity id. Ownerless instances are visible to any tenant participant already ([ADR 0040](0040-item-instance-read-visibility.md)), so the bot adds no GM gate to the *suggestions*; `/drop`'s own `isCampaignGm` gate in `execute` is unchanged, and remains a friendly-rejection layer over the API's real authorization, as in ADR 0052.
- Still only a suggestion. The typed id and slug paths keep working for anything not listed — notably a container someone else owns, or a still-empty one, since `is_container` is `null` (not `true`) until something is inside it ([ADR 0066](0066-is-container-computed-field.md)).
- Both reads run in parallel; a failure in either surfaces through `dispatchInteraction`'s existing autocomplete error handling, same as `/move`.

### Slugs are shown where they help, in the form that suits the surface

- **Autocomplete choice names** append the slug in brackets (`Goblin hoard [goblin-hoard]`), so two same-titled containers are distinguishable, what the GM types matches against the slug too, and the slug is learned in passing. Choice names are capped at Discord's 100 characters; the *title* is truncated, never the slug.
- **`/inventory` and `/inspect`** (one shared formatter) add the slug as an inline code span, only for instances that have one — most don't, and their lines are unchanged.
- **`/item`** adds a "Slug" field holding a fenced code block. Discord renders a copy button on fenced blocks, and one item has room for the field; that is the "one-tap copy" the RFC asked for, without inventing a button. The field reserves its own slot against Discord's 25-field cap so a note-heavy item can't push it out.
- `EntityDetailOut` carries no slug — it lives on the item *instance* — so `/item` looks it up with `getItemInstance`, in parallel with the entity read. That lookup is a convenience and never allowed to fail the command: a 404 (the entity isn't an item instance — an NPC's gear list, a place) is silently "no slug", and any other API error is logged at `warn` and treated the same.

### `OwnedItem` gains `slug`

`getMyItemInstances` and the new `getUnownedItemInstances` share one `toOwnedItem` mapper, so `slug` (and `isContainer`) can't drift between the two.

## Consequences

- One extra API read per `/item` call (parallel, so no added latency in the common case), and two per `/drop` autocomplete keystroke. Autocomplete's 3-second window is the constraint to watch; both are single unpaginated reads.
- The `unowned` endpoint only exists in the regenerated client, which is why this slice builds on the client-drift check's regeneration (slice 1) rather than hand-editing a generated file.
- Not built: a slug in `/award`/`/move`/`/reassign` replies, or a slug on container *group headings* in `/inventory` (the API's `container` summary carries only `id` and `name`) — neither was asked for, and the latter would need an `apps/api` change.
- A one-time, cosmetic wrinkle worth knowing: a code span in an inline list isn't a copy button on every Discord client. It reads as "this is the copyable thing" and is trivially selectable; `/item`'s fenced block is the real one-tap copy.
