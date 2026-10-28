# 0370 - Frame resolution and the GM's reads

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 12. Reads the tables of
[ADR 0369](0369-frames-and-axes.md) and joins the address of
[ADR 0335](0335-the-gms-address-and-the-location-lint.md), which said frames would come in with their own
`via`. Every read here is for those who write Locations; no player read gains a key.

## Decision

**Resolution is per axis, and the nearest explicit row wins.** For an entry, the chain is, nearest
first: the entry itself, each container it is in (`contained_in`), its owner and the owner's containers
(`with`) when it is in no container, the place of the top of that chain (`at`) and every Location above
that place (`part_of`), and for an entry that is a Location, the Locations above it. These are the
nodes the address already lists, in the order it lists them, and only the ones the caller sees; a hidden
node, or a frame the caller cannot see, is absent as if it had no row, and the search goes on to the next.
The first node with an `entity_frame` row on the axis gives that axis's frame. Nothing is read through
prototypes, and a map, a connection or a drawing never gives a frame.

**Frames of frames.** From the frame found, the search goes on along that frame's own row on the *same*
axis and so on up, nearest first, to a depth of eight, with a guard against a loop that ends the chain
without an error naming a row. So an entry on the plane *Ethereal*, which is on the plane *Prime
Material*, resolves to both, in that order. A frame's row on another axis is not inherited by what is on
it.

**The address.** `GET /entities/{id}/address` gains steps with `via: "frame"` after the `part_of` steps
of `segments`, one for each frame found, axis by axis in the order `plane`, `sphere`, `timeline`,
`universe`, each axis's frames nearest first. A frame step is the same id, name and link name as the
others, plus `axis`; the key is on frame steps alone. A library with no frame rows returns exactly what it
returned before. `interior` is unchanged.

**Reads of the rows themselves**, all for those who write Locations, in the library's standard page shape
where they list:

- `GET /entities/{id}/frames` answers `{"frame_axes": [...], "frames": [{"axis", "frame": {id, name,
  slug}}]}`: what the entry is a frame on, and the frames it is on itself, never inherited. A key that
  has nothing to say is `[]`.
- `GET /frames?axis=&q=` lists the entries that are frames the caller sees, by name then id, each with the
  axes it is a frame on; `axis` narrows and `q` matches the name.
- `GET /entities/{id}/frame-members?axis=` lists what is explicitly on a frame ("everything on the
  Ethereal"), by name then id, `axis` narrowing it when the frame has several; only entries the caller
  sees, and the entry must be a frame the caller sees.

A hidden entry, a hidden frame and a missing one are the same 404 and a hidden member is absent from every
row and every count. The caller's own visibility is applied in SQL.

**What does not change.** Whereabouts, the inventory reads and every read a player has: no axis word, no
frame, no key. The location lint gains no finding. Reach ([ADR 0046](0046-gm-reachability-widens-to-surroundings.md)) never reads a
frame row, and a test pins it as it does for places.

## Validation and delivery

Tests: nearest-wins along every kind of step of the chain, an entry's own row beating a place's, two
axes independent, a frame on a part-of ancestor, an owner, a container and an interior ancestor, frame of
frame, a loop made by raw rows ending quietly, a hidden node and a hidden frame skipped, the list and member
reads with their pages and counts, the standing and the 404s, the address unchanged for a library with no
frames, a player's reads byte-identical before and after frames exist, and that no reach code names a frame.

## Excluded

A frame-aware whereabouts for players; frames in the lint; resolving more than one entry in a request;
a frame step for the Map an entry is drawn on.
