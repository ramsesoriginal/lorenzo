# 0216 - Parents for any entry

Status: accepted, decided with the maintainer on 2026-10-08. Slice K3 of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md), tracked in #552. Builds on [ADR 0072](0072-item-catalog-prototype-set-editing.md), whose route it generalises, and [ADR 0015](0015-entity-prototype.md), whose table and cycle trigger it uses unchanged; needed by Bench and Studio to author a race, a class or a category node.

## Context

An entry's parents (the API's `prototype`: an `entity_prototype` row, what "inherits from" means) are written through `PUT /items/{id}/prototypes` and three `bulk-*` routes, all of which load the entry through the `item` table. A being, a character or a bare entry has no way to inherit from anything, though the table, its cycle trigger, the effective-stat view and the copy engine are all generic. So a race other beings inherit from, or a group under a category, cannot be written ([RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) §3). This slice adds the route and nothing else: no migration, no change to the engine.

## Decision

### `PUT /tenants/{id}/entities/{entity_id}/parents`

The body is `{"parent_ids": [...]}`, the complete new set of the entry's own direct parents; an empty list clears it. It answers `200` with the entry's detail (`EntityDetailOut`, whose `prototypes` is the new set) and an `ETag`. It works for an item, a being, a character and a bare entry.

| Case | Answer |
| --- | --- |
| The entry is not in the library, or is another library's | `404 entity-not-found` |
| `If-Match` is given and stale | `412` |
| The entry is an inventory item | `409 inventory-item-parents`: its one parent changes through `PATCH /item-instances/{id}` ([ADR 0192](0192-the-placeholder-item-the-api-and-the-seed.md)), and the detail says so |
| A parent id is the entry itself, or closes a loop (the trigger of ADR 0015 finds a transitive one) | `422 entity-prototype-cycle` |
| A parent id is not an entry of the library | `422 invalid-prototype` |
| The caller is not a member of the library | as `PUT /items/{id}/prototypes` |

Nothing is written for a refused request. A repeated id in the list is one parent.

**Loops are `422`, not the `409` RFC 0041 §3 says.** The RFC asks for the route to behave "exactly as `PUT /items/{id}/prototypes` does", and that route answers a loop `422` (`EntityPrototypeCycleError`, [ADR 0072](0072-item-catalog-prototype-set-editing.md)). Two routes that run one rule answer it one way, and changing the item route's status would break its clients for no gain; the RFC's number was a slip.

**The gate is the item route's: a member of the library.** The RFC leaves which routes an Author may use to [RFC 0040](0040-authors-and-invites.md), and this route is gated as the route it generalises.

### One write path

`entity_parents.replace_parents` holds the rules, and `PUT /items/{id}/prototypes` calls it, so an item and a being cannot drift. It compares the new set with the current one and **writes only the difference**: parents removed are deleted, parents added are inserted, a parent kept is not touched. A change sets `updated_by` and `updated_at` (the entry's ETag moves even when the same person writes twice) and is **one activity entry**: `entity.parents_replaced` with `parents=<count>` on this route, `item.prototypes_replaced` on the item route as before. **The same set again writes nothing, logs nothing and leaves the ETag where it was**; the item route used to log and bump on a repeated identical `PUT`, and now does not.

### What happens to inherited values

Nothing is stored, so nothing has to move. Effective stats resolve through the entry's parents when they are read ([ADR 0037](0037-effective-stat-resolution.md), [ADR 0039](0039-generic-effective-stat-view.md)), and so do inherited descriptions ([ADR 0111](0111-inherited-descriptions-and-stat-value-sources.md)): a being given a parent shows its stats the next read, and loses them when the parent is removed. A value the entry holds itself is its own (`own: true`) and survives any change of parents. A library that copied the repository sees the new parents as a changed `prototypes` field in its updates, merged element by element ([ADR 0121](0121-repository-updates-and-re-sync.md)), exactly as for an item; the tests cover it for a being.

### A version on the read

`GET /tenants/{id}/entities/{entity_id}` and `GET .../by-slug/{slug}` now carry an `ETag` header, the same weak tag from `updated_at` that items already have (`etag_for`), so a client has something to put in `If-Match` for a being or a bare entry. Without it the guard this route and the item route offer could not be used for any entry but an item.

## Not in scope

- The `bulk-add`, `bulk-remove` and `bulk-reparent` routes stay item-only; so does the ancestry read.
- A GM or an owner of a character as a writer: the route is for members of the library, as the item route is.
- The name `prototypes` on the item route: it stays beside `parents` until a cleanup ([RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md)).
- Refusing a parent by kind. An entry may be given any entry of the library as a parent, an inventory item included, as the item route allows.
- "New from parent" and duplicate: K4.

## Consequences

- A race, a class or a category node can be a being or a bare entry that others inherit from, and a group can sit under a category: the API obstacle to beings joining a rules repository ([RFC 0033](0033-item-repositories-common-equipment-rules-and-bridge.md)) is gone.
- API additions only: a route, a request schema, a problem type, an `ETag` header on two reads. The generated clients take them; the check for breaking changes finds none.
- `PUT /items/{id}/prototypes` is no longer a delete-and-reinsert: an unchanged parent keeps its row, and an identical request is a no-op, which is the one behaviour change.
- Nothing in the engine, the registry or the migrations changes.
