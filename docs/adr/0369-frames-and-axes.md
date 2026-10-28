# 0369 - Frames and axes

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 12, the last of the data work. API
only: no app places an entry on an axis. It narrows [RFC 0026](../rfcs/0026-world-model-axes-and-address.md)
as [RFC 0048](../rfcs/0048-locations-maps-connections-and-optional-dates.md) sets out. Nothing here is a
Location, a Map or a connection, and no time column exists on either table.

## Decision

**An axis is a closed word.** The axes are `plane`, `sphere`, `timeline` and `universe`: platform
structure, the same in every library, widened only by an ADR. The database keeps the token open in shape
(`axis ~ '^[a-z][a-z0-9_]{0,31}$'`) so that a later axis is a code change and no migration; every writer
and every importer refuses a token that is not in the list in code, so the list is also the cap on how
many distinct axes a library can hold. A library that never uses one has no row, no form field and no
response key (RFC 0048 G1); nothing is seeded.

**A frame is an ordinary entry that carries a designation.** Two tables, both with `tenant_id`, row
level security forced, and composite same-tenant keys ([ADR 0117](0117-same-tenant-references-by-composite-foreign-keys.md)):

- `frame(entity_id, axis, tenant_id)`, primary key `(entity_id, axis)`, unique `(entity_id, tenant_id,
  axis)`: the entry is a frame on that axis. An entry may be a frame on several axes. It is a designation,
  not a kind: it combines with every kind, appears in no `kinds` list and needs no kind plumbing. The
  entry key cascades.
- `entity_frame(entity_id, axis, frame_entity_id, tenant_id)`, primary key `(entity_id, axis)`: the
  entry is on that frame, and at most one frame per axis. `entity_id <> frame_entity_id`. The key
  `(frame_entity_id, tenant_id, axis)` references `frame`, so the axis of the frame and of the row
  always match, in the database. Both keys cascade: deleting an entry removes its own rows and the rows
  that put others on it; taking a designation away removes the memberships on that axis.

A frame may itself be on a frame of the same axis. That is how a multiverse is written: a plane inside a
plane, a universe inside a universe, never an axis of its own. A timeline is membership only: an entry
is on it or is not, and nothing says when. Nothing is inherited through prototypes, and a frame row feeds
no reach, no whereabouts and no read a player has.

**Writes** are for those who write Locations ([ADR 0330](0330-locations-the-kind-and-the-part-of-tree.md))
and who may write the entry itself ([ADR 0333](0333-placement-an-entry-is-at-a-location.md)); a target
the writer cannot see is the same 404 as a missing one.

| Request | Does |
| --- | --- |
| `PUT /tenants/{t}/entities/{id}/frame-axes/{axis}` | designates the entry as a frame on the axis; idempotent |
| `DELETE /tenants/{t}/entities/{id}/frame-axes/{axis}` | takes the designation away, and with it every membership on that axis |
| `PUT /tenants/{t}/entities/{id}/frames/{axis}` with `{"frame_entity_id"}` | puts the entry on that frame, replacing its frame on the axis |
| `DELETE /tenants/{t}/entities/{id}/frames/{axis}` | takes the entry off its frame on the axis |

An axis that is not in the list, a target that is not a frame on that axis, an entry put on itself, a row
that would make frames of one axis a loop, and a chain of frames longer than eight are 422s with their
reasons in words. Limits fixed in code: 2,000 frames and 20,000 memberships in a library.

**Repository.** Both tables are content: copyable, counted on purge, in the release document (format 25,
keys `frames` and `entity_frames`, always written, with a reader for 24 that adds them empty), digested and
diffed with the entry (`frame_axes` and `frames`), and applied by updates as units. A copy writes a
membership only when the entry and its frame are both copied, drops one whose frame is not designated on
that axis or whose axis this version does not know, and says why for each; the count of rows a copy leaves
out is reported like every other table's.

## Validation and delivery

Tests: the tables (constraints, row level security, cascade on delete of an entry and of a designation),
each write and each refusal, idempotence, loops and depth, the standing and the 404s, that no player read
changes by a byte whether or not frames exist, the registry and release rows, copy and update, a release
round trip and the v24 reader, and a schema scan that no frame table has a time column.

## Excluded

A client place for any of it; timeline variants and "does not exist in this timeline"; two frames on one
axis; an axis a library defines; inheritance through prototypes or containment on write; a frame row that
carries a name, a label or a coordinate.
