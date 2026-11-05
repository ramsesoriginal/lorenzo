# 0405 - Optional time on a relationship, and reading as of an Event

Status: accepted, decided with the maintainer on 2026-11-05; [RFC 0049](../rfcs/0049-lorenzo-social-relationships-and-social-webs.md)
slices 6 and 12. Builds on [ADR 0312](0312-explicit-event-order-and-causality.md),
[ADR 0315](0315-reader-scoped-event-order-and-sharing.md) and [ADR 0399](0399-relationships-the-kind-and-its-two-ends.md).

## Context

A war begins and ends, a marriage starts at a wedding. RFC 0048 kept time off `connection` and put none on a
placement, and ADR 0363 excludes it, with a test. The relationship is a different kind, so it can carry an optional
limit without amending any of that. The order of Events is explicit and partial, and a reader derives it from the
Events and shared assertions they see.

## Decision

**Two nullable references.** `relationship` gains `starts_at` and `ends_at`, each an Event (a `story_event`) under a
same-tenant key, `CHECK (starts_at <> ends_at)`; the columns arrive with the slice that reads them. They name Events,
never dates, and set no order. A relationship with neither behaves as if time did not exist. An Event that a
relationship references can be deleted, and the delete clears the reference (the keys are `ON DELETE SET NULL
(starts_at)` and `(ends_at)`, clearing only the column). In the same transaction the Event's delete route leaves a note on
each relationship it bounded: information of the ordinary note type, restricted to staff, saying that the Event of that
name started or ended it and was deleted. The relationship does not silently become unbounded, and the note is the only
record (ADR 0313's refusal of a delete is not used here). A repository's purge and a tenant's deletion do the same or
nothing, as their own rules say. Writing the references needs the standing of ADR 0399 and visibility of the Event; the
release format carries them, with the older reader giving none.

**Reading as of an Event E.** `GET /tenants/{t}/relationships?as_of=<event id>` adds `as_of` to each row, one of:

- `holds`: the start is E or is recorded before E, and the end is none or is not recorded at or before E;
- `not_yet`: the start is recorded after E;
- `ended`: the end is recorded at or before E;
- `unknown`: otherwise, including a start or end that is not recorded against E.

A relationship with no start and no end `holds`. **Recorded** means a path of `causal` or `ruled` assertions in the
reader's authorized graph (visible Events and shared assertions only, ADR 0315). A `linearized` comparison decides
nothing here: it is a display order and never chronology. `state=` filters before pagination. The reachability sets of
E (before and after) are computed once, over the reader's graph, and bounded in code (*proposed default*: 2,000
Events); past the bound the answer is `limit_reached` and no row is classed. The read takes no argument that names
another reader's graph.

**A limit the reader cannot see** makes the answer `unknown`: the Event is absent for them, so no recorded path can
place it. This tells the reader that a limit exists and never which Event, a cost the maintainer accepted over reading
it as no limit. A plain read of the relationship names only the Events the reader can see.

**As seen by X.** `as_seen_by=<being id>` returns the relationships X may read through X's own grants and X's groups. It
is for staff (full-visibility Owners and Organizers, GMs of a campaign the being is in) and for a player when X is a being
that player controls; for a player the result is also limited to what that player may read, so it never shows more than
they could see, and a being they do not control is refused. It says what X *may read*, not what X believes; belief,
rumour and confidence wait for RFC 0029, and the interface words it that way.

**Drawing.** `unknown` is the dotted edge of §18 (uncertain). `not_yet` and `ended` are absent from the graph and listed
under a switch.

## Validation and delivery

Tests: no limits; start only; end only; both; the four states on a graph with `causal`, `ruled` and no path; a
`linearized` pair deciding nothing; a reader with fewer shared assertions getting `unknown` where staff gets a state;
a hidden Event making the answer `unknown` with no Event named in any field or error; the bound and `limit_reached`;
filtering before pagination; deleting a referenced Event clearing the reference and leaving the staff note, which a
player cannot read; `as_seen_by` for staff, for a player's own being (limited to what the player may read) and refused
for another being; copy and release; and that `connection` still has no time column (the RFC 0048 scan).

## Excluded

Dates on a relationship, a default Event, a "now", an order created by a date or a Session, time-aware routing, belief
and confidence, and as-of reads of anything but relationships.
