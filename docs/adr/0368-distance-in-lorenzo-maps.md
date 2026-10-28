# 0368 - Distance in Lorenzo Maps

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 11. Extends
[ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md) and [ADR 0365](0365-connections-in-lorenzo-maps.md)
for the reads of [ADR 0367](0367-the-distance-read.md). Desktop only.

## Decision

**A Map page can measure.** Below the list of places there is *Distance*: *From* and *To*, each one of
the places on the Map; *By the connections, measured in*, a choice of the library's numeric stats (a
number, with its unit) that is left empty to ask only for the straight line; and *Measure*. It asks for
the straight line on this Map and, when a stat is chosen, for the route, and says each answer in words:

- known: *Straight line: 40 miles* (with the metric of a grid, *counting diagonals by the alternating
  rule*), and *By the connections: 52 miles, over 3 legs*, the legs listed by name;
- partial: *By the connections: at least 12 miles; 2 of 4 legs have no length*, the legs without one
  marked;
- unknown or limit reached: the API's own reason, as it gave it (*no known route*, *the Map has no
  scale*);
- the same place twice is *0*, said as it is.

A number is written as the API gave it, with the unit the author chose, never converted or rounded to
look more sure. The page never says *you are here* and never treats a distance as a time.

**Setting up a grid says how it counts.** A square or rectangular grid has *Diagonals count as* in Make a
Map and in Settings: *Euclidean (the default)*, *The larger of the two (chebyshev)*, *Both added
(manhattan)* and *Every second one double (alternating)*, kept in the system's `metric`
([ADR 0366](0366-straight-line-distance-on-a-map.md)). A hex, a plane, a sphere and an outline do not
show it.

**What it does not do.** It does not draw the route on the Map, choose the route's mode for a person,
estimate a time, or measure across Maps.

## Validation and delivery

Unit tests of the words of each state. Browser tests against the real API: a writer sets up a square grid
with a metric and a measure and reads the straight line between two pins; a plane with a scale; a route of
two roads with a length is read as known and one road without a length as partial; two places with no
connection say *no known route*; the same place twice says 0; a player measures; axe in light and dark
with the section and its answer.

## Excluded

A route drawn on the sheet, choosing among several routes, time, a measure across Maps, and a form for
the hub or the stat definitions themselves.
