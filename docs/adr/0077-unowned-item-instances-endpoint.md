# 0077 - Unowned item-instances endpoint, grouped like owned-by

Status: accepted

## Context

`apps/inventory-web`'s GM item-management board ([issue #77](https://github.com/ramsesoriginal/lorenzo/issues/77)/milestone 3) renders `GET .../item-instances/owned-by/{owner_entity_id}`'s `OwnedByResponse` shape directly: columns are containers, cards are item instances. There's no equivalent way to browse item instances that have **no** owner at all - freshly created stock, unclaimed loot sitting in a container - which is exactly the other half of a GM's "assign this to someone" workflow ([issue #95](https://github.com/ramsesoriginal/lorenzo/issues/95)).

`GET /tenants/{tenant_id}/item-instances` (the plain list) has no owner filter of any kind, and adding `unowned=true` there would return the wrong *shape* - a flat paginated list, not grouped by container the way the board's existing rendering code expects. The issue's own suggestion - mirror `owned-by/{owner_entity_id}` exactly - avoids a second, differently-shaped client-side renderer for what's conceptually the same "instances at a location" view.

## Decision

New `GET /tenants/{tenant_id}/item-instances/unowned`, returning the identical `OwnedByResponse`/`OwnedGroupOut` shape `owned-by/{owner_entity_id}` already returns - literally the same schemas, no new ones. Registered before `/{entity_id}` and after `/owned-by/{owner_entity_id}`/`/by-slug/{slug}` in `routers/item_instances.py`, for the same wildcard-shadowing reason those two are already ordered that way (confirmed empirically for this pattern before, per that router's own existing comments).

Authorization: `require_tenant_participant`, same as every other read route in this router - no visibility narrowing beyond that. Ownerless instances are already unconditionally visible to any tenant participant per [ADR 0040](0040-item-instance-read-visibility.md) (`_visible_owner_predicate`'s first OR-branch, unconditional) - there is no owner to reach or hide behind, so this endpoint needs none of that predicate's owner-reachability logic at all, unlike `owned-by`.

The container-grouping mechanics (join `Containment`, collect referenced containers, group into `OwnedGroupOut`) are extracted into a shared `_grouped_by_container_response` helper, parameterized by which `owner_entity_id` condition selects rows - `owned-by` and `unowned` now both call it, rather than keeping two copies of the same grouping logic that could drift, the same `_perform_set_owner`/`_perform_split`-style extraction this router already uses for its write paths.

## Not in scope

- A query-param filter on the plain list endpoint - rejected above in favor of matching `owned-by`'s grouped shape exactly, per the issue's own stated rendering-reuse rationale.
- Any change to `owned-by/{owner_entity_id}`'s own behavior or response shape.

## Consequences

- `routers/item_instances.py`: new `GET .../unowned` route plus the `_grouped_by_container_response` extraction; `list_item_instances_owned_by` now calls it too, unchanged in behavior.
- No migration - `VItemInstance.owner_entity_id` (ADR 0019) already exists and is already nullable; this is a pure read addition.
- Closes [issue #95](https://github.com/ramsesoriginal/lorenzo/issues/95).
