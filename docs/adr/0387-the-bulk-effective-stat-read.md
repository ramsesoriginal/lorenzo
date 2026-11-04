# 0387 - The bulk effective-stat read

Status: accepted, decided with the maintainer on 2026-11-03. Slice K7 of [RFC 0041](../rfcs/0041-entity-kinds-and-author-freedom.md) §7 and its Spike 3, tracked in #975. Builds on [ADR 0215](0215-finding-entries-filters-kinds-and-name-order.md) (the filters), [ADR 0037](0037-effective-stat-resolution.md), [ADR 0039](0039-generic-effective-stat-view.md) and [ADR 0111](0111-inherited-descriptions-and-stat-value-sources.md) (effective stats and where a value comes from), [ADR 0285](0285-api-reads-that-cost-what-they-read.md) (what a read costs) and [ADR 0249](0249-bench-the-table-and-the-compare-grid.md), whose grid is the first reader.

## Context

The effective value of a stat on an entry takes one `GET /entities/{id}` an entry: the lists return four named stat groups, nothing else. Bench's compare grid reads every entry's detail, six at a time, and says "Reading 14 of 120 entries…" ([ADR 0249](0249-bench-the-table-and-the-compare-grid.md)); that is fine for hundreds and slow for thousands. RFC 0041 §7 asks for one read that returns, for a page of entries, the effective value of the stats asked for, formulas evaluated, and left the choice between a query a page, formulas on the client and a `POST` form to Spike 3.

## Decision

### The spike

Spike 3 (findings in RFC 0041) measured the candidate below on libraries of 3,000, 5,000 and 20,000 entries: **a page of 100 entries by 30 columns takes 41 to 58 ms in 11 statements, formulas included**, against 510 to 690 ms for the same 100 entries one at a time. One query per page is fast enough; formulas stay on the server and no `POST` form is added.

### `GET /tenants/{tenant_id}/entities/effective-stats`

- **Which entries.** The filters of `GET /entities`, with the same meaning and the same order (name, then id): `q`, `kind` (repeatable, any of), `parent_id` and `recursive`. The list route's statement is factored into one function that both routes call, so a grid and a list over the same filters name the same entries.
- **Which stats.** `stat_definition_id`, repeatable, at least one and at most 50 (`422` otherwise), each a stat definition of the library (`404` for one that is not).
- **Paged** as every list is: `page` from 1, `size` at most 100, and the envelope `items`, `total`, `page`, `size`, `pages`.
- **Each item** is `{id, name, stats}`. `stats` holds one `{stat_definition_id, value, own, from_entity, computed}` for each requested stat the entry has a value for, in the order asked; a stat it has none of is left out, as an unset stat is on the entry's own read. `value` is the effective value with formulas evaluated (a stored value, or what a linear, comparison, sum or contents formula works out to); `own` says the entry holds it itself, as `EntityStatValueOut.own`; `from_entity` is the entry it is inherited from (`id`, `name`), null for an own value and for a source the caller may not see ([ADR 0305](0305-facts-and-entry-audiences.md)); `computed` says a formula decided it.
- **Who may read.** The gate of `GET /entities`: a participant of the library, and only the entries that caller may see. For a non-member the public catalog is not a separate branch here, because `GET /entities` has none either: it answers for participants only.

### How it is read

The page's entries come first, in name order, from the entry table alone, so what is walked is the page and nothing else ([ADR 0285](0285-api-reads-that-cost-what-they-read.md)). Then **every** effective row of those entries is loaded in one query with its stat definition, its source entry and its formulas, whatever columns were asked for, because a formula needs the rows it reads; contents formulas are loaded for the whole page at once (`attach_contents`, as the sheet read does); each entry's values are evaluated with the same function the entry's own read uses, and the requested ones are picked out. A stat reads the same here as on `GET /entities/{id}`; a test holds the two to each other.

## Not in scope

- A `POST` form that names entries by id, and "all of" filters.
- Writing: a grid edits through the ordinary stat routes.
- Information, pictures and parents of the entries: the list's rows are `GET /entities`'s.
- The count of the page envelope is the list's own `count(*)`.

## Consequences

- A compare grid is one request a page instead of one a row; Bench's `loadAll` is replaced by it in the grid's slice of this change.
- `list_entities` is factored: the filter statement moves to a function both routes use. No change to what the list answers.
- New route and schemas only; the check for breaking changes finds none. The generated clients change.
- A library freshly loaded in bulk is slow until the database has analysed it, as any read is.
