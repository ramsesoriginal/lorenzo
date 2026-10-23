# 0333 - Placement: an entry is at a Location

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 2.

## Decision

`entity_location` (`entity_id` primary key, `location_entity_id` not null, `tenant_id`) says that an entry
is at a Location now. One row per entry, any kind, including a Location (a ship that is also a
Location can be docked at one). Both ends are composite same-tenant references, to `entity` and to
`location`, and both cascade: deleting the entry removes its row, and deleting a Location, or
removing its marker, leaves the entries that were at it unplaced. A check says an entry is not at
itself. There is no time column, no coordinate and no quantity. A place is a fact about one entry
and never inherits down the part-of tree, along containment or through prototypes: what is at the
Tavern is not thereby at its Cellar.

**Containment wins.** Something in a container is located by the container, and a container by
its own place, so a reader takes a place only at the top of an entry's containment chain, through
the same walk that carries an owned thing in no container to its owner (ADR 0115, 0123). A place row
on an entry that is contained is ignored by every reader. `PUT .../at` on a contained entry is
accepted and ignored with the response it would give otherwise: no 409, no container named, as a
refusal would disclose what holds it.

**The row follows the container.** A flush hook, installed like the repository quota hook, applies
two rules to every write the inventory routes make through the ORM, in the same transaction:

- putting an entry into a container deletes its place row;
- taking an entry out of its container gives it the place of the top of the chain it left: the
  `entity_location` of that top, or, when the top is itself a Location with no place row of its
  own, that Location. If none resolves, no row is written. An entry put into another container in
  the same write gets none.

Putting an entry back into a container clears the row again; the earlier place is not restored.
Moving an entry from one container to another changes nothing. The containment responses show
nothing of any of this. Repository writers do not go through the hook: the copy planner drops a
place row whose entry is contained in the copied set, and readers ignore a stray row either way.

**Writes.** `PUT /tenants/{tenant_id}/entities/{entity_id}/at` (body `location_entity_id`) and
`DELETE` the same address. They need the standing that writes Locations (Authors, GMs and
full-visibility Owners and Organizers, ADR 0330) and the standing that writes that entry. The entry
and the Location are resolved under the writer's own visibility, and a hidden or missing one is the
same 404. Players place nothing in this slice, and the Maps app offers no way to place an entry yet:
this is the API and the command line.

**Repository.** `entity_location` is a content table with the `repository_read` policy, a registry
line, a planner step that drops, and reports, a row whose Location was not copied, and an update
applier field, `place`, in the entry's snapshot. The release document format gains an
`entity_locations` key, following the convention of ADR 0330.

**What it never does.** It never feeds ADR 0046 GM reach: no reach code names the table, and a test
scans for it and checks the reach set is the same with and without rows. It never filters an
inventory read: a thing is listed whether or not it has a place.

## Validation and delivery

Part of RFC 0048 slice 2, one API pull request stacked on slice 1. Tests: the writes and their
refusals, the containment rules above (put in, take out, put into another, back again, and a stray
row), the hook through the inventory routes, deletion of an entry and of a Location, the hidden
target's 404, copy, update, release and purge, the schema scan that no placement or position table
has a time column, and the reach pin.

## Excluded

The player's read (ADR 0334); the GM's address read, frames and axes; placing from the Maps app;
timelines; coordinates, which belong to a map's own placements.
