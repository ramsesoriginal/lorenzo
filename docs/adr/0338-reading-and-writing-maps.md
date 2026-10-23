# 0338 - Reading and writing Maps

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 4.

## Decision

**Standing.** Any participant of a library reads the Maps and placements they may see. Creating a
Map, changing its system, and writing or removing placements need the standing that writes Locations
(ADR 0330): Authors, GMs and full-visibility Owners and Organizers. Library Authors and GMs read
every Map entry as authored world content, as they read Locations and Facts, and a Map's placements
and Locations never feed ADR 0046 reach.

**Routes**, all under `/tenants/{tenant_id}`:

- `GET /maps`: the visible Maps by name then id, the library's standard page shape, with `q` for a
  case-insensitive name match. A row is a stub (id, name, slug, kinds).
- `POST /maps`: `name`, optional `slug`, `system`, optional `subject_entity_id`, `is_public` (false
  unless set), and an optional client `id`. The system and the subject are validated (ADR 0336,
  0337); a subject the writer cannot see is the same 404 as a missing one.
- `GET /maps/{id}`: the header, with an `ETag`: the stub, `system`, `subject` (a stub, only if the
  reader can see that Location), `updated_at`, `can_manage` and, to managers, `is_public`. A Map the
  reader cannot see is the same 404 as a missing one, and so is an entry that is not a Map.
- `PUT /maps/{id}`: replaces `system` and `subject_entity_id` under `If-Match`; a stale version is
  the library's usual 412 and a missing header a 428. A plane may become an outline and back; no
  placement is touched. Renaming and opening a Map to the library use the entry routes, as for a
  Location.
- `PUT /maps/{id}/placements/{entry_id}` with `geometry`, optional `role`, `style` and `z`
  (`-100` to `100`, default 0), and `DELETE` the same address. The Map and the entry are resolved
  under the writer's visibility, one 404 for hidden and missing; the validator runs on every write and
  derives `bytes` and the bounding box.
- `GET /maps/{id}/placements`: the placements the reader may see, ordered by `z` then entry id, as
  keyset pages after the visibility join (`limit` at most 200, `cursor`). A page ends at 200 rows or
  about 1 MiB of body, whichever comes first, and carries no total. `bbox=x0,y0,x1,y1` keeps what
  overlaps it, `role` (repeatable) keeps those roles, and `min_diag` drops what is smaller than a
  diagonal. A row is the entry's stub (id, name, slug, kinds: no tags), `geometry`, `role`, `style`
  and `z`.

**Nothing leaks.** A placement is listed only when the reader may see both the Map and the entry;
the visibility predicate runs in SQL before the keyset limit, so a hidden entry leaves no row, gap or
count, and a page of a reader with a hidden placement is byte-identical to a page of one for whom it
does not exist. There is no count and no revision counter anywhere. A placement whose entry the
reader cannot see is absent; the Map's own audience gates everything.

**Caching.** The placements' `ETag` is the hash of the viewer's own body, `Cache-Control` is
`private`, and `If-None-Match` answers 304. A client holds a Map in its read cache (ADR 0325) under
the viewer's scope, revalidates it on every open, and clears it at sign-out and library switch; no
freshness window decides what a person may read.

**Writes touch.** A placement write touches the Map entry (its `updated_at` and so its `ETag`) and
is one activity entry. Concurrent placement writes to one Map are not ordered by a lock: each row
is its own; the Map's version moves for whoever reads it next.

## Validation and delivery

Tests: each route and refusal; standing; the 404s for hidden and missing; keyset paging across
`z` ties and the 200-row and size bounds; `bbox`, `role` and `min_diag`; hidden-placement parity
(a page with a hidden entry equals a page without it); the ETag and 304; `If-Match` on the header
write; and that no reach module reads a Map or its placements.

## Excluded

Batch writes and "place the children" (slice 6), counts, links and distances (slices 10 and 11),
a placement's own audience, and any cross-Map query of where an entry is drawn.
