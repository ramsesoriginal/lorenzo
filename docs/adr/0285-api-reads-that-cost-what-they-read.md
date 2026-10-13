# 0285 - API reads that cost what they read

Status: accepted

## Context

A profile of the end-to-end suites ([ADR 0148](0148-dependency-aware-pr-ci.md), addendum of 2026-10-08) found that a read of one item runs 48 SQL statements for a GM and that the time of such a read is not in those statements alone. Replaying the statements as the app role with row-level security set (`EXPLAIN (ANALYZE)`) found two causes of cost that grow with the size of the library and not with what is read:

- **`v_effective_stat` walked the whole tenant to answer for one entity.** Its recursive walk started from every entity (`FROM entity` is the anchor), and a filter on `entity_id` is applied after the walk: Postgres cannot push a filter into a recursive CTE. `v_item` and `v_item_instance` joined that view once for each of the six stats they carry, so one item read ran six walks of the whole library. The same holds for everything that reads the view with `entity_id IN (...)`: the `effective_stats` of every entity read, binding, capacity and the computed stats routes.
- **JIT compiled the result.** The six walks give the planner an estimated cost far above `jit_above_cost` (100,000), and past it Postgres compiles the query with LLVM before every execution; past 500,000 it optimises the compiled code too. The queries of this API are short and many, and compiling them cost more than running them.

Measured on one entity of a library of generated entries (a random acyclic graph of parents, stats, formulas and groups), as the app role with row-level security on, warm, one read at a time:

| Entities in the tenant | `v_item`, JIT on | `v_item`, JIT off | `v_effective_stat`, JIT on / off |
| --- | --- | --- | --- |
| 3,000 | 194-222 ms | 69-74 ms | 14-19 / 13-15 ms |
| 5,000 | 228-244 ms | 88-94 ms | 16-17 / 14-16 ms |
| 20,000 | 1,800-1,930 ms | 170-190 ms | 305-340 / 29-31 ms |

In a library of 13 entries (the end-to-end world) the same read is 10-15 ms (4-7 ms to plan, 6-8 ms to run), nearly all of it the six copies. A library of that size is what the tests build, so CI did not show any of this; a real one can be far larger.

## Decision

- **The app role runs with `jit = off`.** A migration sets it on the role the app connects as (`ALTER ROLE ... SET jit = off`), the role `database_url` names, as the migration that created it ([ADR 0021](0021-restricted-app-role-for-rls-enforcement.md)) does. It is a setting of the role and not of the connection because a pooler in front of the database refuses a startup parameter it does not know, whereas the server applies a role's own settings itself. A session that wants JIT can still `SET jit = on`.
- **`v_effective_stat` resolves per entity.** The walk is a lateral subquery anchored on the entity it belongs to (`SELECT e.id` as its first step instead of `FROM entity`), so a filter on the entity is a filter on where the walk starts and a read costs what the length of the entity's prototype chain costs, whatever the size of the library. Each ancestor's stored values, formulas and group priority are looked up by the ancestor instead of aggregated over the tenant first.
- **`v_item` and `v_item_instance` take their six stats from one walk per row**, a lateral subquery that pivots the stats they carry (`MAX(value_int) FILTER (WHERE name = ...)`), instead of one join of the view per stat.
- **The rule that picks a stat is not changed.** The same winner per (entity, definition) by the same order: distance, a stored value before a formula, group priority, then parent order and id ([ADR 0037](0037-effective-stat-resolution.md), [0039](0039-generic-effective-stat-view.md), [0266](0266-stat-tie-break-by-parent-order.md), [0276](0276-where-a-stat-value-comes-from.md)). The columns, their types and their order are the same, so nothing built on the views changes and the migration can put the previous definitions back.

## Alternatives considered

- **A closure table of every entity's ancestors,** kept by triggers on `entity_prototype`. It would make the views plain joins, but it is a tenant table (row-level security, `copyable_tables.py`, repository copies and attachments all have to handle it), every change of a parent has to recompute the ancestors of everything below it, and it is a second copy of what `entity_prototype` already says.
- **A set-returning function of a list of entities.** The ORM's relationship loaders select from the view with `entity_id IN (...)`; they cannot call a function, so every route that loads `effective_stats` would have had to change. A view with a lateral walk keeps every caller as it is.
- **Six scalar subqueries in `v_item`** (Postgres defers expensive select-list expressions until after a `LIMIT`): it does the same walk six times for every row it does evaluate, so it costs several times what one pivoted walk does for a single read, to help a page of a list that is still slow.
- **An index on `entity (tenant_id, name, id)`** to let a name-ordered page stop early: tried, the planner did not use it (the joins deliver rows in id order).
- **Fixing only `v_item`.** The same walk was behind every other read of `v_effective_stat`.

## Consequences

Measured as above, with the new views (JIT on or off; it no longer matters): one entity is 0.2-0.6 ms at 3,000, 5,000 and 20,000 entities, for `v_effective_stat` and for `v_item`. At 20,000 entities, through the statements the list route sends:

| Statement | Before (JIT on / off) | After (JIT on / off) |
| --- | --- | --- |
| One item (`v_item`, one entity) | 1,800-1,930 / 170-190 ms | 0.3-0.6 ms |
| The list's `count(*)` | 2,700-3,000 / 900-970 ms | 23-25 ms |
| A page of 100, ordered by name | 2,950-3,600 / 960-980 ms | 1,000-1,020 / 670-800 ms |
| Every stat of the tenant (`v_effective_stat`) | 430-530 / 160-180 ms | 380-430 / 200 ms |

- **A page of a list is still slow.** It sorts by name and the entry's own columns are not an ordered input, so Postgres runs the per-row walk for every entry of the tenant before it sorts and limits (about 35 microseconds each). It is cheaper than before and not cheap; computing a page's ids first and joining the view for those only is a change to the list routes and is left for them.
- **A read of every stat of a tenant costs what it did** (a walk per entity instead of one walk of all), so a full export is neither faster nor slower.
- **The walk still enumerates paths,** not distinct ancestors: an entry with several parents that share ancestors walks each path. Chains are short and parents few in libraries; a dense graph of parents is the one thing that would make a read expensive, as it did before.
- **The role setting is the server's, not the database's.** `ALTER ROLE ... SET` applies to the role in every database of the cluster, so downgrading the migration in one database resets it for all of them, and the test that checks it fails in the others until the migration is applied again.
- **Not done here:** the statements of an item read that no view change removes (the eager loads of to-one relationships, information visibility resolved even when everything read is public or the caller is an admin, the prototype chain of an item's description), tracked in the same milestone.

## Tests

`apps/api/tests/test_stat_views_per_entity.py`:

- The views return the rows they returned before: a generated library (parents in orders of their own, stats, formulas, groups with priorities) compared in both directions with the previous definitions of `v_effective_stat`, `v_item` and `v_item_instance`, kept in the test as the reference. Before the change was written the same comparison was made on libraries of 400 to 3,000 entities and up to 6,823 rows, with no difference.
- A read of one entity walks that entity and not the library: the plan of `SELECT ... WHERE entity_id = ...` over 300 unrelated entries produces at most ten rows in its recursive walks (306 for `v_effective_stat` and 1,836 for `v_item` with the previous definitions).
- The app role runs without JIT.
