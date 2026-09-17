# 0065 - Bulk item-instance container move

Status: accepted

## Context

`PUT`/`DELETE /tenants/{tenant_id}/item-instances/{entity_id}/container` ([RFC 0005](../rfcs/0005-item-and-item-instance-crud-api.md)) move or clear one item instance's `Containment` row at a time. Emptying a chest into a cart, or relocating a list of already-decided items into a new container, means one HTTP call per item today - the exact "N separate requests, no way to know what happened as a whole" gap [ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md) already closed for ownership assignment (`bulk-assign`) and [ADR 0062](0062-bulk-invite-to-tenant.md) closed for tenant invites. Nothing does the same for containment.

## Decision

### `POST /tenants/{tenant_id}/item-instances/bulk-move`

Body: `BulkMoveContainerRequest{to_container_entity_id: uuid.UUID, from_container_entity_id: uuid.UUID | None = None, items: list[BulkMoveItem] | None = None}`, `BulkMoveItem{entity_id: uuid.UUID, if_match: str | None = None}`. Exactly one of `from_container_entity_id`/`items` must be set - a Pydantic `model_validator`, not a database `CHECK` (this is a request-body shape invariant with no row to constrain, unlike `knowledge`'s exactly-one-of-N columns, ADR 0028); FastAPI surfaces a violation as an ordinary `422` validation error.

- **`from_container_entity_id` given** ("move everything in this container"): resolves to every item instance whose `Containment.parent_entity_id` is that entity, **direct children only** - the same non-recursive default `GET /item-instances?container_id=` already uses, and consistent with this codebase's general preference for explicit over implicit (recursing an arbitrarily deep containment tree into a single flat move was not asked for and isn't built here). `from_container_entity_id` must itself resolve to a real entity in this tenant (`404`, checked once via `get_entity_or_404`) - resolving to zero contained item instances is not an error, just an empty result list, mirroring `list_group_members`'s own "exists but empty" tolerance. No `if_match` is possible in this mode - the caller doesn't have per-item ids ahead of time to attach one to.
- **`items` given** ("move exactly this list"): each entry's `entity_id` is moved regardless of its current container or owner, with an optional per-item `if_match`, mirroring `BulkAssignItem`'s identical shape.

`to_container_entity_id` must resolve to a real entity in this tenant - checked **once**, up front (`404`), not per item: it's the same destination for every entry in the batch, the identical "doesn't vary per item, so check it once" reasoning [ADR 0062](0062-bulk-invite-to-tenant.md) already gives for its own up-front `_require_owner` check, as opposed to [ADR 0044](0044-loot-assignment-split-merge-bulk-assign.md)'s per-item re-check where the fact being checked genuinely does vary per item.

Each item's own move - existence, `If-Match` (when given), and `_authorize_instance_write` against that item (self-or-managed, unchanged - moving an item you can reach is exactly as self-service as the existing single-item `PUT .../container`, no new authorization tier) - runs inside its own `session.begin_nested()`, the same never-all-or-nothing `bulk_assign_item_instances`/`bulk_create_memberships` pattern: a caught `Problem` becomes that item's own `"error"` entry, everything else already applied proceeds to the one shared commit. The actual mutation is `_perform_set_container`, extracted from `set_item_instance_container`'s own body exactly as ADR 0044 extracted `_perform_split`/`_perform_set_owner` - the single-item `PUT` and this new bulk route share one implementation, so the two can't drift.

Response: always-`200` `list[BulkMoveResultItem{entity_id, status: "ok" | "error", item_instance: ItemInstanceOut | None, problem: ProblemOut | None}]`, one entry per resolved item - identical shape to `BulkAssignResultItem`.

No new cycle/self-containment guard: `PUT .../container` today allows moving an item into itself or forming a containment cycle at all (ADR 0016's deliberate "game worlds can be legitimately non-Euclidean," unchanged since). This ADR reuses that route's exact mechanics via `_perform_set_container` and does not tighten it as an incidental side effect of adding a bulk path.

## Not in scope

Partial-stack moves - this operates on whole `Containment` rows, exactly like the existing single-item `PUT .../container` (`quantity` rides along untouched, per [ADR 0041](0041-containment-quantity-and-stacking.md)); splitting off part of a stack and moving only that part is `split` (ADR 0041/0044) followed by an ordinary move, not a new combined primitive. A recursive "move everything nested arbitrarily deep inside this container" mode - direct children only, as decided above. Bulk container-move for non-item entities (a room full of NPCs) - `set_item_instance_container`'s own write surface is item-instance-only today (ADR 0041's own identical scoping), and this ADR doesn't widen that.

## Consequences

- `schemas/items.py` gains `BulkMoveContainerRequest`, `BulkMoveItem`, `BulkMoveResultItem`.
- New typed problem: none - every failure mode this route can hit (`404`/`403`/`412`) already has one from the existing single-item routes; reused as-is.
- `routers/item_instances.py`: `set_item_instance_container`'s own mechanics extracted into `_perform_set_container` (auth/`If-Match`/response-shaping stay in the route, only the DB mutation moves, mirroring `_perform_split`/`_perform_set_owner`'s own extraction); new `bulk_move_item_instances` route built on it.
- No migration - this is a new endpoint over the existing `containment` table, no schema change.
- A GM can now empty a whole container in one call, or relocate a specific claimed-items list into a new container in one call, with a clear per-item outcome instead of one `PUT` per item and no combined picture of what succeeded.
