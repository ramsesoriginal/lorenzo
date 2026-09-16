# 0041 - Quantity and stacking, on `Containment`

Status: accepted

## Context

A black-box completeness review of everything built through [ADR 0040](0040-item-instance-read-visibility.md) surfaced a real, concrete gap: there is no way to represent "50 arrows" or "20 identical townsfolk" as anything other than 50 (or 20) separately-created entities. Every entity is individually addressable - its own id, its own prototype links, its own stats, its own information - which is exactly right for anything that matters individually, and needlessly heavy for anything that doesn't. A usable inventory manager or loot-splitter needs stacks; the domain model had no concept of one.

Two designs were considered: attaching a `quantity` to `Containment` (the generic `child_entity_id`/`parent_entity_id`/`tenant_id` physical-containment relation, [ADR 0016](0016-containment.md)), or attaching it to `item_instance` specifically. Resolved via a structured debate (two independent cases built for each side, then a third pass fact-checking both and weighing the actual trade-off) rather than by first instinct - first instinct wrongly dismissed the `Containment` option over concerns (an uncontained item having nowhere to put a count, the `child_entity_id` primary key somehow being at risk, splitting being harder one way than the other) that turned out not to hold up under scrutiny.

Currency/economy (a merchant being able to charge for stacked goods) is explicitly out of scope here - tabled as its own future topic, not resolved or half-resolved by this ADR.

## Decision

### `quantity` lives on `Containment`, not on `item_instance`

`containment.quantity: int NOT NULL DEFAULT 1`, `CHECK (quantity >= 1)`. This is the one point the two designs didn't actually differ on technically (stat resolution and the authorization reachability walk are unaffected either way, and the `child_entity_id` primary key is untouched by an ordinary non-key column either way) - the deciding factor was genericity. An arrow-stack, a crowd of townsfolk, and a shelf of identical books are *the same mechanism* under this design: one `Containment` row, one column, no decision required about "is this an item." Putting `quantity` on `item_instance` instead would cover items only - a GM's "20 goblins in this room" (a `Being`, not an `Item`) would need a second, parallel column on a second table, forking how "a stackable thing" is represented depending on what kind of entity it happens to be. That fork is exactly what [RFC 0001](../rfcs/0001-core-domain-data-model.md)'s entity/component design has consistently avoided elsewhere in this codebase.

`DEFAULT 1`, not nullable: Postgres (11+, this project runs `postgres:17-alpine`) doesn't rewrite a table to add a column with a constant default, so this is exactly as cheap as a nullable column to add - the usual reason to prefer nullable-with-implied-default doesn't apply here. `NOT NULL DEFAULT 1` also means every ordinary, non-stacked containment link ("this sword is in that chest") is trivially and correctly "a stack of one," not a special case a query has to `COALESCE` around - `SUM(quantity)` across a container's contents is correct immediately, mixing genuine stacks and plain single items in one query. Matches this codebase's own existing precedent for this shape of column: `stat_group.priority` ([ADR 0014](0014-stats.md)) defaults rather than being nullable.

### Resolved stats are per-unit, by convention, not by schema

A stat resolved through `v_effective_stat` ([ADR 0039](0039-generic-effective-stat-view.md)) - `weight`, `price`, whatever - describes *one* member of the stack, never the aggregate. A client wanting a stack's total weight computes `weight * quantity` itself; this ADR does not add an API-computed total. Per-unit is the only convention that survives a split or merge without recomputation - a stored total would need to be kept in sync on every quantity change, a per-unit value never does.

### The residual gap: a stack still needs *something* to be contained by

`quantity` only exists on `Containment`, so an item with no containment row at all (owned, but not placed anywhere) has no stack count at all - it's just "one, unremarkable" by the absence of a row, the same as today. This is a real, accepted gap, not solved by schema: the expected modeling convention going forward is that a stackable entity is always contained by *something*, even a structural bucket (e.g. a per-character "Equipped" or "Carried" entity) rather than truly floating. Not enforced by a constraint - genuinely uncontained entities remain valid, they just can't carry a stack count while in that state.

### Read surface: exposed everywhere a containment relationship already is

