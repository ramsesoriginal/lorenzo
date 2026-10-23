# 0330 - Locations: the kind and the part-of tree

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 1.

## Decision

A Location is an entity kind. A `location` marker (`entity_id` primary key, `tenant_id`, a composite
same-tenant foreign key to `entity` with cascade) gives an entry the kind, through the existing kind
API (`POST /entities` with `kinds`, `PUT` and `DELETE /entities/{id}/kinds/location`), and a
convenience `POST /tenants/{tenant_id}/locations` creates an entry, its marker and its outer
audience in one request. The marker carries no other column. A Location has ordinary entry identity,
slugs, prototypes, Information and pictures. Its user-facing word is **Location**.

`location_part` (`child_entity_id` primary key, `parent_entity_id` not null, `tenant_id`,
`level_ordinal` numeric null) is the part-of tree. Both ends are composite same-tenant references
to `location` and cascade, so deleting a Location, or removing its marker, makes its children roots
and drops its own row. A root is a Location with no row. A row has a check that child and parent differ.
Part-of is single-parent and skip-level: a parent need not be the next level up, and a Location has
no type and no mandatory level. A floor is an ordinary child Location. `level_ordinal` only orders
siblings (null last, then name, then id); it has no zero point, unit, direction or uniqueness.
`containment` is untouched, and no part-of row is ever read as containment, ownership, a prototype
edge or travel.

Writes (`PUT` and `DELETE /tenants/{tenant_id}/locations/{id}/part-of`, the `PUT` body naming
`parent_entity_id` and an optional `level_ordinal`) check acyclicity with a recursive ancestor walk
inside the write transaction, under a per-library advisory lock, with a depth cap of 50. A cycle,
a self reference or a chain beyond the cap is one generic 422 that names no row. The tree is
acyclic by this route-level guarantee only: the repository planner validates a copied tree before
applying it, a release refuses a cyclic tree, and every reader keeps the depth cap and a path guard,
ending a chain at a cycle without an error that names a row. The writer's parent is resolved under
the writer's own visibility, and a hidden or missing parent or Location answers the same 404.

**Visibility.** An entry's outer audience (ADR 0305) is the Location's visibility: no new column.
A Location created through `POST /locations` has a restricted audience unless the request sets
`is_public`, like every other new kind. A marker added to an existing entry changes nothing
that entry's readers see. The existing entry-audience edit route accepts Locations. Every read uses
the shared `visible_entry_clause`, and a forbidden fetch answers the same 404 as a missing one.
Counts and pages are computed over visible rows in SQL before pagination.

**A hidden level is skipped.** A reader sees a visible Location under its nearest visible ancestor.
The chain is derived at read time and never stored. No response marks that a level was skipped, as
a marker would reveal that the level exists, and the interface says "in" or "within" for every
hierarchy line, never "part of directly". The parts of a Location are the visible Locations that
reach it through hidden levels only: the read descends through hidden children and stops at visible
ones, in one recursive statement that carries the visibility predicate and the depth cap, and the
cap counts hops whatever their visibility. A response must be byte-identical whether a hidden
middle level exists or the child sits directly under the grandparent.

**Standing.** Any library participant reads visible Locations. Creating, editing, re-parenting,
restricting and deleting need the standing that clocks and Events use: Authors, GMs and
full-visibility Owners and Organizers. Library Authors read every Location as authored world
content, and, as for Facts and Events, Location entries are in the library GMs' reach as
authored content. Part-of, placement and frames never feed ADR 0046 reach: the pin test enumerates
those relation tables and scans the compiled reach statements.

**Reads.** `GET /tenants/{tenant_id}/locations` lists visible Locations (`root=true` for roots,
`q` for a case-insensitive name match, a keyset cursor ordered by name then id, at most 200 per
page, no total). `GET .../locations/{id}` returns the name, slug, ordinal, the nearest visible
ancestor and, to managers, whether the audience is public. `GET .../locations/{id}/parts` returns
the visible parts as above, ordered by ordinal, name and id. Entry stubs carry only id, name, slug
and kinds. No endpoint returns a depth, a path, a child count of hidden rows or a hidden name.

**Repository.** `location` and `location_part` are content tables with the `repository_read` policy,
a registry line each and a planner step. The release document format gains a `locations` key,
following the existing convention (a bump per landing slice, every key always written, the
older reader shim). A copy drops a part row whose parent or child falls outside the copied set
and reports it; an update merges `location_part` by child. `Location` joins the kind matrix
(ADR 0331) and the publishable combinations.

**Deleting.** Deleting an entry or removing its marker removes its `location_part` rows both ways,
so the children become roots; whole-library deletion stays supported. The generic deletion guard
adds no dependent for this slice.

## Validation and delivery

One API-and-app vertical pull request (ADR 0332 for the app), stacked after the documentation pull
request. Tests cover: marker round trip through the kind API; cycle, depth and cross-library
references; keyset pages; hidden-parent parity (the byte-identical case above); the GM and Author
reach rules with the placement tables untouched; two-library byte equality for hidden against
absent Locations; deletion rows; copy, update, release and an older document; the response `kinds`
enumeration widening through the breaking-change process.

## Excluded

Placement of entries at Locations, frames and axes, maps, connections, distance and dates (later
slices of RFC 0048); a level label column; types or levels on Locations; any use of the tree for
containment, ownership, travel or reachability.
