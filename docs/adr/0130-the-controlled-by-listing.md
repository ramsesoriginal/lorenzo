# 0130 - What a board shows: the controlled-by listing

Status: accepted

## Context

[RFC 0031](../rfcs/0031-equipped-carried-controlled-and-setting-things-down.md) §1–4 decided what a being's or a group's board shows, in terms of five words: Equipped, Carried, Personal, Owned, and Controlled. It's slice 1 of four: the API listing, with the board following in slice 2.

`held-by` ([ADR 0123](0123-held-by-listing-and-the-equipped-column.md)) can't simply change shape. It reads "an owned item in no container" as being with its owner, and loot-bot's `/inventory` and `/inspect` depend on that. It also walks from the holder alone, so it doesn't include what a character's groups own ([ADR 0124](0124-groups-own-things-and-moving-is-not-giving.md)).

## Decision

### `GET /tenants/{tenant_id}/item-instances/controlled-by/{entity_id}`

It lists the entity's board as columns. The entity may be a being, or anything else that owns things, such as a group. It isn't paginated, for the same reason `held-by` isn't.

**Access** is `held-by`'s. The caller must reach the entity (their own character or group, a GM's reachable set, or ORGA); otherwise the answer is `404`, the same as for an entity that doesn't exist.

**What it walks.** Everything reachable from the entity and from every group it's a member of: what they own, and everything contained under them or under what they own, at any depth (`entity_access.reachable_entity_ids`). Only item instances are listed. Other entities in the walk, such as a familiar in a backpack, only shape the tree.

**Controlled**, exactly as RFC 0031 §1–2 has it:

- *Personal*: owned by the entity itself. *Owned*: owned by the entity or by one of its groups.
- *Carried*, for a being only: everything contained under it, at any depth. A group, or any other holder that isn't a being, carries nothing.
- *Controlled* is:
  - everything Carried, except the direct contents of an item instance that isn't Owned and holds, at any depth, nothing Personal;
  - everything Owned;
  - the direct contents of every Owned item instance, except those of one that isn't Personal and holds, at any depth, nothing Owned.

Containment cycles ([ADR 0016](0016-containment.md)) are walked with every node visited once, so they can't loop.

It's computed in `lorenzo_api/controlled.py` as plain Python over what the walk loaded, with no queries of its own.

### Columns

Every Controlled item instance is in exactly one column, the one for where it is:

1. **`equipped`**, for a being only, always present, even when empty: what it contains directly. `container` is the being.
2. **`not_carried`**, always present, even when empty: what's in no container. `container` is `null`.
3. **`container`**, one for every Controlled item instance that is a container (`is_container`, [ADR 0066](0066-is-container-computed-field.md)) or has anything in it, so an empty backpack gets one.
4. **`read_only`**, one for every other entity that directly holds something Controlled: another being, an item instance that isn't Controlled, or a place. By the rules above, what lands there is always Owned.

Columns come in that order. Container columns come carried ones first, then the rest. Within each part, and among the read-only columns, they're in tree order, as `held-by` orders its groups: a container's outermost surroundings first, then its own name.

Each column carries:

- `kind`, and `container` (an `EntitySummary`, `null` for `not_carried`);
- `container_kind`: `being`, `item_instance`, or `other`, `null` for `not_carried`;
- `path`: the containers around the column's container, nearest first, **by containment alone**. It never goes through an owner the way `held-by`'s `surroundings` does. A carried column's path stops before the being.
- `carried`: whether the being is on that path. It's always `true` for `equipped` and always `false` for `not_carried`.
- `contents_hidden`: whether the column's container directly holds anything the column doesn't list, whether an item instance that isn't Controlled or another entity entirely. It's always `false` for `not_carried`.
- `item_instances`, in id order.

`owners` names every owner of a listed item once, by name, as in `held-by`.

### `visible_to_characters`

Each listed item is a `ControlledItemInstanceOut`: `ItemInstanceOut`'s fields plus `visible_to_characters`, whether the entity the listing is for knows the item is there. It's always `true` for now.

When knowledge ([ADR 0028](0028-knowledge-and-group-membership.md)) comes to back it, a caller who isn't a GM for the entity never gets an item with `false`, and such an item doesn't count towards `contents_hidden` for them. A GM gets it, with `false`. Nothing is filtered yet, because nothing can be `false` yet.

### Visibility

Controlled decides what's listed, not whether the caller reaches each item's owner ([ADR 0040](0040-item-instance-read-visibility.md)). A player sees what their character controls, including something of an NPC's that sits in their backpack. Hiding what a character doesn't know about is `visible_to_characters`' job. Descriptions and every other information-derived field still go through the caller's own information visibility, as on every item read.

## Not in scope

- inventory-web reading this listing: slice 2.
- Setting things down and splitting stacks (slice 3), and merging identical items (slice 4).
- loot-bot, and any change to `held-by`.

## Consequences

- A board has one listing that says what to show and where, groups' things included, and a client doesn't infer carrying from ownership.
- An empty container is somewhere to drop, as soon as it's marked `is_container`.
- The listing reaches further than ADR 0040's filter for the being's own board, deliberately, until `visible_to_characters` is backed by knowledge.
- `held-by` and `controlled-by` disagree about owned things in no container until loot-bot moves: `held-by` shows them as Equipped, `controlled-by` as not carried.