- `v_item`/`v_item_instance` (and therefore `ItemOut`/`ItemInstanceOut`) gain a `quantity: int | None` column, sourced from the same `LEFT JOIN containment` already producing `container_entity_id` - `NULL` exactly when `container_entity_id` is `NULL` (uncontained), otherwise the containment row's own `quantity` (always ≥ 1).
- `EntityDetailOut` gains a top-level `quantity: int | None`, symmetric with its existing `parent: EntitySummary | None` field and sourced from the same `entity.containment` relationship - "how many of *this* entity are in its own current container," null exactly when `parent` is null.
- `EntityDetailOut.children` - each entry needs its *own* quantity within this entity (a caller listing a room's contents needs to know "20" without fetching that child individually) - `EntitySummary` gains an optional `quantity: int | None = None`, populated for `children` entries (sourced from `entity.contained_links`, the `Containment` association-object relationship, not the bare `entity.children` convenience list, which loses the per-edge column entirely) and left unset for its other existing uses (`prototypes`, `instances`, `stat_groups`, `parent`), which aren't about a specific containment edge's count.

This is what actually makes the "20 townsfolk" case real rather than theoretical: nothing about it needs `item`/`item_instance` at all, it's visible through `GET /entities/{id}` the same way any other entity is.

### Write surface: a `split` operation, scoped to item instances only

`POST /tenants/{tenant_id}/item-instances/{entity_id}/split` (`SplitItemInstanceRequest{quantity}`) - splits `quantity` units off the source's current stack into a new instance. Self-or-managed authorization against the *source* entity ([RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md)'s existing `_authorize_instance_write`) - splitting your own stack is acting on your own stuff, same as any other instance write.

Effect, one transaction: a new `Entity` + `ItemInstance`, copying the source's own direct `EntityPrototype` link(s) (not its direct `entity_stat` overrides, its `Information`/knowledge grants, or its attribution trail - a split-off unit is a fresh instance of the same prototype, exactly like `POST /item-instances` already creates one, not a deep clone of the source's own accumulated state); the new instance's `Ownership` matches the source's current owner, if any; a new `Containment` row for it at the *same* parent as the source, `quantity` set to the requested amount; the source's own `Containment.quantity` decremented by that amount.

Validation: the source must currently have a `Containment` row (a truly uncontained item has no stored count to split from) with `quantity` strictly greater than the requested split amount (`422 InvalidSplitQuantityError` otherwise) - splitting off "all of it" is just reassigning/moving the whole stack via the existing owner/container endpoints, not a new-entity-producing operation. `201` + `Location` + the new instance's `ItemInstanceOut`, mirroring `POST /item-instances`'s own convention.

Moving a whole stack is unchanged - the existing `PUT`/`DELETE .../container` still moves the `Containment` row as one unit, `quantity` riding along untouched, zero new code.

## Not in scope

Currency/economy (tabled per Context). A `merge` endpoint (the reverse of split, summing two same-prototype stacks under one parent back together) - a genuine convenience, not required for correctness, since a caller can already reassign ownership/delete manually; not built without a concrete need for it yet. `split` (or any write support for stacking) on non-item entities - a GM splitting one named NPC out of a crowd-of-20 `Being` is exactly the kind of case this schema is generic enough to eventually support, but it isn't asked for yet and isn't built here; only the *read* side (`EntityDetailOut`) is generic today, the *write* side is item-instance-only, a real, deliberate asymmetry. Automatic merging of two stacks that happen to land in the same container - explicit only, matching this codebase's general preference for explicit operations over implicit ones. Representing a partial exception within a stack (e.g. "3 of these 20 arrows are cursed") - still requires splitting those 3 out first, same as it would under either design considered in Context; not a gap this ADR introduces or could remove.

## Consequences

- One migration: adds `containment.quantity` (`NOT NULL DEFAULT 1`, `CHECK (quantity >= 1)`) and updates `v_item`/`v_item_instance`'s `CREATE VIEW` SQL to select it alongside `container_entity_id` - purely additive, no backfill, every existing row already satisfies the new default and constraint.
- `Entity.children` (the bare, viewonly `secondary="containment"` convenience list) is no longer what backs `EntityDetailOut.children` - `entity.contained_links` (the `Containment` association-object list, already existing, [ADR 0018](0018-sqlalchemy-modeling-conventions.md)'s modeling precedent) is, since only it carries the per-edge `quantity` column. `Entity.children` itself is unaffected and unremoved - still valid for any caller that only wants "what's in here," not "how much of it."
- New typed problem: `InvalidSplitQuantityError` (422).
- A tenant admin/GM/worldbuilder can now populate a room, a shop, or a container with an arbitrary count in one call instead of one-per-unit - the concrete usability gap the original bird's-eye review named is closed for the item/inventory case, and made *representable* (read-only, for now) for the general entity case.
