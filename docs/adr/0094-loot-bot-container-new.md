# 0094 - loot-bot: `/container-new`

Status: accepted

## Context

[RFC 0021](../rfcs/0021-loot-bot-player-toolkit.md) slice 5b: bundle loose items into an ad-hoc container without leaving Discord, via a reusable per-tenant "sack" prototype. The RFC flagged one open question — *may a player create the prototype and an instance of it?* — to be settled against the API's real authorization rather than assumed. It came out worse than either answer the RFC expected:

- **Creating an instance is self-service.** `POST .../item-instances` with `owner_character_id` set to one of the caller's own characters needs no other standing (`_authorize_create_instance`, [ADR 0032](0032-item-and-item-instance-crud-api.md)). A player can make a sack.
- **But a player can't find the prototype to make it from.** The whole `/items` router sits behind `get_tenant_context`, which requires a tenant `Membership` — and ordinary players deliberately have none ([ADR 0050](0050-loot-bot-stack-linking-and-isolation.md)). So `GET /items` (even the read-only `?q=` search) and `POST /items` both answer a player with the same 404 a non-member gets for a tenant that doesn't exist ([ADR 0023](0023-authgear-token-verification.md)).
- There is no shared service token to fall back on: every call is made as the person who ran the command, and that rule is load-bearing for visibility, not incidental.
- `ItemOut` exposes `title` but not `name`; `title` equals the name unless someone authored a description title, and the server-side `q` filter matches on *name*.
- A fresh, empty container reports `is_container` as `null`, not `true` ([ADR 0066](0066-is-container-computed-field.md)), so it won't appear in `/move`'s container autocomplete until it holds something.

## Decision

### `/container-new name:<text> [character:<char>]`

Named `container-new`, not `container new` as the RFC wrote it: the interaction adapter has no subcommand support (its option reader is flat) and [ADR 0053](0053-loot-bot-http-interactions-and-cloud-run-deploy.md) deliberately keeps this bot's surface narrow; every existing multi-word command is hyphenated (`move-bulk`, `give-bulk`, `add-to-group`). Real subcommands would be transport work for one command's spelling.

Two steps:

1. **`execute`** resolves whose sack it is — the `character` option, else the stored default ([ADR 0068](0068-loot-bot-inventory-and-gm-toolkit.md)), else the only character the caller controls, else it asks (the same rule as [ADR 0090](0090-loot-bot-sheet.md)) — then makes the sack (an instance of the sack prototype, owned by that character, named as asked) and replies with a **multi-select of that character's loose items**: those in the API's "not in a container" group, minus the new sack. Up to Discord's 25 options; if there are more, it says how many aren't shown.
2. **`onSelectMenu`** moves exactly the picked items into the sack with `POST .../item-instances/bulk-move`'s explicit-list mode ([ADR 0065](0065-bulk-item-instance-container-move.md)) and reports per item — never all-or-nothing: `Put 2 items in.`, or `Put 1 item in. 2 couldn't be moved: <why>`.

The pick is **stateless**: the only thing it needs is which sack it fills, carried in the menu's `customId` (`container-new:fill:<sack id>`), the same convention as `/give`'s confirmation ([ADR 0088](0088-loot-bot-give-confirmation-and-last-used-character.md)) — a click can land on another Cloud Run instance. It acknowledges with `deferUpdate` and then edits the message (a select-menu `editReply` was added to the interaction type and adapter for this), because moving several items can outlast Discord's 3-second window. Unlike `/give`'s split, moving into the same container twice is harmless, so `deferUpdate` is enough and no double-click guard is needed.

### The sack prototype is found once, then stored

A new `loot_bot.container_prototype(tenant_id PK, prototype_entity_id)` table (migration `0004`) holds the catalog item's id per tenant. `resolveSackPrototype`:

1. **Stored?** Use it — no API call, works for any player.
2. **Otherwise** search the catalog (`?q=Sack`) as the caller, match a title of exactly "Sack" case-insensitively (a substring hit like "Sack cart" doesn't count), and create a plain "Sack" if none exists — then store the id.
3. **Caller can't reach the catalog** (404/403): report it, and `/container-new` tells them to ask a GM or admin to run the command once, or to add an item called "Sack" to the catalog.

So whoever *first* runs `/container-new` with catalog access sets it up for everyone; players never need it. That's the RFC's "lazily created on first use", adapted to who can actually do the creating. A stored id whose catalog item was later deleted surfaces as a 422 on instantiation; the bot forgets the stored id then, so the next run re-resolves instead of failing forever.

### An abandoned picker leaves an empty sack — accepted

The sack exists from step 1, so someone who never touches the picker is left with an empty sack in their inventory. This was chosen over the alternatives deliberately: holding the name and picks in bot-side state until a second step creates it would be state a click can lose across instances, and capping the command at five autocompleted `item1`…`item5` options would remove the multi-select. An empty sack is visible in `/inventory`, harmless, and can hold something later.

## Consequences

- One new table and migration; the deploy pipeline already runs `db:migrate` ([ADR 0053](0053-loot-bot-http-interactions-and-cloud-run-deploy.md)). Running `mise run register-commands` is needed for the new command.
- **A one-time human step**, made explicit rather than hidden: until someone with catalog access has run `/container-new` (or added a "Sack"), players get the ask-an-admin message. Nothing else is required of an admin.
- `createItemInstance` gains an optional `name`; new client methods `findItemsByName`, `createItem`, `bulkMoveItemInstances`. None changes `apps/api`.
- Not built: undo for the fill (a bulk move has no single-row inverse, and `/undo` holds one action), a `slug` option, updating the remembered character (`rememberActingCharacter` is on a separate open branch), nesting a *container* into the new sack beyond what the API already allows, and any way to delete an abandoned sack (`/confiscate` is GM-only).
- The sack prototype is matched by title, so a "Sack" someone gave an authored description title won't be recognised and a second plain one is created on first use. Rare, cosmetic, and self-limiting once the id is stored.
