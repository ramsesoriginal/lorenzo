# 0357 - The sphere system, its geometry and its projection

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 8. Adds the sixth kind to the
system document of [ADR 0336](0336-maps-the-kind-its-system-and-its-placements.md), a rule for
geometry on it ([ADR 0337](0337-geometry-roles-and-the-validator.md)) and a projection to
`map.view` ([ADR 0354](0354-grid-systems-square-rectangular-and-hex.md)).

## Decision

**A sphere is a system of kind `sphere`** in `lorenzo.map-system/1` (the format string does not
change):

```json
{"format": "lorenzo.map-system/1", "kind": "sphere", "extent": [-180, -90, 180, 90],
 "radius": {"value": 6371, "unit": "km"}}
```

- Its positions are **longitude and latitude in degrees**: `[longitude, latitude]`, longitude from -180
  to 180 (east positive, 0 at the prime meridian the author chose) and latitude from -90 to 90 (north
  positive). Storage is the rectangle of those numbers; the extent is that rectangle exactly and a
  `sphere` with another is refused, so it is written out and never defaulted. Latitude is north-up,
  unlike the y-down sheet of a plane, because that is what the numbers mean; the renderer turns it
  (ADR 0358).
- `radius` is optional: the world's radius, a positive number of a `unit` of at most 32 characters in
  the author's words. Without it nothing is measured and no unit is invented. A sphere takes no
  `scale`, `cell`, `measure`, `sub` or `orientation`.
- There is no wrap and no seam handling. A sphere Map is the rectangle: a region that crosses the
  antimeridian is two parts, one on each side, and a region around a pole runs along the top or bottom
  edge. A segment between two points is the **straight line between them in longitude and latitude**,
  whatever the projection draws it as; a great-circle segment is a distance, which is a later slice's
  function and never a drawing.

**Geometry on a sphere** (ADR 0337 otherwise as it is): a part is a `point`, a `polyline` or a
`polygon`. A `circle` and a `bezier` are refused, because a circle of drawing units and a curve through
degrees mean nothing on a sphere (a spherical cap is a later decision; an area is drawn as a polygon).
Every coordinate is within its range, to the six decimals of ADR 0337. A polygon's simplicity is
checked in the rectangle as for a plane. The validator takes the system with the geometry:
`validate_placement(geometry, role, style, z, system=...)` is called by the single write, the batch, the
repository copy and the repository update with the Map's own system, and a placement written for any
other kind is as before.

**A projection is a drawing choice.** `map.view` may hold, for a sphere only,
`{"projection": {"kind": "equirectangular" | "mercator" | "orthographic", "centre": [lon, lat]}}`;
`centre` is for `orthographic` only (the point facing the viewer, `[0, 0]` when not said) and is refused
for the others. A view's `grid` is refused on a sphere, which draws its own lines of longitude and
latitude (ADR 0358). No projection is the equirectangular one. The projection is read by nothing but
the renderer and changes no stored position.

**Changing a system that has placements.** As ADR 0354 says for hexes, turning a Map into a sphere or
out of one is a **409** once any placement exists (the numbers would mean something else); every other
change is allowed as before. Changing the radius or the projection never refuses.

**Format 21.** The release document is format 21 so that an older server refuses a repository holding a
sphere or a projection plainly, instead of reading the Map as an outline; its v20 reader changes
nothing. Nothing is migrated: `map.system` and `map.view` are the columns they were.

## Validation and delivery

`packages/map-engine`: the golden corpus gains accepted and refused spheres (a wrong extent, a `scale`,
a zero radius) and the view's projections (a centre on a flat one, a centre out of range, a grid on a
sphere), and geometry on a sphere (every shape, a circle and a bezier refused, every coordinate just
inside and just outside). API: create, replace and read a sphere and a projection, the 409 into and out
of sphere with places and none without, the placements' range check on the single write, the batch, the
copy and the update, the v20 reader.

## Excluded

Distance on a sphere (a later slice, with golden vectors), a spherical cap, a wrapped region as one
part, a prime meridian other than 0 beyond the author's own meaning, other projections, and a sphere
with a picture on it.
