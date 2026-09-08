# 0016 - Containment: the generic entity-to-entity physical relation

Status: accepted

## Context

[RFC 0001](../rfcs/0001-core-domain-data-model.md) designs `containment` as "a plain, generic entity-to-entity relation covering an item in a backpack, a backpack on a character, a character in a room, all the same table." This ADR promotes it as sub-slice 5, after `entity` ([ADR 0012](0012-entity-table.md)), the tenant bootstrap ([ADR 0013](0013-tenant-table-bootstrap.md)), stats ([ADR 0014](0014-stats.md)), and `entity_prototype` ([ADR 0015](0015-entity-prototype.md)).

RFC 0001 is explicit that containment is **deliberately cycle-tolerant**, unlike `entity_prototype`: "game worlds can be legitimately non-Euclidean (a room whose exit leads back into itself, recursive pocket dimensions), so traversal code needs to handle cycles gracefully rather than the schema forbidding them." This is the opposite conclusion from ADR 0015's prototype graph, which rejects cycles because there's no sensible way to resolve an inheritance chain that never terminates. A cyclic physical space is just a weird but valid space; nothing about it fails to make sense the way a self-inheriting prototype does.

**Not in scope**: `ownership` (RFC 0001 explicitly moves it to [RFC 0002](../rfcs/0002-campaign-player-character-model.md), which needs `character`/`player` machinery this branch doesn't have yet) and any traversal/query logic over the containment graph (e.g. "list everything eventually inside this room"). This sub-slice builds the relation and makes it safe to write to; nothing walks it yet, same framing as ADR 0014 and ADR 0015 before it.

## Decision

`containment(child_entity_id, parent_entity_id, tenant_id)`. Both `child_entity_id` and `parent_entity_id` FK to `entity.id`; `tenant_id` FK to `tenant.id`, `NOT NULL`, indexed — the same pattern as every table so far. No row for a given entity means "not contained in anything" (a room, or any other top-level entity), the same no-row-means-no-relation convention `entity_prototype` already uses, rather than a nullable parent column.

**Primary key is `child_entity_id` alone, not a composite `(child_entity_id, parent_entity_id)`.** This is a deliberate difference from `entity_prototype`'s composite PK, which exists specifically to let an entity hold several rows at once (multiple inheritance is a first-class feature there). Containment has no equivalent case: a physical object isn't simultaneously inside two different containers, so the schema enforces "at most one direct container per entity" directly, rather than leaving it as an application-level invariant to maintain by hand. A useful side effect: moving an item to a new container is a single `UPDATE` of `parent_entity_id`, not the delete-then-insert `entity_prototype` needs for a changed inheritance edge.

**`parent_entity_id` is indexed**, unlike `entity_prototype.prototype_id`. "What does this container hold" is the query this vertical slice exists to support (listing a backpack's or room's contents) and isn't covered by the PK the way it would be if `parent_entity_id` were the composite PK's leading column — worth the extra index here even though the equivalent case wasn't indexed for `entity_prototype`.

**No CHECK constraint and no trigger** — not even the trivial `child_entity_id <> parent_entity_id` self-loop check `entity_prototype` has. RFC 0001 asks for full cycle tolerance, including the degenerate case; adding partial prevention here would contradict the RFC's own reasoning rather than implement it.

## Consequences

- "Where is this" (by PK) and "what does this contain" (by the new `parent_entity_id` index) are both cheap, indexed lookups.
- Same known, unsolved limitation as `entity_stat_group`/`entity_prototype`: nothing enforces that `child_entity_id`/`parent_entity_id`/`tenant_id` actually agree with each other.
- Nothing here computes "everything eventually inside this room" or does anything special when a cycle exists — that's traversal/application logic for later, and it has to be written cycle-safely (e.g. tracking visited nodes) precisely because the schema won't stop a cycle from existing.
- Same RLS caveat as every table so far: policies are real and tested, but currently unenforced in practice until the app's DB role stops being a superuser (ADR 0002/0012).
