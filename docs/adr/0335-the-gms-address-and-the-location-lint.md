# 0335 - The GM's address and the Location lint

Status: accepted with the maintainer on 2026-10-23; RFC 0048 slice 3.

## Decision

Two GM-only reads. They add no table, no column and no write, and they are not part of any other
read: a library that never asks pays nothing, and no response of the player's gains a key.

**The address.** `GET /tenants/{tenant_id}/entities/{entity_id}/address` says where an entry sits,
step by step, as the library's GMs, Authors and full-visibility Owners and Organizers see it (the
standing that writes Locations, ADR 0330; anyone else is refused). The entry must be visible to the
caller, and a hidden or missing one is the same 404.

```json
{"segments": [
  {"via": "contained_in", "entity_id": "...", "name": "Backpack"},
  {"via": "with",         "entity_id": "...", "name": "Bram"},
  {"via": "at",           "entity_id": "...", "name": "Rusty Tankard"},
  {"via": "part_of",      "entity_id": "...", "name": "Neverwinter"}],
 "interior": [{"via": "part_of", "entity_id": "...", "name": "Rusty Tankard"}]}
```

- `segments` runs from what holds the entry up to the broadest Location: each container the entry
  is in (`contained_in`, nearest first); then, when the chain ends at a thing in no container that
  has an owner, the owner (`with`) and the owner's containers, as the inventory reads it
  (ADR 0123); then the place of the top of that chain (`at`: its `entity_location`, or nothing when
  the top is itself a Location with no place row of its own, which already stands in the list);
  then every Location above that place (`part_of`, nearest first). A key is absent when it does not
  apply: an entry in no container and at no place has `{"segments": []}`.
- `interior` appears only for an entry that is a Location, and lists the Locations above it
  (`part_of`). A bag that is also a Location has both: where the bag is, and what it is within.
- Each step names an entry by id, name and link name, and nothing else: no depth, no ordinal, no
  count, no axis word. Frames and axes join the list in their own slice, with their own `via`.
- Containment and part-of are walked with the same cycle guard and depth cap as every reader, and
  a chain that loops ends without an error that names a row.
- The walk uses the caller's own visibility, as every read does. A GM sees every Location, so the
  address is the whole chain; the reads are the same code as the player's, with the standing
  differing, not a second traversal.

**The lint.** `GET /tenants/{tenant_id}/lint/locations` lists what is probably a mistake in a
library's places, for a GM to fix. It stores nothing, changes nothing and offers no repair. Each
finding names the entries involved and says why in words, never in a code a player would see:

- `dormant_place`: an entry that has a place row and is also in a container (the row is ignored);
- `place_hidden`: an entry everyone can see, placed at a Location the players cannot, which they
  read as `unknown` (ADR 0334);
- `part_hidden`: a Location everyone can see that is part of one the players cannot, which they
  see under a higher one, or as a root (ADR 0330);
- `part_loop`: Locations that are part of one another, which only a copy can make.

"Everyone can see" is the entry's own audience: no row, or a public one. The list is ordered by
finding, then name, then id, in the library's standard page shape, and is empty for a library that
has no Locations. It is read for the library as a whole and never narrows to one campaign.

## Validation and delivery

Part of RFC 0048 slice 3, one API pull request stacked on slice 2. Tests: each segment and strand
(containers, owner, place, part-of ancestors, the interior of a Location that is also a container),
an empty address, the standing and the 404s, byte equality of the player's reads before and after
the routes exist, and each finding, including a loop made by raw rows.

## Excluded

Frames, axes and the player's `where` block on inventory lists (their own slices); any repair or
automatic move; the address of more than one entry in a request.
