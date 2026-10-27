# 0358 - Projections and drawing a sphere

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 8. Extends
[ADR 0339](0339-the-map-renderer.md) (`project` is the one place a stored position becomes a drawing
position) and [ADR 0355](0355-the-cell-functions-and-drawing-a-grid.md) (what is drawn under the
placements) for the system of [ADR 0357](0357-the-sphere-system.md). Pure TypeScript; the engine does
not mirror it, as nothing in the API reads a drawing position.

## Decision

**`project` and `unproject`.** For a system of kind `sphere` the renderer's `System` carries the
projection of the Map's view (the app merges `view.projection` into it, as it does the overlay), and
`project(system, [lon, lat])` gives a point of the **projected sheet**, in drawing units, where one unit
is one degree along the equator (the globe: 90 units to the limb). `unproject(system, point)` is its
inverse, for the pointer: it gives longitude and latitude, clamped into their ranges, and for the globe
a point outside the disc is moved onto the limb. For every other kind both are the identity. `extentOf`
is the extent of the projected sheet, so that fitting, panning, zooming and the design unit
(1/1000 of the sheet's width) follow without a second path.

| Projection | A position is drawn at | The sheet |
| --- | --- | --- |
| `equirectangular` | `[lon, -lat]` | `[-180, -90, 180, 90]` |
| `mercator` | `[lon, -m(lat)]`, `m(lat) = deg(ln(tan(pi/4 + lat/2)))`, latitude held to +-85.0511287798 (so `m` is +-180) | `[-180, -180, 180, 180]` |
| `orthographic` of centre `(l0, p0)` | `[90 cos(p) sin(l - l0), -90 (cos(p0) sin(p) - sin(p0) cos(p) cos(l - l0))]` | `[-100, -100, 100, 100]`, a disc of radius 90 |

A latitude beyond the Mercator limit is drawn on the sheet's edge. On the globe a position is visible
when `sin(p0) sin(p) + cos(p0) cos(p) cos(l - l0) >= 0`; a position that is not is moved to the limb
(its drawn point scaled to radius 90) so that every number stays finite. The inverse of the globe is
the usual one from the radius `rho` of the point (`c = asin(rho / 90)`) and is exact on the visible
hemisphere; the Mercator inverse is `lat = deg(2 atan(exp(-y)) - 90 deg)`.

**Shapes.** A segment is straight in longitude and latitude (ADR 0357), so for the equirectangular
projection a line is drawn as it is stored. For the others a segment is cut into samples, one at most
every 2 degrees of its longer span and at most 180 per segment, and each sample is projected. On the
globe a line is cut where it goes behind the limb, the crossing found by bisection, and is drawn as
the runs in front; a pin behind the limb is not drawn; an area is drawn with its hidden vertices on the
limb, and not at all when none of its vertices is in front. A hole is treated as the ring it is. Every
mark of a placement is built from these points, so a theme, the hit test and the labels are unchanged:
the only change in the Scene is the path data.

**The lines of longitude and latitude** are the sphere's grid, drawn under the placements as paths of
class `m-grid` when the **Grid** switch is on, with the globe's limb as a circle of class `m-limb` drawn
above the sheet whether it is or not. The step is the smallest of 90, 45, 30, 15, 10, 5, 2 and 1
degrees whose spacing at the centre of the view is at least 40 screen pixels and whose samples (the
globe's lines are sampled every 3 degrees, the others are straight lines) are at most 30,000, and
`gridPrims` reports `drawn` as for any grid. The brand tokens of `.m-grid` apply; `.m-limb` takes a
strong border and no fill.

**Turning the globe** is changing the projection's centre: the controller keeps the view's zoom and
centre as before, and the host sets `System.projection` with `setModel`. Nothing in the renderer
rotates by dragging.

**The pointer.** `ToolEvent.point` is in the units the geometry is stored in: `unproject` is applied
once, where the event is made, so a tool that writes `point` writes a valid longitude and latitude
and the tools of the app need no knowledge of projections. On the globe a press outside the disc is
not given to a tool. `placementCentre` is a stored position; `centreOn(entry)` projects it before it
moves the view.

## Validation and delivery

Unit tests of the arithmetic against known positions (the centre of each projection, the equator and
the prime meridian, 90 degrees east on the globe, the limb) and a round trip of `unproject(project(p))`
over a lattice of each projection; the Scene of a line over the antimeridian, of a line behind the
limb and of an area half behind it; the graticule's steps and its sample cap; the hit test over a
projected line; and that a Map with no sphere has the Scene it had.

## Excluded

Dragging to turn the globe, a central meridian for the flat projections, other projections, great
circles as lines, a hemisphere clip of an area at the exact limb curve, shading or a night side, and
labels placed to follow a curve.
