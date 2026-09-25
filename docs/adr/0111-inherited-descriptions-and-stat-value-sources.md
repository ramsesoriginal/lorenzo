# 0111 - Showing inheritance: inherited descriptions and pictures, and where a stat value comes from

Status: accepted

## Context

[RFC 0001](../rfcs/0001-core-domain-data-model.md) lets an entity inherit from prototypes. Its example: "My Shovel" inherits from "Shovel" and "Cursed Item", "overrides some inherited values, and adds instance-specific information". Stats inherit through `v_effective_stat` ([ADR 0037](0037-effective-stat-resolution.md), [0039](0039-generic-effective-stat-view.md)). Information never did.

`ItemOut.descriptions` and `ItemOut.pictures`, which `ItemInstanceOut` inherits, list only the entity's own. So a description written on "Longsword", or on anything it inherits from, doesn't show on a longsword instance. That was reported while testing inventory-web.

Editing tags in inventory-web ([ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md)'s `PUT`/`PATCH`/`DELETE`) has a related gap. The three states are on, explicitly off, and inherited, but no read says whether a value is the entity's own or inherited.

## Decision

### Inherited descriptions and pictures accumulate

`ItemOut.descriptions` lists the entity's own visible descriptions first, as today. Then come those of every ancestor it reaches through `entity_prototype`, nearest first, by fewest hops. `ItemOut.pictures` does the same.

- **Ordering.** An ancestor reached by several paths counts once, at its shortest distance. Equally near ancestors are ordered by name, then id. The walk stops at 50 hops, `v_effective_stat`'s limit, so stats and descriptions reach the same ancestors.
- **Visibility.** Each ancestor's descriptions and pictures pass the same visibility check as the entity's own (`InformationVisibility.can_see` on the information they belong to). A GM-only note on a prototype stays GM-only on every instance.
- **Labels.** `DescriptionOut` and `PictureRefOut` gain `from_entity: EntitySummary | null`. It's `null` for the entity's own, and otherwise the ancestor the value comes from, so a client can show "from Longsword".
- **Accumulate, not override.** This was the maintainer's choice, following RFC 0001's "adds instance-specific information". It also handles several direct prototypes, where there's no single nearest one. An instance's own description adds to its item's rather than hiding it.

Only `ItemOut` and `ItemInstanceOut` change. `EntityDetailOut.information` stays the entity's own information, because that's what editing addresses.

`title` doesn't inherit either. An instance's displayed title is still its own description's title, else its own name ([ADR 0019](0019-item-and-v-item.md), [0067](0067-item-title-falls-back-to-name.md)). A new instance already copies its prototype's name.

Cost: each response makes one more recursive query for the ancestors of every item in it, and one load of their description and picture information. It doesn't grow with the number of items listed.

### Where a stat value comes from

`EntityStatValueOut`, in `EntityDetailOut.stats`, gains `own: bool`. It's true when the entity itself holds the winning value, stored or computed, and false when the value is inherited. A client editing a tag or stat can then show what `DELETE` would change: back to inherited, or nothing.

`ItemOut.tags` stays effective values only. It's a reader's view.

## Not in scope

- Inheriting other information, such as notes, rumours and handouts. They're about the entity they're written on, and knowledge is granted per row. Describing is the one kind a prototype does for its instances.
- Inherited display titles.
- Overriding an inherited description, or hiding one on an instance.
- Any change to `v_effective_stat`: `own` comes from the entity's own `entity_stat` and `computed_stat` rows.

## Consequences

- Every item reader sees prototype descriptions and pictures, labelled: inventory-web, and loot-bot's item views, which render `descriptions` and `pictures`. For loot-bot this adds text but no new behaviour.
- A long prototype chain adds its descriptions to every instance. What a GM writes on a broad prototype such as "Weapon" appears on every weapon.
- The response shape only grows: two nullable fields and one bool.
