# 0266 - Stat tie-break by parent order

Status: accepted

## Context

[ADR 0037](0037-effective-stat-resolution.md) resolves an entry's effective stat by the nearest ancestor that sets it (a direct value always wins), then, among ancestors at the same distance, by the highest priority of the stat groups each has acquired ([ADR 0014](0014-stats.md)), and left the entity id as a "deliberately arbitrary but deterministic" last resort. [ADR 0039](0039-generic-effective-stat-view.md) moved that into `v_effective_stat` for every entry, and [ADR 0104](0104-computed-stats.md) added formulas to the same ordering.

What was undecided is the case a library really meets: two parents of one entry at the same distance, neither with a group of higher priority (usually neither with a group at all). Which parent wins was the order of their random ids, so adding a parent could silently change a stat, and an author had no way to say "this parent first". The v1.0 row "stat tie-break order" ([v1.0.md](../../v1.0.md)) was this.

The order of an entry's parents was also not stored: `entity_prototype` was a set of `(entity, prototype)` pairs, written by `PUT /entities/{id}/parents` ([ADR 0216](0216-parents-for-any-entry.md)) as a set and read back in id order.

## Decision

- **The entry's own parent order breaks the tie.** The parent listed first wins. For ancestors further away, the order is that of the parents they were reached through, compared from the entry down: an ancestor reached through the first parent beats one reached through the second, and where those are the same parent, the next step down decides.
- **The entity id is the last resort**, as before, when two ancestors are still equal (the same position in two lists, or a row written without a place that a trigger put last in the same step).
- **Nothing else about resolution changes.** The order of the rules stays: distance, a stored value before a formula at the same distance, group priority, and only then parent order and id. A direct value of the entry still beats every ancestor; a nearer ancestor still beats a further one whatever the order.
- **The order is stored** in a new column, `entity_prototype.position` (integer, not null). The migration gives every existing row the place its id gave it in its entry's list, so no stat resolves differently than it did before. A trigger fills it for a row written without one (the next place after the entry's last parent), so every other writer (a stack split, a duplicate, a repository sync or attachment, an instance's prototype change) appends, and no caller is forced to know about it. The writers that take a list set the places themselves: `PUT /entities/{id}/parents` and `PUT /items/{id}/prototypes` (the same function), `POST /entities`, `POST /items`, a stack split and a duplicate (they copy the order of what they copy from).
- **`PUT .../parents` keeps the list's order**: it is the complete list, in that order. A list equal to the stored one, in the same order, writes nothing and does not move the entry's version (ETag); the same ids in another order is a change. A repeated id counts once, at its first place.
- **The order is read back**: `parent_ids` of the entries list, `prototype_ids` of an item and the repository browse list the parents in order, ties by id.
- **A repository copy keeps the order.** The copy reads a repository's parents in their order and writes them with places in that order. A parent added by a later update or an attachment goes last. The content digest and a release's change list still compare parents as a set, so reordering a repository's parents alone is not a change a release reports; a copy that took the earlier order keeps it until it is copied again.
- **`v_effective_stat` carries the rule**: its walk records the places taken from the entry to each ancestor (an integer array) and orders by it before the id. `v_item` and `v_item_instance` read it and are unchanged.
- **No API schema change.** The routes' bodies and answers had lists already; only their order now means something and is kept.

## Consequences

- Putting the more specific parent first now decides a clash, in the Bench parents editor and through the API alike. Nothing needs a new field.
- An existing library resolves exactly as before until someone reorders parents.
- A new tenant table column was added to a registered table, so [`copyable_tables.py`](../../apps/api/src/lorenzo_api/copyable_tables.py) needed no new line; `entity_prototype` was already in it as content.
- Reordering parents of a repository entry is not reported as a change by publish (the digest is a set); an author who needs subscribers to take the new order publishes after some other change, or a later ADR makes order part of the digest.

## Tests

`apps/api/tests/test_stat_parent_order.py`: two parents at equal distance and priority with each order, reordering through the API flipping the winner (and back), the order read back from the entries list, a create with parents keeping their order, a parent added by a writer that names no place going last, the id fallback for equal places, group priority still beating the order, a direct value still beating both, grandparents decided by the order of the parents they come through, and an unchanged order leaving the ETag alone. The existing suite, including the priority tie-break tests of ADR 0037, passes unchanged.
