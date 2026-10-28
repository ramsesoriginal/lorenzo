# 0359 - Authoring on a sphere

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 8. Extends
[ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md) and [ADR 0356](0356-authoring-on-a-grid.md) for the
sphere of [ADR 0357](0357-the-sphere-system.md), drawn as
[ADR 0358](0358-projections-and-drawing-a-sphere.md) says. Desktop only.

## Decision

**Making and setting up a Map** offers a sixth kind, **a sphere**. Its extent is not asked for (it is
the rectangle of longitudes and latitudes). It asks for an optional **radius** (an amount and a unit in
the author's words) and for how it is **drawn**: *Flat* (equirectangular), *Mercator*, or *Globe*, the
last with the longitude and latitude it faces. The drawing is saved with the Map as its first view and
a reader may change it for themselves (below). The other kinds' fields are not shown, and a plane or
an outline is not given a projection. The 409 of ADR 0357 is shown as that of ADR 0354 is, with the
draft kept.

**Looking.** The pointer over a sphere says where it is in words, *40.1 degrees N, 12.5 degrees E*
(written with the degree sign; four decimals are stored, one is shown), nothing on the globe's far
side or outside its disc; a selected place says where it is as **At** and its position, a line or an
area as the position of the middle of its box. The **Grid** switch draws and hides the lines of
longitude and latitude. On a globe the page has **Turn** buttons (west, east, north, south, by 15
degrees, and one back to the saved centre) that change what this reader sees and nothing stored; a
reader's choice of the flat or round projection is likewise theirs alone and is kept with their other
local choices.

**Drawing.** The tools Pin, Line and Area work as on a plane, and **Circle**, **Cells**, curves and
**Snap to the grid** are not offered on a sphere. A press on the sheet is a longitude and a latitude
(clamped into their ranges); on the globe a press outside the disc does nothing. A line or an area that
has to cross the antimeridian is drawn as two parts, which the tool says when a segment would be
longer than half a turn. The numeric fields of a place are labelled **Longitude** and **Latitude** and
refuse a value outside their ranges before they are sent; the API refuses it as well (ADR 0357).

**What is not here.** Dragging to spin the globe, great-circle lines, caps and circles, distance, and
any change to what an entry's place means: a sphere is a drawing like any Map and never says where an
entry is.

## Validation and delivery

Unit tests for the words of a position (hemispheres, the equator, the prime meridian, rounding at the
ends), the clamping of a pointer, and the antimeridian rule of the tools. Browser tests against the
real API: a writer makes a sphere with a radius and a pin, a line and an area on the flat view, turns
to Mercator and to the globe and sees the same places, turns the globe and loses a pin behind the
limb, reads the pointer's words, is refused with the draft kept when a Map with places is made a plane,
and a player sees the sphere, the words and the turn buttons with no tools; axe in light and dark on
the flat and the round view.

## Excluded

Spinning by dragging, a sphere's own scale bar and compass, a prime meridian other than 0 in the
interface, and a place described by its cell.
