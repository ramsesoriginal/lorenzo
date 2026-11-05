# 0399 - Relationships: the kind and its two ends

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slice 1. The shape follows [ADR 0363](0363-connections-the-kind-and-its-two-ends.md). Nothing in Maps changes.

## Context

A friendship, a parentage or a war joins two entries as a road does, and a connection already has two ends, a
direction, a visibility rule and a repository format. But a connection is read by Maps as a way: the router of
[ADR 0367](0367-the-distance-read.md) is kind-blind and counts a connection with no length as an unmeasured leg, so a
social tie that touched a place would make "no known route" an "at least" answer, and the links of
[ADR 0364](0364-links-derived-from-connections.md) would list it as a road. ADR 0363 also excludes time on a
connection, and RFC 0048 pins that with a test. The choices were: reuse `connection`, reuse it with a discriminator
that every Maps read must honour, or a second kind.

## Decision

**A second kind, `relationship`**, user-facing **relationship**. A `relationship` marker gives an entry the kind:

```sql
relationship(entity_id PK, tenant_id NOT NULL, end_a NOT NULL, end_b NOT NULL,
  one_way boolean NULL CHECK (one_way IS NOT FALSE), CHECK (end_a <> end_b))
```

Same-tenant foreign keys ([ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)) to `entity` for the
entry and for each end, `ON DELETE CASCADE` (deleting an end removes the marker and leaves a plain entry). `one_way`
is null for a way both ways and true from `end_a` to `end_b`. Indexes on `(tenant_id, end_a)` and
`(tenant_id, end_b)`. Row Level Security forced with the `repository_read` policy, and one line in
`copyable_tables.py` (`carried_by="entity"`). The release document gains `relationships` with a format bump and a
reader that gives none for older documents.

- **Ends are entries of any kind**, kind-blind: a being, a group, a Location, an Event, an item that stands for a bond,
  another relationship. The two ends differ.
- **It combines with no other kind.** `POST /tenants/{t}/relationships` is the only way to make one; the kind route
  refuses to add it and refuses any other kind to one; deleting the marker is allowed once the entry is public, as for
  a connection. The kind joins `EntityKind`, the publishable combinations as `("relationship",)` alone and the kind
  matrix as one row. The widening of `kinds` in responses goes through the breaking-change process
  (`openapi-breaking-accepted.txt`, this ADR, a `!` commit).
- **Its types are prototypes** (parent of, ally of, at war with), entries the author makes. Nothing is seeded.
- **A standing or a measure is an ordinary stat** of the entry. No column here.
- **No uniqueness on a pair or a type.** A refusal would tell a writer that a hidden relationship exists. Two
  relationships of one type between one pair are legal.

**Visibility.** The entry's outer audience is the relationship's, and a relationship made through the route is
restricted unless `is_public`. **A relationship is read only by a reader who can see it, its end A and its end B**, in
every read, and the predicate is part of the shared `visible_entry_clause` for this kind, so the generic entry reads
(the list, the bulk stat read of [ADR 0387](0387-the-bulk-effective-stat-read.md), previews, search, the entry itself)
apply it with nothing to remember. It is applied in SQL before pagination and counts. A relationship with a hidden end
answers 404 as a missing one does. **No relationship row feeds [ADR 0046](0046-gm-reachability-widens-to-surroundings.md)
reach or any access decision**, and the pin test that scans the reach statements names the table. Maps reads no
relationship, and a pin test says so.

**Standing.** Any participant reads visible relationships. Making, replacing the ends of, restricting and deleting one
need the standing that writes Locations and Maps ([ADR 0404](0404-who-sees-and-who-writes-a-relationship.md)), and
each end is resolved under the writer's own visibility (a hidden or missing end is the generic 404).

**Reads.** `GET /tenants/{t}/relationships` lists the visible ones by name then id in the standard page shape, with
`end`, `end_a_in` and `end_b_in` (at most 100 ids each), `type` (a prototype and what inherits from it), `q`,
and repeatable `stat_definition_id` (at most 50) that adds the effective values as ADR 0387 does. `GET
.../relationships/{id}` returns one with an ETag. A relationship is `{id, name, slug, kinds, end_a, end_b, one_way,
updated_at, can_manage, is_public}`, each end an entry stub, `is_public` for managers only.

**Writes.** `POST` takes `{id?, name, slug?, end_a, end_b, one_way, prototypes, is_public}`; `PUT` replaces the ends and
`one_way` under `If-Match`; deleting is the entry's own delete. An end equal to the other is a 422. The bulk write is
[ADR 0400](0400-relationship-kinds-standings-and-direction.md). A library holds at most 20,000 relationships
(*proposed default*), counted apart from connections.

**Repository.** `relationship` is a content table. A copy writes the marker only when both ends were copied, else the
entry is copied without it and the drop is reported; an update compares and applies `end_a`, `end_b` and `one_way` as
one unit by the ends' names, and skips it with a reason when an end is not in the library yet.

## Validation and delivery

Tests: the marker round trip through the kind routes and the refusals; creation with ends under the writer's
visibility; equal ends; one-way direction; replacing under `If-Match`; a hidden end hiding the relationship from every
route, including each generic read, with two libraries (a hidden end and a missing one) answering alike; two
relationships for one pair; the limit; the pin tests for reach and for Maps; the kind matrix row; copy, update,
release and the older reader; the `kinds` widening in the breaking-change gate.

## Excluded

A relationship with more than two ends; time (ADR 0405, its own slice); standings and types as schema; any use in
routing, distance, links or reach; and a discriminator on `connection`.
