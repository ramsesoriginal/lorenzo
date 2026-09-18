# 0072 - Item catalog prototype-set editing

Status: accepted

## Context

[GitHub issue #82](https://github.com/ramsesoriginal/lorenzo/issues/82): `apps/inventory-web`'s GM item-management UI can create a catalog item with zero or more prototypes (`POST /tenants/{tenant_id}/items`, `ItemCreate.prototype_ids`), but has no way to edit that set afterward - `PATCH /tenants/{tenant_id}/items/{id}` (`ItemUpdate`) only ever touched `name`, by design ("nothing else on a bare Item row exists to update," [RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md)). RFC 0005/[ADR 0032](0032-item-and-item-instance-crud-api.md) explicitly deferred this: "prototype-graph editing on an existing item... `entity_prototype` is generic, not item-specific" - waiting on a hypothetical future "generic entity attribute CRUD" RFC that still doesn't exist. With a concrete GM-facing need now in hand, this ADR picks the deferred piece back up scoped narrowly to a catalog item's own direct prototype set, rather than waiting further on a generic entity-graph editor nothing has asked for yet.

## Decision

### `PUT /tenants/{tenant_id}/items/{entity_id}/prototypes`

Body: `SetPrototypesRequest{prototype_ids: list[uuid.UUID] = []}` - the same shape as `ItemCreate.prototype_ids`, as a stand-alone action. Full replacement, not a delta: every existing direct `EntityPrototype` row for `entity_id` is deleted and one row per given id is inserted, in the same transaction - deliberately not an add/remove API. A client wanting to add one prototype to an existing item's set reads the current set (now on `ItemOut`, below) and `PUT`s it back with one more id - the identical "transfer to a new owner" and "set an owner for the first time" being the same call shape that [ADR 0032](0032-item-and-item-instance-crud-api.md) already gives `PUT .../owner`, just over a set instead of a single value.

No `DELETE` sub-resource, unlike `owner`/`container`: those are singular values with no way to express "empty" other than deleting the row, so clearing them needs a dedicated action. A set already has its own empty representation - `PUT .../prototypes` with `prototype_ids: []` already means "clear everything" - so a separate `DELETE` would just be a second way to say the same thing.

### Validation - pre-checked explicitly, not left to surface as a raw DB violation

Matching this codebase's established convention (`InvalidUserError`/`InvalidCharacterError`/`InvalidStatGroupError`/`InvalidGroupMemberError`, all "body references something that isn't there, checked before it can hit a raw constraint"):

- **Each id must resolve to a real `Entity` in this tenant** - checked with one `IN` query up front; `422 InvalidPrototypeError` naming every missing id otherwise. Deliberately **not** required to itself be a base `Item`, unlike `ItemInstanceCreate.prototype_id`'s own `InvalidItemPrototypeError` check - `entity_prototype` is a generic entity-to-entity edge ([ADR 0015](0015-entity-prototype.md)), and `POST /items`'s own existing `prototype_ids` handling imposes no such restriction either. This endpoint doesn't newly narrow what create-time already allowed.
- **`entity_id` itself in the given set** - `422 EntityPrototypeCycleError` (a self-loop is a degenerate one-hop cycle). Cheap to check in Python; no need to round-trip through `entity_prototype`'s own `entity_prototype_no_self_loop` CHECK to reject it.
- **A transitive cycle** (the replacement would make some prototype in the new set transitively inherit back from `entity_id`) is left entirely to `entity_prototype`'s existing `BEFORE INSERT` trigger ([ADR 0015](0015-entity-prototype.md)) - re-deriving that recursive CTE in Python would just be a second copy of the same logic to keep in sync. This is the first write path able to actually reach that trigger through client input: every prototype id up to now only ever appeared on a brand-new entity at `POST /items`/`POST /item-instances` time, which can't yet be anyone's ancestor. The trigger's `DBAPIError` is caught around the replacing `flush()` and translated into the same `422 EntityPrototypeCycleError`, rather than surfacing as an unhandled 500.

### `ItemOut` gains `prototype_ids: list[uuid.UUID]`

Read off `Entity.prototype_links` (already a relationship - newly added to `eager_load_options`'s eager-load recipe, shared by `routers/items.py` and `routers/item_instances.py`). `ItemInstanceOut` inherits it for free. This closes the actual gap the issue itself flagged as "worth checking" - the existing read shape did not expose it - without a dedicated `GET .../prototypes`: the identical reasoning `owner_entity_id`/`container_entity_id` already being inline fields on `ItemInstanceOut` gives for those not having their own `GET` either. `PUT .../prototypes` itself returns `200 ItemOut`, the same "the relationship action returns the canonical resource" convention every other write on this router already follows.

### Attribution: unlike owner/container, this **does** touch `entity.updated_by`/`updated_at`

[ADR 0032](0032-item-and-item-instance-crud-api.md) deliberately keeps the owner/container actions off `entity.updated_by` - "moving an item isn't updating it in the sense that column tracks." A prototype set is different: it's part of what the item *is* (it changes the item's own resolved/effective stats, [ADR 0037](0037-effective-stat-resolution.md)/[0039](0039-generic-effective-stat-view.md)), not where it's placed - closer to `PATCH .../items/{id}`'s rename than to a relocation. This also keeps the item's own `ETag` meaningful: `ItemOut` now includes `prototype_ids` directly (and its resolution-dependent stat fields already did indirectly), so a stale `ETag` surviving a prototype change would otherwise be a real, silent caching bug.

## Not in scope

**Bulk operations across many items** - e.g. "add prototype X to every item currently missing it," or the issue's own "push a prototype up the chain" idea (replacing prototype X with a new intermediate Y across every item that currently has X as a direct prototype, so `Weapon->Sword`/`Weapon->Dagger`/`Weapon->Axe` all become `Weapon->MeleeWeapon->{Sword,Dagger,Axe}` in one call). Both are real, plausible future needs - mirroring [ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md)/[0065](0065-bulk-item-instance-container-move.md)'s own "bulk operation built on top of an existing single-item primitive" pattern - but each raises its own design questions (does re-parenting also auto-link the new intermediate back to the old one? scoped by an explicit id list or "every item currently having X"? tenant-wide or narrower?) that don't belong bundled into this ADR. Flagged here for a future ADR if/when it's actually asked for, not built speculatively now.

**"Splicing" a prototype into the middle of an existing chain** (the issue's other example: `Weapon->Longsword` becoming `Weapon->Sword->Longsword`) - already fully expressible with `POST /items` plus this ADR's own endpoint (create `Sword` with `prototype_ids: [Weapon]`, then `PUT` `Longsword`'s prototypes to `[Sword]`) - no new endpoint needed for it.

**`ItemInstance`'s own direct prototype** (fixed at `POST /item-instances` time) - the issue, ADR 0032, and RFC 0005 all frame this request as a *catalog* item concern; an instance's prototype is a different, narrower invariant (`InvalidItemPrototypeError`'s own "must be a base item" check) this ADR doesn't touch. `ItemInstanceOut.prototype_ids` is still populated (it inherits `ItemOut`'s new field for free) for read-side symmetry, purely informational.

**Fixing `POST /items`'s own pre-existing gap of never validating `prototype_ids` at all** (a nonexistent id today surfaces as a raw FK-violation 500 - confirmed by grep, no test covers it). The same condition this ADR's own `InvalidPrototypeError` now guards against, but a pre-existing issue independent of this one - not silently folded in here.

## Consequences

- No migration - `entity`/`entity_prototype` both already exist ([ADR 0012](0012-entity-table.md)/[0015](0015-entity-prototype.md)), the same "new endpoint over existing tables" shape as [ADR 0047](0047-item-catalog-search-and-container-convention.md)/[0065](0065-bulk-item-instance-container-move.md).
- `exceptions.py` gains `InvalidPrototypeError` (422) and `EntityPrototypeCycleError` (422).
- `schemas/items.py` gains `SetPrototypesRequest`; `ItemOut` gains `prototype_ids` (inherited by `ItemInstanceOut`).
- `routers/items.py`'s `eager_load_options` (shared with `routers/item_instances.py`) gains `Entity.prototype_links`.
- `routers/items.py` gains `replace_item_prototypes` (`PUT /{entity_id}/prototypes`).
- The bulk/re-parenting/splice ideas raised alongside this request are recorded here as real future candidates, not lost, but intentionally not built now.
