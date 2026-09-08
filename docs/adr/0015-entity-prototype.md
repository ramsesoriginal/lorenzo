# 0015 - entity_prototype: the inheritance graph

Status: accepted

## Context

[RFC 0001](../rfcs/0001-core-domain-data-model.md) designed prototype inheritance as a self-referential join on `entity` — a prototype isn't a separate kind of row, just an entity referenced as a parent by another. This ADR promotes that join table as sub-slice 4, after `entity` ([ADR 0012](0012-entity-table.md)), the tenant bootstrap ([ADR 0013](0013-tenant-table-bootstrap.md)), and stats ([ADR 0014](0014-stats.md)). RFC 0001 flagged cycles here as needing real prevention, unlike `containment`'s deliberate cycle-tolerance: resolving an entity's effective stats means walking the prototype graph to a fixed point, and a cycle would just infinite-loop.

**Not in scope**: the actual resolution algorithm (walking the graph to compute effective/inherited stat values, applying "more specific wins" and `stat_group.priority` tie-breaking). RFC 0001 explicitly left that as "an implementation detail for when this gets built" — this sub-slice builds the graph and makes it safe to write to; nothing walks it yet.

## Decision

`entity_prototype(entity_id, prototype_id, tenant_id)` — composite primary key, both `entity_id` and `prototype_id` FK to `entity.id`. An entity can have any number of rows here (multiple inheritance). Tenant-scoped like every table so far (`tenant_id` + `ENABLE`/`FORCE ROW LEVEL SECURITY`); same known, unsolved limitation as `entity_stat_group` ([ADR 0014](0014-stats.md)) — nothing enforces that `entity_id`/`prototype_id`/`tenant_id` actually agree with each other.

Two independent mechanisms prevent cycles, since they catch different cases:

- **`CHECK (entity_id <> prototype_id)`** — rejects direct self-inheritance. Plain, single-row, no trigger needed.
- **A `BEFORE INSERT` trigger** running a recursive CTE, walking from the new row's `prototype_id` through existing `entity_prototype` edges: if that walk can already reach the new row's `entity_id`, the prototype transitively inherits from the entity already, and adding this edge would close a loop — rejected. Scoped to `INSERT` only, not `UPDATE`: this table has no data beyond the relationship itself, so changing an inheritance edge is naturally a delete-then-insert, not an in-place update, and supporting `UPDATE` too would need reasoning about the row-being-updated's own old values mid-walk for no real benefit.

## Consequences

- Multiple inheritance is just "insert more rows" — proven directly by the tests (an entity acquiring several prototypes at once).
- The recursive CTE runs on every insert into a table that's a small fraction of `entity`'s own size in practice (prototype graphs are shallow and don't grow proportionally with instance count) — not a real performance concern at this scale, revisit if it ever becomes one.
- "What's this entity's effective weight, inherited through its prototypes" still isn't answerable after this — that's the next piece of work, once this graph exists to walk.
- Same RLS caveat as every table so far: policies are real and tested, but currently unenforced in practice until the app's DB role stops being a superuser (ADR 0002/0012).
