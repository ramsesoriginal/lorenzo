# 0364 - Links derived from connections

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 10. Reads the connections of
[ADR 0363](0363-connections-the-kind-and-its-two-ends.md) against the placements of
[ADR 0336](0336-maps-the-kind-its-system-and-its-placements.md). Nothing here is stored.

## Decision

**A link is a connection seen from one place on a Map.** `GET /tenants/{t}/maps/{map_id}/links`
returns, for the entries the reader sees placed on that Map, the connections they are an end of:

```json
{"items": [{"connection": {"id", "name", "slug", "kinds"}, "here": {"id", "name", "slug", "kinds"},
            "other": {"id", "name", "slug", "kinds"}, "direction": "both" | "out" | "in",
            "other_maps": [{"id", "name", "slug", "kinds"}]}],
 "truncated": false}
```

- `here` is the end that is placed on this Map and `other` the end at the far side. A connection whose
  two ends are both placed on the Map gives two rows, one from each end. `direction` is `both` for a
  way that goes both ways, `out` for a one-way connection that leaves `here` and `in` for one that
  arrives at it.
- `other_maps` are the Maps the other end is placed on and that the reader may see, this one left out,
  ordered by name then id. It is what makes a portal on one Map lead to a pin on another; it is never a
  claim about where anything is.
- A row exists only when the reader sees the Map, the connection, both ends and the placement of `here`,
  and a map shown to the reader is only one they can see; a hidden connection, end or Map is absent
  without a trace, as in every read of ADR 0363. The visibility predicate is applied in SQL.
- At most 500 rows, ordered by `here` name, `other` name and connection id; `truncated` says there were
  more. There is no total and no counter.
- It is derived at read time from the endpoints alone. It never reads a drawn polyline, a placement's
  geometry or a Location's place; redrawing a road never changes it. No row is cached or stored, and no
  link feeds routing, distance or reach.

**One read answers a Map page.** The page reads the links once with the Map and indexes them by `here`;
a selected entry shows its own. A reader of the Locations pages reads the connections of one Location
with `GET /connections?end=` (ADR 0363) and says each direction in words from its two ends.

## Validation and delivery

Tests: a portal between two Maps (a row with `other_maps`), a connection with both ends on one Map (two
rows), the three directions, a hidden Map, end, connection or placement leaving no trace and no count,
two libraries with a hidden end and with none answering alike, the cap and `truncated`, that moving a
drawn road changes nothing, and that no module that reads reach reads the links.

## Excluded

Following a link as a route (the distance slice), a link between entries that no Map places, links
across libraries, and any stored or cached link.
