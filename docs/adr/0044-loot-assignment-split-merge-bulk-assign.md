# 0044 - Loot assignment: split-with-owner, merge, and bulk-assign

Status: accepted

## Context

The motivating "loot drop" flow this whole round of API additions targets - a GM opens an already-prepared container, players take whole items or part of a stack, a GM later assigns several already-claimed items to different characters in one operation - needs three primitives that don't exist yet:

1. `POST .../split` ([ADR 0041](0041-containment-quantity-and-stacking.md)) always copies the source's current owner onto the split-off piece - there's no way to split *and* hand the split-off piece to a different character in one call; today that's split, then a separate `PUT .../owner`, two calls and two chances to race.
2. There is no inverse of split - picking up a dropped stack and adding it to an existing stack of the same thing requires deleting one and hand-editing the other's `Containment.quantity` directly against the database; [ADR 0041](0041-containment-quantity-and-stacking.md) named this explicitly as a real gap, not built at the time.
3. Assigning several already-decided items to different characters is one sequential `PUT .../owner`/`POST .../split` call per item today, with no way to know what happened as a whole if some succeed and some don't - a client wanting "5 of 6 succeeded, item X was already taken" has to track that itself across N separate requests.

Authorization scope note: while grounding this ADR against the current code, a real gap was found in `_authorize_instance_write` (the existing self-or-managed check every owner/container/split write already uses) - it authorizes purely against the item's *current* state (its current owner's campaign, or "any campaign in tenant" if unowned), never against the *new* target character being assigned. Concretely, a GM of campaign A can today reassign campaign A's own item to a character in an unrelated campaign B with zero standing over B, and any campaign's GM can claim any ownerless item for any character tenant-wide. This was raised with the user directly; the explicit decision was to leave this authorization behavior unchanged and build bulk-assign on top of it as-is, not to tighten it as part of this ADR.

## Decision

### `split` gains an optional target owner

`SplitItemInstanceRequest.owner_character_id: uuid.UUID | None = None`. When given, the new split-off instance is created with that owner instead of copying the source's current owner (which remains the behavior when omitted). Authorization unchanged: `_authorize_instance_write` against the *source* only, per the Context note above - no new target-side check.

### `POST .../item-instances/{entity_id}/merge` - the inverse of split

Body: `MergeItemInstanceRequest{into_entity_id: uuid.UUID}`. Full-merge only, mirroring split's own single-operation shape: `entity_id`'s entire current `Containment.quantity` is added onto `into_entity_id`'s stack, then `entity_id`'s `Entity` row is deleted (cascading its own `Containment`/`ItemInstance`/`Ownership`/`EntityPrototype` rows away with it, [ADR 0018](0018-sqlalchemy-modeling-conventions.md)'s existing cascade behavior, unmodified).

Guards (`422 InvalidMergeError`): `entity_id == into_entity_id` (merging into itself); either side missing a `Containment` row (nothing to combine - matches split's own "must be contained to carry a count" precedent); the two `Containment` rows having different `parent_entity_id` (merging across containers silently relocating one of them is a foot-gun, not a feature - move one into the other's container first, then merge); the two instances having different current owners, including the both-uncontained-by-anyone (`None`/`None`) case counting as a match (silently changing an owner as a side effect of a stack operation is the same foot-gun as the container case). No requirement that the two instances share the same prototype - matches `split`'s own existing lack of type-checking, an accepted looseness this ADR doesn't newly introduce.

Authorization: `_authorize_instance_write` on **both** `entity_id` and `into_entity_id` - this write mutates both rows (one is deleted, the other's quantity changes), so both need standing, not just the source. `If-Match` (optional, as everywhere) is checked against the *source* (`entity_id`) only, mirroring `split`'s own single-sided precondition check. Response: `200` + the *target*'s (`into_entity_id`'s) resulting `ItemInstanceOut` - it's the surviving resource whose state actually changed in a way the caller is likely to want to see immediately, unlike `split`'s `201` (a genuinely new resource is created there; nothing new is created here).

### `POST .../item-instances/bulk-assign`

Body: `list[BulkAssignItem{entity_id, owner_character_id, quantity: int | None = None, if_match: str | None = None}]`. `quantity` given delegates to the split-with-owner path above (creating a new instance); omitted delegates to the plain owner-`PUT` path (reassigning `entity_id` itself). Both delegate to the exact same helper functions the single-item routes call (`_perform_split`/`_perform_set_owner`, extracted from those routes' own bodies) - not a reimplementation, so the two paths can't drift apart.

Response: `list[BulkAssignResultItem{entity_id, status: "ok" | "error", item_instance: ItemInstanceOut | None, problem: ProblemOut | None}]`, one entry per input, always `200` - **not** all-or-nothing, since the whole point is "tell me what happened to each one," not "fail the batch on one stale claim." Each item's `check_if_match`/`_authorize_instance_write`/mutation runs inside its own `session.begin_nested()` (a SQL `SAVEPOINT`): a typed `fastapi_problem.error.Problem` raised by any of those (a `404`, `403`, `412`, or `422`) is caught, rolls back just that item's own nested transaction via the `async with` block's own exception handling, and becomes that item's `"error"` entry (`problem` populated from the exception's own `.marshal()` - the identical dict shape a real single-item error response body would have) - the other items' already-applied, uncommitted changes are untouched and proceed to the shared final `await session.commit()`. An unexpected (non-`Problem`) exception is **not** caught here and fails the whole request as a `500`, matching this codebase's general practice of only ever gracefully handling anticipated, typed failure modes.

## Not in scope

Tightening `_authorize_instance_write`'s target-blind authorization (see Context - an explicit, separate decision, declined for this ADR). Partial merges (merging only some units of a stack into another) - a full merge is the only operation that has no equivalent already reachable through `split` + reassignment, so it's the only one built; see [ADR 0041](0041-containment-quantity-and-stacking.md)'s own "Not in scope" for the identical reasoning about why a `merge` endpoint wasn't built there. Automatic merging of stacks that land in the same container by coincidence - explicit only, matching this codebase's general preference.

## Consequences

- `schemas/items.py`: `SplitItemInstanceRequest.owner_character_id`; new `MergeItemInstanceRequest`, `BulkAssignItem`, `BulkAssignResultItem`, `ProblemOut`.
- New typed problem: `InvalidMergeError` (422).
- `routers/item_instances.py`: `split_item_instance`'s and `set_item_instance_owner`'s own mechanics extracted into `_perform_split`/`_perform_set_owner` (auth/`If-Match`/response-shaping stay in each route, only the DB mutation itself moves); new `merge_item_instance` and `bulk_assign_item_instances` routes, both built on those same two helpers.
- A GM can now hand a freshly-split pile of arrows straight to the character who claimed it in one call, pick up a dropped stack and fold it into an existing one instead of hand-editing the database, and resolve a whole loot-split session's worth of assignments in one request with a clear per-item outcome - the concrete gaps the motivating flow named are closed.
