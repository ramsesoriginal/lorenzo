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
- **The statements of an item read** are the addendum below.

## Tests

`apps/api/tests/test_stat_views_per_entity.py`:

- The views return the rows they returned before: a generated library (parents in orders of their own, stats, formulas, groups with priorities) compared in both directions with the previous definitions of `v_effective_stat`, `v_item` and `v_item_instance`, kept in the test as the reference. Before the change was written the same comparison was made on libraries of 400 to 3,000 entities and up to 6,823 rows, with no difference.
- A read of one entity walks that entity and not the library: the plan of `SELECT ... WHERE entity_id = ...` over 300 unrelated entries produces at most ten rows in its recursive walks (306 for `v_effective_stat` and 1,836 for `v_item` with the previous definitions).
- The app role runs without JIT.

## Addendum (2026-10-13): the statements of an item read

With the views fixed, a read of one catalog item through the route (the caller's identity supplied, so without the per-request user upsert) was 31 statements and 36.5 ms for an owner, 47 and 54.4 ms for an owner who also GMs a campaign (three characters), and 32 and 36.3 ms for a player. A statement costs about 1.1 ms all in (a bare `SELECT 1` through the same stack is 0.25 ms; the rest is the ORM's work on each result), and the GM's reach alone was 16 statements and 18 ms.

- **A to-one relationship loads with the row that has it.** `VItem.entity` (and `VItemInstance.entity`), `Entity.item`, `Payload.description` and `Payload.picture`, `VEffectiveStat.stat_definition` and `StatDefinition.stat_group` are joined into their parent's query, six statements fewer. The collections (information, payloads, knowledge links, effective stats, containment, parents) stay separate selects: a join of several would multiply their rows.
- **The prototype chain is one recursive query.** `prototype_ancestors` walks `entity_prototype` once, whatever the depth, keeps a row per (entity, ancestor, distance), takes each ancestor at its shortest distance and joins the entities to it; it used to ask for the edges one level at a time and then for the entities. The order of the answer (nearest first, then name, then id) is the same.
- **Who may read is resolved after the rows are, and only as far as `can_see` needs** (`resolve_information_reader`). When every row the answer may show (the item's and its ancestors') is public, nothing is resolved: `can_see` is true of a public row for anyone. For an admin, who `can_see` everything, only their tier is (their Membership and the opt-out check, which suppresses the bypass). Anyone else, with a row that is not public among them, gets `resolve_information_visibility` as before. The catalog item routes use it; they ask nothing of the caller's sight but `can_see`. The item-instance routes, beings and the export use the sets that the full resolve returns (the GM's reach narrows the inventory tier, ADR 0040), so they still resolve it.

Measured the same way, with the Postgres and the tests pinned to four cores:

| Caller | Before | After |
| --- | --- | --- |
| Owner | 31 statements, 36.5 ms | 15 statements, 19.7 ms |
| Owner who also GMs | 47 statements, 54.4 ms | 15 statements, 20.4 ms |
| Player of a public item | 32 statements, 36.3 ms | 16 statements, 21.3 ms |

- **Not changed:** a caller who is not an admin and reads a row that is not public (a campaign GM reading a GM-only note) still resolves their sight in full; resolving the GM's reach only when a row asks for it is the next step. Some lookups are still repeated inside a request (the Membership is read for the participant check and again for the tier, when a row is hidden), and the other routes that read information (entities, item instances, link previews) have not taken the reader yet.

Tests: `apps/api/tests/test_item_read_statements.py` holds the counts for the three callers (with room for a few statements, so that they fail when the old work returns and not when a statement is added), and that an owner reads a private description of an ancestor and a player does not; `apps/api/tests/test_information_reader.py` the reader itself: nothing resolved for public rows, an admin's tier alone, an owner who opted out and anyone else resolved in full, equal to `resolve_information_visibility`.

## Addendum (2026-10-14): the write routes

A write answers with the row it wrote, and its dependencies and access checks ask the database for what an earlier one in the same request already asked: with the item read at 15 statements, the writes were the larger part of what the API costs (an end-to-end suite spends about 72% of its API time on writes that build a world). Measured as an owner who also GMs a campaign (three characters), warm, through the route with the caller's identity supplied:

| Route | Before | After |
| --- | --- | --- |
| `GET /entities/{id}` | 50 statements, 60.2 ms | 15, 24.6 ms |
| `PUT /entities/{id}/tags/{stat}` | 58, 61.1 ms | 22, 29.4 ms |
| `PUT /entities/{id}/stats/{stat}` | 59, 63.6 ms | 23, 29.1 ms |
| `POST /item-instances` (owned) | 52, 57.6 ms | 29, 33.3 ms |
| `POST /entities/{id}/information` | 22, 21.6 ms | 17, 18.0 ms |
| `POST /items` | 19, 26.3 ms | 19, 26.3 ms |
| `POST /stat-definitions` | 10, 13.3 ms | 10, 13.3 ms |

- **The response of an entity takes the reader.** `entity_detail_out` (the entity's own route, the tag and stat routes through `entity_stats`, and the item-instance responses) resolves who may read with `resolve_information_reader`, as the item read does, instead of resolving the caller's sight in full for every response; the to-one relationships of the entity's detail are joined into its query. The two checks of an information write (`information_out_or_404` with `require_visible`, and `authorize_information_edit`) ask the same of one row and take the same reader. The to-one relationships of an information's payloads and author are joined as well, and an instance response resolves the reader for the rows of the instance and its ancestors, whose chain it already had.
- **The tenant and the caller's membership are read once per request.** A session's identity map holds an object only for as long as something else does, so `session.get(Tenant, id)` and `session.get(Membership, ...)` in the tenant dependency, the participant check, the tier of the reader and the item routes each went back to the database. `db.hold` keeps what a request has read alive for the rest of it (in the session's `info`), `campaign_access.membership_of` is the one way to read a membership and holds it, and the tenant dependencies hold the tenant. The session is the request's own and ends with it.
- **Not changed:** `POST /items` and `POST /stat-definitions` are already few statements and their remainder is the write itself (the row, its links, the activity log, the response). The per-request user upsert (ADR 0023) is untouched. A non-admin campaign GM still resolves their reach for rows that are not public; the item-instance reads and lists, link previews and the export have not taken the reader.
- **A held row can be stale within its own request.** What is held is what the request read first, and the identity map answers for a row the session itself changed or deleted, as it did before; a membership or tenant changed by another transaction while a request runs is not seen by that request after its first read. A request is milliseconds long and its tenant context (RLS) is fixed at its start anyway.

Tests: `apps/api/tests/test_write_route_statements.py` holds the counts of the five routes above that changed, with room for a few statements, and that a membership read twice in a session is one statement. What the answers show is unchanged and is covered by the information visibility, item, item-instance and entity tests of the suite.
