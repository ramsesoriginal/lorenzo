# 0471 - The Spline tool

Status: accepted, decided with the maintainer on 2026-11-16. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); follows [ADR 0421](0421-maps-redesign.md) and [ADR 0465](0465-maps-moves-into-the-web-shell.md), which ask for an ADR per planned tool. Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Decision

- **The tool.** Spline (group Draw, key S): a click or a typed `x,y` for each point, Enter, a double click or `DONE` to finish, Backspace to take back a point, Escape to cancel, as Line. At least two points. Not on a sphere.
- **Its output is a line that is a curve:** one placement of one open `bezier` part ([ADR 0337](0337-geometry-roles-and-the-validator.md)), which the renderer already draws. The role is none, set in the panel as for a line.
- **The curve goes through every point.** It is a cardinal spline: at a point the curve runs along the line from the point before to the point after, scaled by `(1 - tension) / 2`; an end uses itself for its missing neighbour; a cubic segment's controls are a third of that from each of its ends. **Tension** is the tool's one option, a number from 0 (the roundest) to 1 (straight) in steps of 0.05, 0.5 at first, set as [ADR 0470](0470-a-tool-declares-its-options.md) says. Coordinates are kept to two decimals.
- **The limit.** The start and three for each segment count toward a placement's 2,000 vertices, so a spline has at most 666 segments, which is 667 points; the tool says so at the last one.
- **The editor learns it.** A placement of one open bezier whose controls are those of a spline, at one tension of two decimals, to 0.02 of a unit, is edited by its through-points: handles to drag, the points as numbers with add and remove, and its tension as a field. Every control is derived again on each change. Any other bezier stays "Drawn with the API" and is kept as it is.
- **The pure parts** (points and tension to a part, a part back to points and tension) live in `apps/maps/src/lib`; nothing else draws splines.

## Built

As decided. The prototype drew a spline as a kind of its own with its tension kept beside it; here the tension is read back from the curve, because the geometry format holds nothing but the curve.

## Validation and delivery

Unit tests: the part for two, three and many points at tensions 0, 0.5 and 1; the round trip from a part to its points and tension; a bezier that is not a spline is not read as one; the point limit. Browser tests against the real API: a spline drawn by pointer and by typed points, a through-point moved by handle and by number, the tension changed, undo and redo; axe in light and dark with the tool on.

## Excluded

A closed spline (an area with a curved edge), editing a bezier's controls by hand, and splines on a sphere.
