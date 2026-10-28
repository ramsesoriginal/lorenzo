# 0363 - Connections: the kind and its two ends

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 10. A connection is an entry
that joins two entries, as a Location is an entry that is a place
([ADR 0330](0330-locations-the-kind-and-the-part-of-tree.md)). Distance and routing are the next
slice and read nothing but what is written here.

## Decision

**The kind.** A `connection` marker (`entity_id` primary key, `tenant_id`) gives an entry the kind:

```sql
connection(entity_id PK, tenant_id NOT NULL, end_a NOT NULL, end_b NOT NULL,
  one_way boolean NULL CHECK (one_way IS NOT FALSE), CHECK (end_a <> end_b))
```

Same-tenant foreign keys to `entity` for the entry and for each end, all `ON DELETE CASCADE`: deleting
an end removes the marker and leaves the entry, a plain entry, behind. `one_way` is null for a way that
goes both ways and true for one that goes from `end_a` to `end_b`. Indexes on `(tenant_id, end_a)` and
`(tenant_id, end_b)`. Row Level Security forced with the `repository_read` policy, and one line in
`copyable_tables.py` (`carried_by="entity"`). Its user-facing word is **connection**; it has ordinary
entry identity, link names, prototypes, Information, pictures and stats.

- **Ends are entries**, of any kind, and the rows are kind-blind: a road joins two Locations, a portal a
  Location and a Map's pin, a mirror two rooms. The two ends differ. A connection reads only as long as
  both ends exist; a hub (a stair shaft joining twelve floors) is a Location and a connection to each
  floor, written in one request (below). Connections with more than two ends are a later decision.
- **Its kinds are prototypes**: road, stairs, lift, portal, mirror, shortcut, ferry are entries the
  author makes and names a connection after (`prototypes` on the request). Nothing is seeded.
- **Length, speed and cost are ordinary stats** of the entry, with the author's unit; nothing about
  them is a column here. A drawn road is the connection entry's own placement on a Map (ADR 0336) and
  carries shape only; redrawing it never changes the two ends.
- **A connection combines with no other kind.** `POST /tenants/{t}/connections` is the only way to make
  one (the kind route refuses to add it, and refuses any other kind to one); `DELETE
  /entities/{id}/kinds/connection` removes the marker once the entry's audience is public, as for a
  Location. The kind joins `EntityKind` after `map`, the publishable combinations as `("connection",)`
  alone and the kind matrix as one row; the response `kinds` widening goes through the breaking-change
  process.

**Visibility.** The entry's outer audience is the connection's, as for a Location, and a connection
created through the route is restricted unless `is_public`. **A connection is read only by a reader who
can see the connection, its end A and its end B**; a connection with a hidden end is absent from every
list, count, page and fetch, and a fetch of it answers the same 404 as a missing one. The predicate is
the shared `visible_entry_clause` applied to all three, in SQL, before pagination. Connections are
authored world content in the library GMs' reach and Authors may give the kind, as for Locations and
Maps; **no connection row feeds ADR 0046 reach**, and the pin test that scans the reach statements
names the new table.

**Standing.** Any participant reads visible connections. Making, replacing the ends of, restricting
and deleting one need the standing that writes Locations and Maps, and each end is resolved under the
writer's own visibility (a hidden or missing end is the generic 404).

**Reads.** `GET /tenants/{t}/connections` lists the visible ones by name then id in the standard page
shape, with `end=<entry id>` for those that touch an entry and `q` for a name; `GET
.../connections/{id}` returns one with an ETag. A connection is
`{id, name, slug, kinds, end_a, end_b, one_way, updated_at, can_manage, is_public}`, each end an entry
stub (`id`, `name`, `slug`, `kinds`), `is_public` for managers only.

**Writes.** `POST .../connections` takes `{id?, name, slug?, end_a, end_b, one_way, prototypes,
is_public}`; `PUT .../connections/{id}` replaces the ends and `one_way` under `If-Match`; deleting is
the entry's own delete. An end equal to the other is a 422. A library holds at most 10,000 connections.

**The hub write.** `POST .../connections/hub` takes `{hub, spokes, prototypes, is_public}` with at most
50 spokes, each `{end, direction, name?}` with `direction` `both` (the default), `to_hub` or `from_hub`,
and makes one connection from the hub to each spoke in **one transaction**, named `<hub> - <spoke>`
unless the spoke gives a name. A spoke twice, a spoke that is the hub, an end that is hidden or missing,
or the library limit, refuse the whole request and write nothing; it answers the connections made.

**Repository.** `connection` is a content table: release format 23 has `connections` (`end_a`, `end_b`,
`one_way` for each connection entry; the v22 reader gives none). A copy writes the marker only when both
ends were copied, else the entry is copied without it and the drop is reported; an update compares and
applies `end_a`, `end_b` and `one_way` as one unit by the ends' names, and skips it with a reason when an
end is not in the library yet.

## Validation and delivery

Tests: the marker round trip through the kind routes and the refusals; creation, ends under the
writer's visibility, equal ends, one-way direction; replacing under `If-Match`; the hub write and each
of its refusals writing nothing; visibility (a hidden end hides the connection from every read, and
two libraries with a hidden end and a missing one answer alike); the GM and Author reach and the pin
test; deleting an end and deleting the entry; the library limit; the kind matrix row; copy, update,
release and the v22 reader.

## Excluded

A connection with more than two ends, time on a connection, travel, speed and cost beyond stats, a
router or a distance (slice 11), and any reading of a connection as containment, part-of, placement or
reach.
