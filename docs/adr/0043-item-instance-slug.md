# 0043 - Item-instance slug

Status: accepted

## Context

A client building a "loot drop" flow needs to find a specific, already-created item instance again later - e.g. a GM authoring a scripted encounter wants to reference "the cursed dagger I placed in the shrine" from outside the API (a level-design spreadsheet, a script, a support ticket) without first looking up its `entity_id` (UUID) through the API. Nothing in the current surface supports this: `GET /tenants/{tenant_id}/item-instances` only filters by `container_id`/`recursive`.

Adding full-text/name search over item *instances* (as opposed to the base item catalog, addressed separately in [ADR 0047](0047-item-catalog-search-and-container-convention.md)) would be a heavier feature for a narrower need - most instances share the base item's name and aren't meaningfully distinguished by it. A short, optional, human-assigned identifier is cheaper and matches what's actually being asked for: "let me name this specific one so I can find it again."

## Decision

`ItemInstanceCreate` gains `slug: str | None = None`; `item_instance` gains a matching nullable `slug` column. Unique per tenant when set - a partial unique index (`ix_item_instance_tenant_id_slug` on `(tenant_id, slug)`, `WHERE slug IS NOT NULL`), not a table-level `UniqueConstraint`, since a bare `UniqueConstraint(slug)` would be tenant-wide rather than per-tenant, and Postgres already treats every `NULL` as distinct from every other `NULL` in an ordinary unique index (the same property [ADR 0028](0028-knowledge-and-group-membership.md)'s `knowledge` table relies on for its own two `UniqueConstraint`s) - the `WHERE` clause is for readability on top of that, not strictly required by it.

`ItemInstanceOut` exposes `slug: str | None`. New `GET /tenants/{tenant_id}/item-instances/by-slug/{slug}` → `ItemInstanceOut`, registered *before* `/{entity_id}` in the router (same routing-order requirement `/owned-by/{owner_entity_id}` already documents in `routers/item_instances.py` - a wildcard path segment registered first would otherwise greedily match `by-slug` as an `entity_id`). `404 ItemInstanceSlugNotFoundError` if no instance in this tenant currently has that slug - non-enumerable, matching every other not-found shape in this router.

No slug-mutation endpoint. `slug` is set once, at creation, like `prototype_id` - `PATCH /item-instances/{id}` stays name-only (unchanged); a caller that needs to rename a slug can be added later if a concrete need for it shows up, matching this codebase's own general preference for not building unrequested write surface ahead of need.

## Not in scope

Making `slug` a general lookup/search key (that's what `by-slug` alone already gives - not extended to partial matching). Slug uniqueness across item *instances and items both* - the two are separate tables, this ADR only touches `item_instance`; a base item and one of its instances could coincidentally share the same slug string with no conflict, which is fine, they're different resources.

## Consequences

- One migration: adds `item_instance.slug` (nullable `Text`) and its partial unique index; drops and recreates `v_item_instance` to select it (`v_item` is untouched - slug is instance-only).
- `models/v_item_instance.py`, `schemas/items.py` (`ItemInstanceCreate.slug`, `ItemInstanceOut.slug`), `routers/item_instances.py` (new `get_item_instance_by_slug` route, `create_item_instance` passing `body.slug` through to the new `ItemInstance` row).
- New typed problem: `ItemInstanceSlugNotFoundError` (404).
- A client authoring or scripting content can now name an instance once at creation and resolve it again later by that name alone, with no need to have persisted its `entity_id` out-of-band.
