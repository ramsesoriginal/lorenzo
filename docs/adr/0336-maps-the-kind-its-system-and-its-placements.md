# 0336 - Maps: the kind, its coordinate system and its placements

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 4.

## Decision

A Map is an entity kind. A `map` marker (`entity_id` primary key, `tenant_id`, a composite
same-tenant foreign key to `entity` that cascades) gives an entry the kind, through the kind API
(`PUT /entities/{id}/kinds/map`) and through `POST /tenants/{tenant_id}/maps`, which makes an entry,
its marker and its outer audience in one request. Like a Location, a new Map is restricted unless
`is_public` is set. A Map has ordinary entry identity, slugs, prototypes, Information and pictures.
Its user-facing word is **Map**.

`map` carries two columns besides its key:

- `system` (jsonb, not null): what the Map's positions mean, as `lorenzo.map-system/1`.
- `subject_entity_id` (uuid, null): the Location the Map depicts, an authored pointer that no resolver,
  reach or whereabouts read ever follows. A composite same-tenant reference to `location`, with
  `ON DELETE SET NULL (subject_entity_id)`: deleting the Location empties the pointer and leaves the
  Map. A Map and the Location it draws may also be one entry; the interface recommends two.

**The system.** Positions are continuous *drawing units* on a flat sheet; y grows downward, as in
SVG, and the renderer never flips it. This slice knows two systems, and the rest of RFC 0048's six
arrive with their own slices:

```json
{"format": "lorenzo.map-system/1", "kind": "plane", "extent": [0, 0, 1000, 640],
 "scale": {"per_unit": 0.5, "unit": "km"}}
{"format": "lorenzo.map-system/1", "kind": "outline", "extent": [0, 0, 1000, 640]}
```

`extent` is the sheet, `[x0, y0, x1, y1]`, finite, with the far corner beyond the near one, no
coordinate beyond 1e7 in size, and has no unit of its own. A `plane` may say what a drawing unit is,
`per_unit` (a positive number) of a `unit` (a name of at most 32 characters, the author's own words);
without a scale no distance is computed, and without a unit none is invented. An `outline` measures
nothing and takes no scale. The kind lives in the JSON and in no database check: a document written by
a newer version that names a kind this one does not know is read as an outline and measures nothing.
Nothing is seeded and nothing is a default; the interface asks for the extent and offers a plain
choice between "draw with measurements" and "just draw".

**Placements.** `map_placement` says where one entry is drawn on one Map, with these columns:
`map_entity_id` and `entry_entity_id` (the primary key, both composite same-tenant references that
cascade), `geometry` (jsonb, ADR 0337), `role` (text, null), `style` (jsonb, null), `z` (smallint, 0),
and the derived `bytes` and `minx`, `miny`, `maxx`, `maxy` (a bounding box that is a superset of the
shape, as ADR 0337 says). It carries no time, no audience and no revision. One entry has at most one
placement on a Map, and the same entry may be placed on many Maps with different geometry; a placement
never inherits. A Map shows exactly the entries that have a placement. There is no "all the children"
mode and no read-time expansion; a bulk action in the editor writes explicit rows.

A placement is a drawing. It is never read as where an entry is: no whereabouts, address, reach or
distance read consults it, and a presence marker of a being says where it is drawn. Its visibility is
the Map's and the entry's, joined in SQL (ADR 0338), and a secret position is a restricted entry or a
restricted Map.

**Combinations.** A Map may be any other kind, as a Location may (ADR 0331): the refusals of the
calendar family, clock, Scene, Session and Fact are lifted for Map in both directions through the kind
API, a generated matrix proves every pair (create, publish, copy, release), and a Map beside a Location
is one of them. Today's refusals between other kinds are unchanged, and a triple is not published
until it is proven.

**Repository.** `map` and `map_placement` are content tables with the `repository_read` policy, a
registry line each, planner steps (copy remaps entries by their links, and drops, with a reason, a
placement whose entry was not copied) and purge counts. An update reads a Map's placements as one
field of its snapshot and replaces them as a set, skipping entries not copied. The release document
format gains `maps` (system and subject) and `map_placements`, following the convention of ADR 0330.
Geometry is validated again on every copy and update (ADR 0337).

**Deleting.** Deleting a Map removes its placements; deleting an entry removes its placements; deleting
a Location empties `subject_entity_id`. Whole-library deletion stays supported.

## Validation and delivery

RFC 0048 slice 4, with ADRs 0337 to 0340. Tests: the kind through both routes; the system's accepted
and refused forms; the primary key and cascades; the subject pointer and its deletion; the kind-matrix
rows for every pair; copy, update, release and purge; and that no time, audience or revision column
exists on either table.

## Excluded

Grids, hex and sphere systems and visual overlays (slices 7 and 8); pictures and layers (slice 9);
themes named by a Map (slice 6); counts on placements; links and distance (slices 10 and 11).
