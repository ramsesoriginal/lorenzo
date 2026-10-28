# 0366 - Straight-line distance on a Map

Status: accepted with the maintainer on 2026-10-28; RFC 0048 slice 11. A pure function of a Map's
system and two positions, in `packages/map-engine`, read by the distance read of
[ADR 0367](0367-the-distance-read.md). It never reads a connection and never says where an entry is.

## Decision

`lorenzo_map.straight_distance(system, a, b)` takes a validated system and two stored positions and
returns `{value, unit}` or a refusal that says why there is no answer. Positions are the stored units of
the system ([ADR 0336](0336-maps-the-kind-its-system-and-its-placements.md),
[ADR 0357](0357-the-sphere-system.md)); the position of a placement is the centre of its bounding box (a
pin's own point), which the placement's stored box already holds. The answer is a number and the unit
the Map's author gave, and is never converted:

| The Map is | Distance | In the unit of | When the Map has none |
| --- | --- | --- | --- |
| `plane` | the euclidean distance in sheet units times `scale.per_unit` | `scale.unit` | unknown: the Map has no scale |
| `square` or `rect` | the cells of the two points counted by the Map's `metric`, times `measure.per_cell` | `measure.unit` | unknown: its cells have no size in the world |
| `hex` | the number of hex steps between the two cells, times `measure.per_cell` | `measure.unit` | the same |
| `sphere` | the great-circle distance, by the haversine, times the radius | `radius.unit` | unknown: the world has no radius |
| `outline` or a kind this version does not know | none | none | unknown: an outline measures nothing |

**Cells.** A point's cell is the one ADR 0354 names, tie rule included, whether or not it is in the grid.
Between cells `(c1, r1)` and `(c2, r2)`, with `dc = |c1 - c2|` and `dr = |r1 - r2|`:

- `chebyshev`: `max(dc, dr)`; `manhattan`: `dc + dr`; `euclidean`: `sqrt(dc^2 + dr^2)`;
- `alternating`: `max(dc, dr) + floor(min(dc, dr) / 2)`, every second diagonal step counted double.

A rectangular cell is one cell in each direction, as a square is: the metric counts cells and never the
sheet's units. On a hex grid the offset addresses of ADR 0354 become cube coordinates (odd rows shifted
for `pointy`, odd columns for `flat`) and the distance is `max(|dx|, |dy|, |dz|)`, so a neighbour is 1.
The same cell is always 0.

**The metric is a field of the system.** A `square` or `rect` system may say
`"metric": "chebyshev" | "manhattan" | "euclidean" | "alternating"`; without it a Map counts
`euclidean`. The key is refused on every other kind. It is only read by this function and changes no
stored position, so changing it is never a 409. The release document is format 24 (its v23 reader
changes nothing), so that a server that does not know the key refuses a repository holding it plainly.

**Golden vectors.** `golden/distance.json` holds, for each kind, metric and orientation, pairs of
positions with their answer and the cases that have none, and the Python tests read it; the properties
that must hold are tested over a lattice: zero for the same cell, symmetry, the triangle inequality for
the metrics that have one, six neighbours of a hex at 1 and `6n` at `n`, and the great circle of a
quarter turn of a unit sphere.

## Validation and delivery

Engine: the golden vectors, the properties, a `metric` on each kind (accepted on a square and a rect,
refused on a plane, a hex, a sphere and an outline, refused when unknown), and that a system without it
validates as before. API: the v23 reader and the key through the Map routes, copy and update.

## Excluded

A distance across Maps, levels or scales, a path along a grid, line of sight, a metric of a plane, a
geodesic on an ellipsoid, and any conversion between units.
