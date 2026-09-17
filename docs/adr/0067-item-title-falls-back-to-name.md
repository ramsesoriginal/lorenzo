# 0067 - `title` falls back to `name` when empty

Status: accepted

## Context

`ItemOut.title` (inherited by `ItemInstanceOut`) is sourced from `VItem`/`VItemInstance.title`, itself a `LEFT JOIN` onto whichever `Information` row of `type="description"` the entity has ([ADR 0019](0019-item-and-v-item.md)) - `None` whenever no such row exists at all, which is the common case for anything not yet given a public description. A client displaying an item's "name" today has to fall back to `entity_id` or hand-roll its own default whenever `title` is `None`, even though `Entity.name` - the item's own stable, always-set identifier ([ADR 0047](0047-item-catalog-search-and-container-convention.md) already leans on this same fact for its own `q` search target) - is right there.

Asked directly for `title` itself to fall back to `name` when empty, rather than adding a second field alongside it.

## Decision

`schemas/items.py` gains `_title_out(title, *, name) -> str`, used by `_common_item_fields`: `title or name` - `or`, not an `is None` check, so an `Information.title` that's a non-null but literally empty string (the column is `NOT NULL`, not non-empty) falls back too, the same "empty counts as unset" reading this module's `_is_container_out` (ADR 0066) already established for its own tag lookup.

`ItemOut.title` narrows from `str | None` to `str` - it can no longer actually be `None` on the response, since `Entity.name` is itself `NOT NULL` and always present. The underlying `VItem.title`/`VItemInstance.title` columns stay nullable, unchanged - this is a response-shaping fallback in the schema layer only, not a change to what's stored or to `v_item`'s own `CREATE VIEW` SQL.

No new eager-load requirement: `view.entity.name` is already loaded as part of `view.entity` itself, which every existing field in `_common_item_fields` already depends on (`created_by`/`updated_by`/`updated_at` read off it too).

## Not in scope

Any change to how `title` is authored or stored - still exactly one `Information`/`Payload`/`PayloadDescription` row per entity, per ADR 0017/0019/0038. A similar fallback for any other nullable display field - not asked for, scoped to `title` alone.

## Consequences

- `schemas/items.py`: new `_title_out`; `_common_item_fields` computes `title` via `_title_out(view.title, name=view.entity.name)` instead of reading `view.title` directly; `ItemOut.title: str` (was `str | None`).
- Two existing tests asserting `title is None` for an undescribed item/instance now assert the fallback name instead (`test_api_items.py::test_create_item_without_prototypes`, `test_api_item_instances.py::test_update_item_instance_self_service_rename`) - the behavior they were pinning down genuinely changed, not a spurious break.
- No model, router, or migration changes.
- A client reading `item.title` always gets a non-empty string to display, without a `None`-check of its own.
