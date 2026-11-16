# 0474 - Editing the parts of a placement

Status: accepted, decided with the maintainer on 2026-11-16. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); follows [ADR 0421](0421-maps-redesign.md) and [ADR 0465](0465-maps-moves-into-the-web-shell.md), which ask for an ADR per planned tool. Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210). Extends [ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md), which edits a placement of one part.

## Context

A placement of several parts shows "Drawn with the API". The generators write one entry with many parts ([ADR 0475](0475-the-generator-contract.md)), and a set of height lines is one entry of many lines, so what they make could not be touched after.

## Decision

- **The panel lists the parts** of a selected placement that has more than one, each named by what it is and its number ("Area 3", "Height line 2, 250 m"). Choosing one shows its handles on the Map and its points as numbers, exactly as a placement of one part is edited; a click on a part in the drawing chooses it.
- **What a part can be:** a point, a circle, a line, a spline ([ADR 0471](0471-the-spline-tool.md)) or an area. An area's holes are listed under it as rings, each edited as an area's outline is; removing the outer ring removes the part. A bezier that is not a spline is listed and kept, with no handles.
- **A part's value and unit** are two fields, as [ADR 0473](0473-the-height-line-tool.md) says.
- **A part can be removed,** except the last: that is *Remove from this map*.
- **One change is one write** of the whole placement and one history step, named for the entry. A refusal (a ring that now crosses another, a limit) is shown as given and nothing changes.
- **Cells stay cells.** A placement whose every part is a cell is edited by the Cells panel, as before ([ADR 0356](0356-authoring-on-a-grid.md)).

## Built

As decided, with these details:

- **What is edited part by part:** a placement of several parts, and one area with holes. A placement of one simple part is edited as before, with no list.
- **Names.** A part is numbered among its own kind: Point, Circle, Line, Curve, Area, Curved area, and Height line for a line or a curve that carries a value ("Height line 2, 250 m"). A hole is "Hole 1 of Area 3".
- **Choosing in the drawing.** A press on the selected placement chooses the part under the pointer: a pin or a line within 8 screen pixels before a circle or an area, and no area inside its hole.
- **Dragging.** A handle moves one point. The body of an area dragged moves the area with its holes; a hole chosen and dragged moves that hole alone.
- **An area's value** stays with its outline; a hole carries none.
- **The message** "Drawn with the API" is now only for a curve that is no spline: "it is shown and kept, and its points are not changed here."
- **Height line adds** ([ADR 0473](0473-the-height-line-tool.md)): drawing a Height line for an entry whose every part is a line or a curve with a value adds the line as one more part, up to the 256 a placement holds, and says so before it is drawn.

## Validation and delivery

Unit tests for the pure parts: a part replaced, a ring replaced, a part removed, the names of parts, value and unit kept by every edit. Browser tests against the real API: a placement of several parts written through the API is opened, a point of one part moved by handle and by number, a hole moved, a part removed, undo and redo; axe in light and dark.

## Excluded

Adding a part by drawing (but for a height line, ADR 0473), joining and splitting placements, moving a part to another entry, and boolean operations on areas.
