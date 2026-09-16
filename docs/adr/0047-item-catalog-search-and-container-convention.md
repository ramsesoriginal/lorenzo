# 0047 - Item catalog search and container-capability convention

Status: accepted

## Context

Two small, independent gaps in the item catalog surface, bundled into one ADR since neither needs a schema change:

1. `GET /tenants/{tenant_id}/items` supports only `page`/`size` - a client offering "find an item by name" has to page through the entire catalog client-side.
2. Nothing in `ItemOut`/`ItemInstanceOut` indicates whether an item is meant to be usable as a container for other items - containment is purely structural (any entity may contain any other, [ADR 0016](0016-containment.md)), so a client has no authoritative way to offer "pick one of your container-capable items" without guessing from names.

## Decision

### Catalog search: `q` query parameter

`GET /tenants/{tenant_id}/items?q=...` - optional `q: str | None`, case-insensitive `ILIKE` against `Entity.name` (joined off `VItem.entity`), not `VItem.title`. `title` is a nullable, description-payload-sourced display field ([ADR 0019](0019-item-and-v-item.md)); `Entity.name` is the item's own stable, always-set identifier and the right search target - searching `title` would silently miss any item whose public description hasn't been authored yet.

### Container-capability: no field, no migration - a tag convention

`is_magical`/`is_cursed` are hardcoded named columns baked directly into `v_item`'s `CREATE VIEW` SQL ([ADR 0037](0037-effective-stat-resolution.md)/[0039](0039-generic-effective-stat-view.md)) - a small, curated, migration-gated whitelist. Adding `is_container` the same way would mean a migration for what is, functionally, just another homebrew boolean fact about an item. The *generic* `tags` array already on `ItemOut`/`ItemInstanceOut` surfaces **any other** boolean `stat_definition` a tenant defines, with zero code changes - exactly the mechanism this need already fits.

Decision: no new field. The documented convention is that a tenant marks an item container-capable by defining a boolean `stat_definition` named `is_container` (a suggested, not enforced, name - `stat_definition` rows are already fully tenant-authored via the existing stat CRUD API, [ADR 0037](0037-effective-stat-resolution.md), nothing here is seeded automatically) and setting it on the item or instance; a client reads it back from the existing `tags` array, identical to any other tenant-defined boolean tag.

## Not in scope

Full-text/fuzzy search, or extending `q` to item *instances* (that's [ADR 0043](0043-item-instance-slug.md)'s slug lookup instead, a different need - naming a specific instance, not searching a catalog). A dedicated `is_container` field or any other first-class container-capability schema - deliberately not built, per the decision above.

## Consequences

- `routers/items.py`: `list_items` gains an optional `q` query parameter; the underlying `select(VItem)` gains `.where(Entity.name.ilike(f"%{q}%"))` when given, requiring `VItem.entity` in the query's join (already present via `eager_load_options`' relationship, reused directly here for the `.join()`/filter condition too).
- No model, schema, or migration changes for the container-capability half - purely a documented convention, verified by confirming the existing `tags` mechanism already covers it with no code changes needed.
