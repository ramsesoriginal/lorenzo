# 0104 - Computed stats: linear and comparison formulas

Status: accepted

## Context

Accepts [RFC 0016](../rfcs/0016-stats-computed-values-and-crud-api.md) sub-slices 4 and 5. [ADR 0103](0103-stat-tags-enum-values-and-mandatory-groups.md) took sub-slices 1 to 3. The RFC already chose the representation after a four-way debate: curated formula *kinds*, each a parameterized call into reviewed code, with no expression language or interpreter anywhere. When one kind isn't enough, formulas are chained through named intermediate stats rather than nested. This ADR builds the two kinds the RFC named, fits them into resolution, and adds the authoring checks the RFC called load-bearing for non-technical authors.

The motivating bug: a D&D ability modifier is `floor((score - 10) / 2)`. Truncating instead gives `0` for a score of 9 where the right answer is `-1`. The rounding mode has to be an explicit parameter.

## Decision

### Schema (one migration)

Every table has `tenant_id` and the standard `tenant_isolation` policy with `FORCE ROW LEVEL SECURITY`.

- **`computed_stat(entity_id, stat_definition_id, tenant_id, created_at, updated_at)`**: primary key `(entity_id, stat_definition_id)`, the same address as `entity_stat`. It carries no kind column; which concrete table has the matching row is the kind, as with `payload` ([ADR 0017](0017-information-and-payloads.md)).
- **`computed_stat_linear`** (same key, cascading from `computed_stat`) has these columns:
  - `source_stat_definition_id`
  - `multiplier` and `offset` (`NUMERIC`)
  - `round_mode`: `none`, `floor`, `ceil`, `round` (half away from zero), or `truncate` (toward zero)

  The result is `round(source × multiplier + offset)`, so the D&D modifier is `strength × 0.5 − 5` with `floor`.
- **`computed_stat_comparison`** (same key) has these columns:
  - `left_stat_definition_id`
  - `comparator`: `lt`, `le`, `eq`, `ne`, `ge`, or `gt`
  - the right side, which is exactly one of `right_stat_definition_id` or `right_constant` (`NUMERIC`), enforced by a `CHECK`
  - `true_value`/`false_value` (text, nullable)

  The result is `true`/`false` when the target stat is `bool`. For a `text` or `enum` target it is `true_value` or `false_value`: "heavy"/"light", or "overloaded"/"fine".
- Source-stat foreign keys don't cascade (`NO ACTION`): a stat definition a formula reads can't be deleted out from under it (there is no stat-definition delete route today anyway). `NO ACTION` rather than `RESTRICT`, so deleting a whole tenant, which removes both in one statement, still works.

### Types, checked at write time (422)

- **Linear.** Source and target must be `int` or `float`. An `int` target needs a `round_mode` other than `none`.
- **Comparison.** Exactly one right side, a stat or a constant (also a database `CHECK`). Left and right operands must be `int` or `float`. The target must be `bool`, `text`, or `enum`. `text`/`enum` targets need both result values, and for `enum` both must be allowed values. `bool` targets take neither.
- **No stat reads itself.**

### Resolution

`v_effective_stat` ([ADR 0039](0039-generic-effective-stat-view.md)) now considers `computed_stat` rows alongside `entity_stat` rows at every hop. The rule is ADR 0037's, unchanged: the closest hop wins outright. At the same hop a direct value beats a formula, which only matters for rows inserted around the API, since the API never allows both on one entity (below). A winning formula comes out as a row with every `value_*` column null and a new `computed_entity_id` column naming the ancestor that holds it. Stored winners have `computed_entity_id` null.

A Python pass (`stat_evaluation.py`) then fills in values, in dependency order, against **the resolved stats of the entity being read**, not of the ancestor that holds the formula. A prototype's `strength_modifier` formula therefore uses each instance's own strength. A computed stat whose inputs don't resolve (missing, or itself unresolvable) produces no value, exactly like an unset stat. The pass never raises for bad data: a cycle that slipped past the write-time check leaves the stats involved without a value rather than failing the read.

Every Python reader of effective stats goes through this pass:

