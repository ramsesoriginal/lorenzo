# RFC: Effective stat resolution over the prototype graph

Status: proposed — deliberately short; now covers stat *writing* as an equally unfinished part, not just resolution; expand both together, in a second pass, once actually picked up

## Context

[RFC 0001](0001-core-domain-data-model.md) already decided the resolution *rule* in full: "more specific wins — a value defined closer to the entity... beats one defined further out, and an instance-level override always beats anything inherited... the tie breaks on `stat_group.priority`." [ADR 0015](../adr/0015-entity-prototype.md) built the graph this walks (`entity_prototype`, cycle-rejecting on write) but explicitly deferred the walk itself: "the actual resolution algorithm... is an implementation detail for when this gets built — this sub-slice builds the graph and makes it safe to write to; nothing walks it yet." Nothing since has built it. [ADR 0019](../adr/0019-item-and-v-item.md)'s `v_item`/`v_item_instance` views read `entity_stat` for one entity's own id only — they show what's set directly *on* that entity, never what it inherits.

Concrete trigger: [GitHub milestone #1](https://github.com/ramsesoriginal/lorenzo/milestone/1)'s scenario needs "Ashfang" (an instance) → "Flaming Sword" (a prototype) → "Sword" (a base prototype) to resolve as one coherent effective stat set, with anything set closer to Ashfang overriding whatever "Sword" only provides by default. Nothing in the codebase produces that today — `v_item_instance.weight` etc. is `NULL` unless `entity_stat` has a row directly against Ashfang's own `entity_id`.

**Checking that same milestone against every proposed RFC surfaced a second gap in the identical territory**: there's no way to *write* `entity_stat`/`stat_definition`/`stat_group` at all either. [RFC 0005](0005-item-and-item-instance-crud-api.md) named this explicitly and pointed here: "a generic entity-attribute concern, not item-specific... a future 'generic entity attribute CRUD' RFC is the right home for it." Resolving effective stats and being able to set the stats that get resolved are the same underlying "stats" story — kept in this one RFC rather than split into a second document the two would just cross-reference constantly.

## Decision

Build RFC 0001's own rule, exactly as already specified — this RFC doesn't change it, only schedules building it:

1. For a given entity, walk `entity_prototype` outward from it (its own direct prototypes, their prototypes, and so on — [ADR 0015](../adr/0015-entity-prototype.md)'s graph, already cycle-safe by construction on write).
2. For each `stat_definition`, take the value from the closest node that sets it (fewest hops from the starting entity; the entity's own direct `entity_stat` row, if present, always wins outright — zero hops).
3. Break ties between two equally-close ancestors using `stat_group.priority` — a column that's existed since [ADR 0014](../adr/0014-stats.md) specifically for this, unused until now.

`v_item`/`v_item_instance` (and any future generic "effective stats for entity X" need) consume this instead of a flat `entity_stat` lookup — the views' plain-column *shape* is unaffected, only what populates `weight`/`hp`/`armor`/etc.

### Writing stats — unfinished, deferred alongside the mechanism above, not designed separately

**Deliberately not designed here** — this RFC only names the gap so it isn't lost, the same treatment the resolution mechanism above already gets:

- `stat_group`/`stat_definition` CRUD (the shared vocabulary — "physical," "combat," "weight," "hp") presumably belongs on the same tenant-admin-only tier [RFC 0005](0005-item-and-item-instance-crud-api.md)'s catalog authorization already established for `item` — authoring the shared vocabulary of what stats *can* exist is the identical kind of concern, not a new one.
- Setting an `entity_stat` value on a specific entity (a character's `hp`, an item's `weight`) presumably belongs on [RFC 0005](0005-item-and-item-instance-crud-api.md)'s self-or-managed instance tier instead — a player should be able to set their own character's or item's stats without GM involvement, the same reasoning that made moving your own item self-service there.
- Neither is actually decided — endpoint shapes, request schemas, and whether setting a stat needs its own guard (e.g. type-checking the value against `stat_definition.value_type`, today enforced only by `entity_stat`'s `CHECK` constraint, [ADR 0014](../adr/0014-stats.md)) are all real, undesigned work for whenever this RFC is actually picked up.

## Open questions (intentionally left open)

- **Mechanism.** A recursive CTE (mirroring `entity_prototype`'s own insert-time cycle-check trigger, and `routers/item_instances.py`'s `_recursive_descendants_cte` precedent for containment), a Postgres function, or an application-level Python walk — not decided. Whichever is chosen has to keep working under `v_item`/`v_item_instance`'s existing `security_invoker=true` RLS requirement ([ADR 0019](../adr/0019-item-and-v-item.md)).
- **Live computation vs. caching/materializing** effective stats — not decided; live is the simpler default until it's a proven cost problem, and nothing about this domain's scale so far suggests it already is one.
- **`game_system` needs to become a real, modeled concept, not a string.** `campaign.game_system` ([ADR 0024](../adr/0024-campaign-and-player.md)) is plain `TEXT` today — flagged while revising [RFC 0003](0003-tenant-campaign-read-api.md) as expected to transition to a foreign key "down the line," once there's something real for it to reference. That something doesn't exist yet: no table, entity, or other concept represents a game system as a first-class thing today — only this one free-text column and the prototype-variant sketch in the next bullet. Naming this now so it isn't lost, not designing it: what a "game system" concept even is (its own table? an entity, so it can carry stats/prototypes the same uniform way everything else does? something else?) is real, undesigned work this RFC doesn't do.
- **Multi-game-system stats** — [RFC 0001](0001-core-domain-data-model.md)'s open question #3 (a "Sword (D&D 5e)" vs. "Sword (Blades in the Dark)" prototype variant carrying different stat groups) is a related but separate concern this RFC doesn't resolve.

## Consequences

- No schema change for either half — `entity_prototype`, `entity_stat`, `stat_group.priority`, `stat_definition` all already exist exactly as both the resolution mechanism and a future stat-writing API need them.
- Until resolution is built, `v_item`/`v_item_instance`'s stat columns understate anything an item only inherits rather than sets directly — a real, currently-shipping gap, not a hypothetical one.
- Until writing is built, there's no way to give `Sword`/`Flaming Sword`/`Ashfang` (or any entity) a stat value in the first place — resolution would have nothing to resolve even once it exists. The two gaps are only fully closed together.
