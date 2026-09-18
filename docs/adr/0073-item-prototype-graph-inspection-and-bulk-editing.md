# 0073 - Item prototype graph inspection and bulk editing

Status: accepted

## Context

[ADR 0072](0072-item-catalog-prototype-set-editing.md) gave a catalog item's prototype set a single-item, full-replace `PUT`, and flagged several related needs as real but deliberately deferred: browsing what's built on top of a given prototype, seeing a full ancestry chain, restructuring the catalog by inserting a new intermediate type across many items at once ("push a prototype up the chain"), and applying/removing one prototype across a GM-picked batch of items. This ADR picks up exactly those four, narrowed the same way ADR 0072 narrowed its own scope: catalog items only, building on the primitives ADR 0072/RFC 0005/ADR 0032 already established rather than waiting on a hypothetical generic entity-graph API.

## Decision

### `GET /tenants/{tenant_id}/items?prototype_id={id}&recursive={bool}` - reverse lookup

Extends the existing `list_items` (already has `q`). `prototype_id` filters to items that have it as a prototype; `recursive=false` (default) means direct only, `recursive=true` walks the full descendant tree - the identical default/opt-in shape `GET /item-instances?container_id=&recursive=` already established for containment (ADR 0065). `prototype_id` is validated to resolve to a real entity in this tenant up front (`get_entity_or_404`, matching that same route's own `container_id` validation) - a cross-tenant probe 404s exactly like an unknown id. `recursive` without `prototype_id` is a no-op, not an error - same treatment `container_id`'s own `recursive` gets.

Direct lookup is a plain join against `EntityPrototype`. Recursive lookup needs a new CTE, `_prototype_descendants_cte` - **not** a reuse of `entity_access.py`'s `recursive_descendants_cte`: that one walks `Containment`, a semantically unrelated graph, and existing precedent (`campaign_access`/`information_visibility`/`entity_access` all staying separate, focused modules) argues against forcing a shared abstraction across two unrelated relations just because both happen to be recursive. Kept private to `routers/items.py` for now - nothing else needs a prototype-graph walk yet, and a shared module can be extracted later if that changes, matching this codebase's general "don't generalize before a second real caller exists" practice.

### `GET /tenants/{tenant_id}/items/{entity_id}/prototypes/ancestry` - full ancestry

Returns every transitive ancestor (direct and indirect prototypes), not just the direct set `ItemOut.prototype_ids` already exposes. Each entry is a lightweight `PrototypeAncestorOut{entity_id, name, prototype_ids}` - `prototype_ids` here is that ancestor's own *direct* prototypes (always a subset of the full returned ancestor set, by definition of "ancestor") - not a full `ItemOut`, since a UI rendering a breadcrumb/graph doesn't need stats/descriptions/pictures, just enough structure to lay the graph out itself. Deliberately a flat list of nodes-with-their-own-edges, not a pre-built tree: multiple inheritance means this is a DAG, not always a clean chain (`Longsword` could inherit from both `Sword` and a separate `Masterwork` type) - handing back a flat node+edge list lets the client render whatever shape actually exists instead of this endpoint silently lying about branching by forcing a linear breadcrumb. Not paginated - prototype graphs are shallow by construction (ADR 0015's own observation), the same "bounded, no pagination needed" reasoning `OwnedByResponse` already uses.

### Both walks use plain `UNION`, not `entity_access.py`'s path-array cycle guard

`entity_access.py`'s containment walk needs a path array because `Containment` can legitimately cycle (ADR 0016). `entity_prototype` cannot - its own `BEFORE INSERT` trigger (ADR 0015) already guarantees an acyclic graph, and [ADR 0072](0072-item-catalog-prototype-set-editing.md) is the only write path able to reach that trigger's rejection at all. Multiple inheritance still means diamonds are possible (the same ancestor reachable via two different parents), so a plain recursive CTE needs *some* de-duplication - `UNION` (not `UNION ALL`) gives it for free, and is exactly the technique `entity_prototype`'s own cycle-check trigger already uses for its ancestor walk (see the migration's `entity_prototype_reject_cycles` function) - these two new CTEs are that same query, generalized to start from an arbitrary entity instead of a candidate new edge.

### `POST /tenants/{tenant_id}/items/bulk-reparent-prototype`

Body: `BulkReparentPrototypeRequest{from_prototype_id, to_prototype_id, item_ids: list[uuid.UUID] | None = None}`. For every affected item that currently has `from_prototype_id` as a direct prototype, replaces that edge with `to_prototype_id`. `item_ids` omitted means "every item with `from_prototype_id` as a direct prototype" (resolved via a query, restricted to `Item`-typed entities); given explicitly, an item that turns out not to currently have `from_prototype_id` is a tolerated no-op for that item, not an error - matching `bulk-move`'s own "resolving to zero/nothing-to-do is fine" tolerance, so a client can safely retry or over-specify without needing to pre-check current state. `from_prototype_id != to_prototype_id` is a body-shape invariant, checked via a Pydantic `model_validator` (plain 422), the same treatment `BulkMoveContainerRequest`'s own exactly-one-of check already gets - not a typed `Problem`, since it depends on nothing in the database. Both ids are validated to resolve to real entities up front, once (422 `InvalidPrototypeError`, reused from ADR 0072) - they don't vary per item, the same "check once, not per item" reasoning ADR 0062/0065 already established for their own shared destination checks.

Per item: never-all-or-nothing, `session.begin_nested()` + caught `Problem` -> that item's own `"error"` entry, the same pattern `bulk-assign`/`bulk-move` already use. A self-loop (an item equal to `to_prototype_id`) or a transitive cycle (caught from the DB trigger's `DBAPIError`, same translation ADR 0072's single-item `PUT` already does) becomes that item's own `EntityPrototypeCycleError`, not a batch-wide failure.

**No `link_to_from` auto-linking.** An earlier sketch of this ADR considered automatically also linking `to_prototype_id -> from_prototype_id` (so "pushing a prototype up the chain" changes structure but not resolved stats by default) - dropped once the natural two-call workflow turned out to already give the identical result with less machinery: `POST /items` to create the new intermediate type with `prototype_ids: [from_prototype_id]` already sets up exactly that inheritance at creation time, *then* `bulk-reparent-prototype` moves the leaf items onto it. Same "compose existing primitives instead of adding a special-cased flag" reasoning ADR 0072 already used for "splicing."

### `POST /tenants/{tenant_id}/items/bulk-add-prototype` / `POST /tenants/{tenant_id}/items/bulk-remove-prototype`

Bodies: `BulkAddPrototypeRequest`/`BulkRemovePrototypeRequest{prototype_id, item_ids: list[uuid.UUID]}` (required list here - unlike `bulk-reparent-prototype`, there's no coherent "all items in the tenant" default for "add this prototype everywhere"). Delta operations, not full-replace: adding an already-present edge, or removing an already-absent one, is a tolerated no-op ("ok", nothing changed) rather than an error - the point of a delta API over the single-item full-replace `PUT` is exactly that a client tagging a GM-picked batch of items doesn't need to already know each item's current full prototype set first. `prototype_id` validated to resolve to a real entity up front, once (422 `InvalidPrototypeError`) - a typo'd id should surface clearly rather than silently no-op across the whole batch.

`bulk-add-prototype` needs the same per-item self-loop/cycle handling as `bulk-reparent-prototype` (an added edge can create a cycle; caught the same way). `bulk-remove-prototype` cannot - removing an edge can never create one, so there's no `DBAPIError` translation needed there.

**Attribution is conditional here, unlike `PUT .../prototypes`'s unconditional bump (ADR 0072).** The single-item `PUT` always stamps `updated_by`/`updated_at` because it's a declarative "this is the new state" - even a no-op replace is still an explicit re-assertion. These two bulk endpoints are phrased as "ensure this edge is present/absent," an idempotent check-then-act - only bumping attribution when the edge actually changed keeps `updated_at` meaningful (a batch re-run that changes nothing shouldn't look like every item was just touched).

### No `If-Match` on any of the three new bulk endpoints

`bulk-assign`/`bulk-move`'s own per-item `if_match` exists because those mutate ownership/containment - physical state players can genuinely race to claim. Prototype-graph bulk-editing is a catalog-authoring operation, not a "who gets there first" race; the added request-shape complexity (bare `uuid.UUID` list becoming a list of `{entity_id, if_match}` objects) isn't clearly justified by a risk this operation doesn't really have. Revisit if that assumption turns out wrong in practice.

## Not in scope

**"Splicing" a prototype into the middle of a chain, and the un-flagged form of "pushing a prototype up the chain"** - both already fully expressible by composing `POST /items` with either `PUT .../prototypes` (splice, one item) or `bulk-reparent-prototype` (push-up, many items) - see the `link_to_from` discussion above for why no dedicated flag/endpoint was added for the latter.

**Bulk catalog import/create** - still a content-authoring-tooling concern, not a prototype-graph-editing one, per ADR 0072's own "considered, not pitched" note.

**Optimistic concurrency (`If-Match`) on the three new bulk endpoints** - decided against above, not merely unaddressed.

**Extending any of this to `ItemInstance`'s own direct prototype** - same scoping ADR 0072 already gave: this is catalog-item work.

## Consequences

- No migration - `entity`/`entity_prototype`/`item` all already exist.
- No new typed problems - `InvalidPrototypeError`/`EntityPrototypeCycleError` (ADR 0072) cover every guard condition these four endpoints need.
- `schemas/items.py` gains `PrototypeAncestorOut`, `BulkReparentPrototypeRequest`/`BulkReparentResultItem`, `BulkAddPrototypeRequest`/`BulkAddPrototypeResultItem`, `BulkRemovePrototypeRequest`/`BulkRemovePrototypeResultItem`.
- `routers/items.py` gains `_prototype_descendants_cte`/`_prototype_ancestors_cte`, `list_items`'s `prototype_id`/`recursive` params, `get_item_prototype_ancestry`, `bulk_reparent_item_prototype`, `bulk_add_item_prototype`, `bulk_remove_item_prototype`. `_item_out` gains an optional `response` parameter (`Response | None`), mirroring `routers/item_instances.py`'s own `_item_instance_out` - the new bulk routes' per-item results have no single response to attach an `ETag` to.
- A GM can now browse "everything built on Weapon," see a full ancestry chain for a UI breadcrumb/graph, restructure the catalog by inserting a new intermediate type across many items in one call, and tag/untag a picked batch of items with a shared prototype - all four gaps ADR 0072 flagged as real future candidates, closed.
