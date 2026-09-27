# 0123 - What a being holds: the held-by listing, and an Equipped column that's always there

Status: accepted

## Context

[RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) §1–3 decided that a being is its own Equipped container, and that a being's board should show everything it *holds*: [ADR 0099](0099-player-facing-change-feed.md)'s relation, meaning what it owns, what's contained under it at any depth, and whatever sits inside something it owns.

Both clients show ownership instead. inventory-web's board and loot-bot's `/inventory` and `/inspect` read `GET .../item-instances/owned-by/{id}` ([ADR 0020](0020-rest-api-tenant-scoping-and-schemas.md)). So:

- a character carrying someone else's sword never sees it on their own board;
- Pia's spellbook, lent to Brisk, shows on Pia's board in a column named after Brisk's backpack, with nothing saying whose backpack that is;
- the character's own column only appears when something is loose, so there's nothing to drop onto when it's empty.

[ADR 0115](0115-hand-over-on-give-and-stacks-leave-containers-into-their-owner.md) left "in no container" with two representations: an item contained directly by its owner, and an item with no containment row at all (a single item, never backfilled). `owned-by` hides the difference by listing both with the loose things.

## Decision

### `GET /tenants/{tenant_id}/item-instances/held-by/{entity_id}`

It lists every item instance the entity holds: `entity_access.reachable_entity_ids` from that one entity, the same walk ADR 0099's `holders` inverts. It is not paginated, like `owned-by`: it's bounded by what one being holds.

- **The holder's own group comes first, always**, even when it's empty. For a being, that group is its Equipped container. It holds what the being contains directly, plus what the being owns that has no containment row at all. ADR 0115 already treated the two as the same, and this ADR makes that equivalence explicit: an owned item in no container is with its owner. Later slices read it the same way, so "carried" means contained under a being, or owned by it with no container at all.
- **Then one group per other occupied container**, carried ones first. A container with nothing visible inside gets no group of its own, as with `owned-by`; it's still a card in its parent's group.
- **Each group says where it is.**
  - `container`: its summary.
  - `container_kind`: `being`, `item_instance`, or `other`.
  - `path`: the containers around it, nearest first. Where a chain ends at something in no container that has an owner, it goes on through that owner, by the same equivalence: a backpack Pia owns with no containment row is with Pia. For a carried group it stops at the holder; for anything else it goes up to the top.
  - `carried`: whether the holder is on that path.
- **The response names every owner** once, in `owners`, so a client can say whose each item is from its `owner_entity_id` without a second request. Items keep `ItemInstanceOut`'s shape unchanged.
- **Visibility follows `owned-by`** ([ADR 0040](0040-item-instance-read-visibility.md)): an owned item appears only if the caller can reach its owner. The holder itself has to be one the caller can reach (their own character, a GM's reachable set, or ORGA); otherwise the answer is `404`, the same as for an entity that doesn't exist. `owned-by` answers an unreachable owner with an empty list instead, but an always-present group has to name its holder, and a `404` doesn't.

A group as holder works through the same walk, but members only reach what a group owns once slice 2 extends reachability ([RFC 0030](../rfcs/0030-carrying-holding-binding-and-capacity.md) §4).

`owned-by` stays as it is. Every loot-bot command that acts on your own things still uses it.

### inventory-web's board

A character's board, and a GM's board for any being, reads held-by:

- **Equipped** is the first column, always, labelled "Equipped" and always a drop target. Dropping onto it puts the item into the being, as dropping onto the character's own column did (ADR 0115). An empty board is an empty Equipped column, not an empty-board message.
- **Carried containers** follow, each a column named after the container, with "in the Backpack" under a nested one.
- **Held elsewhere** comes last, under its own heading. Each container says where it is ("in the Carriage") or who has it ("Brisk has it", for a being).
- **Whose it is.** A card whose owner isn't the board's being names its owner ("Pia's"), or says "No one's" for an unowned item.

The board of unowned items keeps reading `GET .../unowned`.

### loot-bot

`/inventory` and `/inspect` read held-by, in the same order:

- **Equipped** first, with "Nothing equipped." when it's empty;
- then carried containers, a nested one named with where it is ("Belt pouch, in the Backpack");
- then what's held elsewhere.

An item that isn't the character's own ends with its owner's name. Commands that act on your own items keep reading `owned-by`.

## Not in scope

- Letting group members reach what a group owns, and groups on the board: slice 2.
- Changing who may move or give what's on the board: slice 2. A card for someone else's item gets its owner mark now, and its actions are whatever the API already allows.
- Backfilling containment rows for owned items in no container. They're read as with their owner instead.

## Consequences

- A character's board shows what they actually have to hand, including what they carry for others and what's theirs but kept elsewhere, and says whose each thing is.
- Equipped is always somewhere to drop.
- "In no container" now means one thing everywhere (with its owner), whichever of its two representations an item has.
- `404` for a holder the caller can't reach differs from `owned-by`'s empty answer, and is deliberate: held-by always names its holder.
