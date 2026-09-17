# 0066 - `is_container` as a computed field, mirroring the tag

Status: accepted

## Context

[ADR 0047](0047-item-catalog-search-and-container-convention.md) established container-capability as a documented convention, not a schema addition: a tenant defines a boolean `stat_definition` named `is_container` in the `tags` stat group, and it surfaces through the existing generic `tags` array `ItemOut`/`ItemInstanceOut` already expose - explicitly *not* a dedicated field, to avoid the migration `is_magical`/`is_cursed`'s own hardcoded whitelist in `v_item`'s `CREATE VIEW` SQL needed ([ADR 0037](0037-effective-stat-resolution.md)/[0039](0039-generic-effective-stat-view.md)).

Asked directly for a real `is_container` field on `ItemOut` in addition to the tag - a client shouldn't have to search a generic `tags` array by name for something this common - and, further, for a fallback: if no tag value is set at all, infer the field from whether the item structurally contains anything right now. The constraint from ADR 0047 still holds: no migration, no new hardcoded `v_item`/`v_item_instance` column.

## Decision

`ItemOut` (inherited by `ItemInstanceOut`) gains `is_container: bool | None`, computed by `schemas/items.py`'s new `_is_container_out`. Not a new SQL column, not a new `stat_definition`, not a new whitelist entry in `v_item`'s `CREATE VIEW` SQL the way `is_magical`/`is_cursed` are (ADR 0037/0039) - two existing, already-available signals only:

1. The `"is_container"`-named entry already present in `view.tags` (`EntityViewMixin.tags`, the same resolved, prototype-inheriting property `_tags_out` already wraps unchanged) - an explicit tag value, `True` or `False`, always wins. Authorial intent over structural inference: a tenant who explicitly marked something `is_container: false` meant that, even if it happens to structurally contain something for an unrelated reason (a decoration glued on, say) - this ADR doesn't second-guess that call.
2. Only when no `is_container` tag entry exists at all does `Entity.contained_links` (ADR 0041's association-object containment list, the `parent_entity_id` side - already used by `EntityDetailOut.children`) get a say: `True` if this entity currently has at least one row there (something really is contained in it right now), otherwise still `None`. A container that's simply empty at the moment is indistinguishable from "we don't know" under this heuristic, so it deliberately stays unset rather than being inferred `False` - inferring "definitely not a container" from mere emptiness would be a much stronger, less defensible claim than inferring "probably is one" from actual contents.

The tag entry itself stays in `tags` too, unchanged either way - a client reading the generic array keeps working exactly as before; only the new field adds the structural fallback on top.

If a tenant somehow defines more than one `stat_definition` named `is_container` within the `tags` group (not prevented by anything today - `stat_definition.name` isn't unique), the first match in `tags`' own order wins - the same "duplicate tag names" looseness `tags` already has for any other name, not a new gap this ADR introduces or resolves.

### Eager-loading `Entity.contained_links`

`routers/items.py`'s shared `eager_load_options()` (already reused by `routers/item_instances.py`) gains a fifth option, `selectinload(view_entity_attr).selectinload(Entity.contained_links)` - `contained_links` is `lazy="raise_on_sql"` like every other relationship this recipe already loads around, so skipping it would raise `MissingGreenlet` the moment `_is_container_out` touched it, not silently lazy-load. One additional bulk `SELECT` per page of items/item-instances, the same cost shape every other relationship in this recipe already has - not a per-row N+1.

## Not in scope

Promoting `is_container` into `v_item`/`v_item_instance`'s hardcoded `is_magical`/`is_cursed`-style whitelist - still deliberately avoided, per ADR 0047's original migration-avoidance reasoning; this ADR only adds a computed, no-migration mirror (plus a structural fallback) on top of the existing tag; the underlying storage mechanism (a tenant-defined `tags`-group `stat_definition`) is unchanged. A recursive "contains anything anywhere inside it, not just directly" fallback - direct `Containment` rows only, matching this codebase's general "explicit/direct over implicit/recursive by default" preference (e.g. `GET /item-instances?container_id=`'s own non-recursive default). Mirroring any other tag name into its own dedicated field, or giving any other tag a structural fallback - not asked for, scoped to `is_container` alone.

## Consequences

- `schemas/items.py`: `ItemOut.is_container: bool | None`; `_common_item_fields` computes it via the new `_is_container_out(view.tags, has_children=bool(view.entity.contained_links))`; `ItemInstanceOut` inherits it for free, identical to every other `ItemOut` field.
- `routers/items.py`'s `eager_load_options()` gains the `Entity.contained_links` load described above - its return type widens from a 4-tuple to a 5-tuple of `ORMOption`; every existing call site already unpacks it with `*`, so no call site itself changes.
- No model or migration changes.
- ADR 0047's own "no dedicated field" decision is partially superseded here - the underlying "no migration, tag-based" storage convention it established stands unchanged, only its "surfaced only through `tags`, no separate field" half is revised.
- A client can now read `item.is_container` directly instead of scanning `tags` for the name, and gets a reasonable default even for an item a tenant never explicitly tagged at all, as long as it's actually holding something right now; anything already reading `tags` generically is unaffected.
