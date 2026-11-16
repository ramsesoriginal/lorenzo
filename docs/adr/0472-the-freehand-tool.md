# 0472 - The Freehand tool

Status: accepted, decided with the maintainer on 2026-11-16. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); follows [ADR 0421](0421-maps-redesign.md) and [ADR 0465](0465-maps-moves-into-the-web-shell.md), which ask for an ADR per planned tool. Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Decision

- **The tool.** Freehand (group Draw, key F): after choosing what is drawn, press, drag and release on the sheet. The stroke is shown as an overlay while it is drawn; Escape during the drag drops it. Not on a sphere. Snapping does not apply.
- **Its output is a line:** one placement of one `polyline` part, role none, edited afterwards as any line.
- **The stroke is simplified** by the Ramer-Douglas-Peucker rule: a sample is dropped when it lies nearer than the tolerance to the line between the samples kept on either side. **Tolerance** is the tool's one option, in screen pixels (0.5 to 10 in steps of 0.5, 2 at first), so the same hand gives the same line at any zoom; it is turned into drawing units by the zoom the stroke was drawn at.
- **A stroke always fits.** If the simplified line has more than a placement's 2,000 vertices, the tolerance is raised by half, again and again, until it fits, and the tool says the line was made coarser. Coordinates are kept to two decimals and a point equal to the one before it is dropped; a stroke with fewer than two points left makes nothing and says so.
- **The keyboard path is the Line tool.** A stroke is a path gesture and has no typed twin of its own; the tool's text says that Line draws the same thing point by point.
- **The pure parts** (the simplification and the fitting) live in `apps/maps/src/lib`.

## Built

As decided. Each sample's weight under the rule is worked out once for a stroke, so raising the tolerance to fit does not walk the stroke again; the line is the same as applying the rule afresh at each tolerance. A stroke that leaves the sheet goes on where it comes back. A typed point is refused with a pointer to the Line tool.

## Validation and delivery

Unit tests: the simplification on straight, bent and closed strokes and at several tolerances; the fitting to the vertex limit; duplicates and a stroke that is too short. Browser tests against the real API: a stroke drawn by pointer becomes a line that can be edited, Escape drops it, undo and redo; axe in light and dark with the tool on.

## Excluded

Pressure, smoothing into curves, a freehand area, and drawing on a touch screen below the width that offers drawing.
