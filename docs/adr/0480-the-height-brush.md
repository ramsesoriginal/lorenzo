# 0480 - The Height brush

Status: accepted, decided with the maintainer on 2026-11-17. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); the last of the planned tools of [ADR 0465](0465-maps-moves-into-the-web-shell.md), on the height lines of [ADR 0473](0473-the-height-line-tool.md) and the preview of [ADR 0475](0475-the-generator-contract.md). Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Context

The prototype paints a heightmap, a raster of heights. A Map holds no raster, and the decision on this tool is that it holds none now: the height lines of an entry are the truth, and a field of heights exists only in the page while the brush is used.

## Decision

- **The tool.** Height brush (group Terrain, key H), for one entry, chosen as with the drawing tools; an entry that is selected and is height lines is chosen at first. Not on a sphere. The Map needs no grid.
- **The entry is height lines or not on this Map yet.** An entry drawn here as anything else is refused, by name, before any stroke. Its lines must share one unit; lines of several units are refused the same way.
- **The field.** When the entry is chosen, a field of 128 samples across the sheet is laid over it, as many rows as keep the samples square. A sample within three quarters of a sample of a line holds that line's height. Every other sample holds the smoothest field between the lines: each one the mean of its four neighbours, worked out until it settles, with the sheet's edge holding nothing in or out. Beyond its last line the land is flat at that line's height, and is then raised by a quarter of a **Step** at the middle of a closed place that has no other line in it: up where the land rises to that line, down where it falls to it, and up for a line with nothing beside it. An entry with no lines starts flat at the **First height**.
- **A stroke.** Dragging raises the field, and dragging with Shift lowers it, around every point the pointer passes, by **Strength** steps at its middle and less towards **Radius**, along a smooth bell. A point of the field is moved once by a stroke, by the most any point of the stroke gives it, so going over the same place again in one stroke does nothing more; a new stroke does. `RAISE x,y` and `LOWER x,y` on the command line make a stroke at that one point.
- **Its options:** Step and Unit, at first those of the entry's lines (the smallest gap between two of their heights, and their unit); with fewer than two heights the Step is yours to give, and with no line the Unit and the First height too. Apply is off until they are given. Then **Radius**, as a share of the sheet's width (1 to 50 hundredths, 5 at first), **Strength** in steps (0.1 to 3, 1 at first), and **Role**, the role of a placement this writes for an entry not yet on the Map, isoline at first, as for a height line.
- **What is redrawn.** The heights are those of the entry's lines and every step from the lowest of them (from the First height on an empty entry) that the field reaches. At each height the field's height lines are traced by marching squares, as Fill by marching squares traces them ([ADR 0477](0477-the-fill-by-marching-squares-generator.md)), and a line that the sheet's edge cuts ends at the edge. A traced line is kept when it passes where the strokes changed the field; a line of the entry at the same height is dropped when a kept line passes near it, within two samples. Every other line of the entry stays exactly as it was drawn, a curve still a curve. A redrawn line is simplified to within a quarter of a sample, and loses any detail finer than the field.
- **The preview** draws the lines that would be added over the Map, and those that would go as they are, dashed. The preview line says how many lines are kept, redrawn and new. Compare, Apply and Discard are those of ADR 0475; Apply writes the entry's placement once, with the role it has or the Role option, and is one history step: "Height brush on Hills: 2 lines redrawn, 1 new". Discard drops every stroke.
- **The limits** are the placement's (ADR 0337): 256 parts, 2,000 points a part, 64 KiB. A result over one is refused in the preview with the limit named, as the generators do.
- **The pure parts** are in `apps/maps/src/lib`: the field from the lines, the stroke, and the lines to keep and to draw. The renderer exports the points of a curve it already works out (`bezierPoints`), so a curved line is read as it is drawn.

## Built

- **A place beyond its last line rises or falls only when it is closed**: one that reaches the sheet's edge stays flat at that line's height. So a stroke on open ground makes a hill out of flat land, and a line at the first height goes round its foot, where the land leaves the flat; the same holds for an entry with no lines.
- **A line a stroke passes over whose height the land there no longer has is gone**, and counted as such ("1 gone"), even when the stroke moved the land past every step.
- **Strokes that change no line yet** keep Apply off: "The strokes change no line yet. Go on, or use a larger Strength."
- **A result with no line left** is refused: Remove from this map takes an entry off the Map.
- **The entry is preselected** when the selected entry is height lines; the chooser says its lines are what the brush changes.
- **ROLL** is refused by name, as the brush has no seed.
- **The tool's options** are kept as the Fill by marching squares' First height and the Height line's Unit are, per tool; the Step is its own, more than nothing.

## Validation and delivery

Unit tests: a field from lines reproduces those lines at their heights; a summit and a hollow beyond their last lines; an empty entry; a stroke raises by Strength steps at its middle and not beyond Radius, and once per stroke; Shift lowers; only the lines near a change are redrawn, the rest kept part for part; a new height above the highest line; a result over a limit, and lines of two units, refused with their sentences. Browser tests against the real API: lines drawn with the Height line tool, a stroke, the preview, Apply writing one placement, undo; a stroke from the command line; an entry drawn as an area refused; axe in light and dark with the preview on.

## Excluded

A raster stored on the Map, a field read from a picture, smoothing and flattening brushes, a brush on a sphere, and shading by height: each needs its own decision.
