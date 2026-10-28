# 0351 - Writing placements in bulk

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 6. Adds one route to
[ADR 0338](0338-reading-and-writing-maps.md); every rule of that ADR still holds for each placement.

## Context

A placement is written one entry at a time (`PUT /maps/{id}/placements/{entry_id}`). Authoring needs
three things that one-at-a-time writes do badly: placing the children of a Location as one action so
that it succeeds or fails whole, undoing a move that changed several placements, and a client that
writes many rows without a round trip each. RFC 0048 decided there is no "show all children" mode and
no read-time expansion: a map shows exactly the entries that have a placement, and "place the
children" is an editor action that writes explicit rows.

## Decision

**One route**, `POST /tenants/{tenant_id}/maps/{map_id}/placements/batch`, with the standing and the
visibility rules of the single writes (those who write Locations; the Map and every entry resolved
under the writer's visibility, one 404 for hidden and missing, so a batch naming an entry the writer
cannot see fails whole and says nothing about which).

The body is `put`: a list of `{entry_id, geometry, role?, style?, z?}` and `remove`: a list of entry
ids, at most **100 operations** in all (one limits table, ADR 0337: this is its write batch cap), no
entry twice. Each `put` goes through the same validator as a single write and is a redraw when the
entry is already on the Map; a `remove` of an entry that is not on the Map is a no-op, as for the
single delete. The Map's placement cap counts the rows the batch would add, before anything is written.

**Atomic.** The whole batch is one transaction: if any operation is refused, nothing is written and the
answer is the first refusal, with the index of the operation it belongs to and a sentence that repeats
none of the input. A success writes every row, touches the Map entry once (so its `ETag` moves once)
and is **one activity entry** naming the Map and the counts, not one per row.

**The answer** is `{put: n, removed: n}` and nothing else: no ids, no counts of what the writer could
not see.

**"Place the children" is not a route.** The editor reads the Location's visible parts with the route
that exists (`GET .../locations/{id}/parts`), chooses where to put each, and sends the explicit rows
in one batch. Nothing on the server expands a Location into its children, and a later change to the
part-of tree changes no placement.

## Validation and delivery

Tests: every refusal of a single write inside a batch (the operation's index is in the answer and
nothing is written); a hidden or missing entry fails the whole batch with the single route's 404; the
100-operation cap and the placement cap; a duplicate entry; remove of an entry not on the Map; one
touch and one activity entry for many rows; the same body gives the same Map as the same writes one at
a time; a player is refused; a batch changes no reach (the pin test of ADR 0338 covers the new code).

## Excluded

Batch reads, a batch across Maps, partial success, a server-side layout of children, and any route
that creates entries: creating a Location while drawing is the client's own call to the Location
route before the write.