- `GET /entities/{id}`'s `stats`.
- `EntityViewMixin`'s stat groups and tags (`ItemOut`/`ItemInstanceOut`/character views).
- The eight named `ItemOut`/`ItemInstanceOut` columns (`weight`, `price`, ...). These still come from `v_item`/`v_item_instance` in SQL, so the schema fills a computed one in from the evaluated bundle when the SQL column is null.

SQL-only consumers see the stored value only. Today that's `v_item`/`v_item_instance` queried directly, as in list filters and ordering.

### Write surface

Tenant-admin tier, like the rest of stat definitions (`get_tenant_context`). Authoring a formula defines what a stat *means*; it isn't a per-character edit. RFC 0016 expects a future repository-author role to take this over.

- **`PUT /tenants/{tenant_id}/entities/{entity_id}/computed-stats/{stat_definition_id}`**: create or replace the formula, with a `kind`-discriminated body (`linear`/`comparison`). `If-Match` is checked against `computed_stat.updated_at` on replace. Returns `ComputedStatOut` plus `ETag`. This route replaces the RFC's `POST`+`PATCH` pair, because the stat definition in the path already addresses the row. It also doesn't create a stat definition by name: the definition must already exist (`POST /stat-definitions`), which keeps one way to create a definition.
- **`DELETE`** on the same path: `204`, with `If-Match`.
- **`GET /tenants/{tenant_id}/entities/{entity_id}/computed-stats`**: the formulas this entity holds itself (not inherited ones).
- **One formula or one direct value per entity and stat.** Setting a formula where the entity has a direct value returns `409`, and so does the reverse: the stat `PUT`, and ADR 0103's tag `PUT`/`PATCH`. Clearing the other first is explicit, never implicit.
- **Cycle check.** The graph is tenant-wide at the *definition* level: an edge from each formula's target to each stat it reads, across every entity in the tenant. A write that would close a cycle is rejected with `422` naming the path. This is conservative: two formulas on unrelated entities can't form a runtime cycle but would still be rejected. It is also sound, since any runtime cycle needs a definition-level cycle. It is a separate graph from `entity_prototype`'s, which keeps its own trigger ([ADR 0015](0015-entity-prototype.md)); the two checks share no code.
- **Dry-run preview: `POST /tenants/{tenant_id}/entities/{entity_id}/computed-stats/{stat_definition_id}/preview`.** It takes an optional formula body. With a body, it runs every write-time check (types, cycles, the direct-value conflict) and evaluates that unsaved formula against this entity. Without one, it evaluates the formula that currently resolves for this stat. It returns the result and the input values used, and writes nothing.
- **Reverse lookup: `GET /tenants/{tenant_id}/stat-definitions/{stat_definition_id}/dependents`.** Every formula in the tenant that reads this stat, as `{entity_id, stat_definition_id, kind}`. This follows the precedent of [ADR 0073](0073-item-prototype-graph-inspection-and-bulk-editing.md)'s prototype reverse lookup.
- **Activity log.** Formula create, replace, and delete are logged as `computed_stat.set`/`computed_stat.deleted`, with ids only (ADR 0084: a formula changes what a stat means for every entity inheriting it, closer to a stat definition than a stat value). Previews and reads aren't logged.

## Not in scope

- More kinds, cross-entity aggregation ("the weight of everything in this bag"), and game-system scoping, all excluded by RFC 0016 itself.
- The unified stat bundle endpoint with per-field provenance (sub-slice 6). Until then a client can tell a computed value from a stored one only through `GET .../computed-stats` on the entity and its prototypes.
- Caching or materializing computed values. Evaluation is live on every read, like `v_effective_stat` itself.
- Creating a stat definition from the formula route by name (see Write surface).

## Consequences

- `v_effective_stat` is a live view every stat read passes through. Changing it touches every entity, which is the main risk of this slice. The migration keeps each existing column and its meaning for stored winners; the only additions are the `computed_entity_id` column and rows whose value columns are null. `EntityStatValueOut` and every Python consumer were updated in the same change, and the existing resolution tests still pass unchanged.
- Correctness now depends on Python code, not just SQL, whenever a formula wins. A consumer that reads `v_effective_stat`'s value columns without the evaluation pass sees null for a computed stat.
- The definition-level cycle check can reject a harmless formula. Loosening it to an entity-aware check is possible later without a schema change.
