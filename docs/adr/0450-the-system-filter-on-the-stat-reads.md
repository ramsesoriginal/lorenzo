# 0450 - The `system` filter on the stat reads

Status: accepted, built (2026-11-12). Slice Y3 of [RFC 0052](../rfcs/0052-game-systems-in-one-library.md). Builds on
[ADR 0448](0448-a-game-system-as-a-row.md) (a stat row says its system) and
[ADR 0387](0387-the-bulk-effective-stat-read.md) (the bulk read). Resolution does not change.

## Context

A library may hold the stats of several game systems, and an entry may carry the stats of all of them. A table plays one, and a
client that draws an entry for it has to drop the stats of the others itself. ADR 0448 put the system on each stat row, so the
filter is a decision the API can make once.

## Decision

- **`?system=<slug>`** is accepted by `GET /tenants/{t}/entities/{id}`, `GET /tenants/{t}/entities/by-slug/{slug}` and
  `GET /tenants/{t}/entities/effective-stats`. The stats returned are those that belong to no game system and those of that
  system; without the parameter, every stat, as before.
- **It shows, it does not resolve.** Every value is resolved over the whole prototype graph and every formula evaluated before
  the filter is applied, so a stat reads the same with it as without it, and a formula of one system that reads a stat of another
  still reads it. Only the rows of the answer are left out.
- **A slug that is not a system of the library is a 404** (`system-not-found`), a slug of another library's system included.
  A library with no system answers every read as it did, since nothing carries a slug.
- **Only `stats` is narrowed.** The entity read's `stat_groups` and the rest of its answer are unchanged.

## Design

A small module, `system_filter.py`: the query type, a check that the slug is one of the library's systems (one statement, only
when the parameter is sent) and the narrowing of a list of rows by their `system`, which ADR 0448 already loads with the group.
The entity read narrows its stat rows after they are built; the bulk read skips a winner whose system is another's after
evaluating, so no read costs a statement it did not.

## Validation and delivery

A test for each: the entity read with each of two systems and without, a formula of one system reading a stat of the other, an
unknown slug and another library's slug (404, on the entity read and the bulk read), the read by slug, the bulk read with each
system and without, and a library with no system. The OpenAPI change is the new query parameter on three routes (no breaking
change); `packages/api-client` is regenerated.

## Consequences

- A client draws an entry for one game system with one parameter and no join to the definitions.
- Y4 and Y5 use the same narrowing for a template and for a campaign that names a system.
