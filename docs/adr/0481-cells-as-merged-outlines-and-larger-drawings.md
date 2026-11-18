# 0481 - Cells as merged outlines, and larger drawings

Status: accepted, decided with the maintainer on 2026-11-17. Amends the limits of [ADR 0337](0337-geometry-roles-and-the-validator.md) and how [ADR 0356](0356-authoring-on-a-grid.md) writes a region of cells. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps). Tracked in [#1267](https://github.com/ramsesoriginal/lorenzo/issues/1267).

## Context

A region of cells is written as one polygon part for each cell (ADR 0356), and a placement holds at most 256 parts (ADR 0337), so one entry holds at most 256 cells. A dungeon's floor, a tournament table's terrain or a fill by wave function collapse ([ADR 0479](0479-the-fill-by-wave-function-collapse-generator.md)) passes that soon. Merging cells into outlines alone does not help where cells lie scattered, which a fill often leaves; a larger limit alone runs into the 2,000 vertices four-cornered cells use up at 500.

## Decision

- **The limits of a placement's geometry are raised** for every placement, as the validator cannot tell a drawing of cells from any other: **256 KiB** (from 64 KiB), **8,000 vertices** (from 2,000) and **1,024 parts** (from 256). The engine (`packages/map-engine`) and its mirror in the browser have the same numbers. The other limits stay: 5,000 placements on a Map, 100 writes in a batch. The largest batch is so 100 times 256 KiB, about 25 MB, under the 32 MB a request may carry where the API runs ([ADR 0011](0011-deploy-target-cloud-run-neon.md)).
- **Cells are written as outlines.** The cells of a region with no value form patches, cells that share an edge; each patch is one polygon part, its outline and its holes, running along the cells' edges, with a straight run along several cells written as one edge. A cell that carries a value and a unit (ADR 0337) stays a part of its own, so its value stays its own. A patch whose outline would meet itself at a point, which squares and rectangles allow where two of its cells meet only at a corner, is written as its cells, one part each.
- **Cells are read from outlines.** A polygon part is cells when every edge of its rings runs along cells' edges and its rings are exactly the outline of the cells whose middles lie inside it. Nothing is stored to say so; it is worked out from the Map's grid, as ADR 0356 does for one cell. A part that is the polygon of one cell is read as before, so the drawings written so far stay cells, and are written as outlines the next time they change.
- **No count of cells is fixed.** The Cells tool and the fill by wave function collapse refuse a result over the placement's limits with the limit named, as the generators do ([ADR 0475](0475-the-generator-contract.md)); the 256 cells of ADR 0356 and ADR 0479 go.
- **The tools take their limits from the one table:** the most points of a freehand line and a spline, and the most parts of a drawing.

## Built

- **Measured** before the limits were loosened, on the machine the tests run on. The engine's validator takes 24 ms for one polygon of 7,999 vertices, 22 ms for 1,024 hexes (6,144 vertices) and 20 ms for a line of 8,000 points of six decimals, with no polygon over the simplicity budget. A Map of 20 placements of 1,024 lone cells each (20,480 parts, 81,920 vertices) opens and is drawn in 1.1 s, and a step of zoom is drawn again in about 300 ms. A freehand stroke of 8,000 samples is simplified in 19 ms; the worst stroke for the simplifier, every sample a corner, takes 1.2 s.
- **The area a fill works in is never one of its tiles.** An area drawn along the grid's lines reads as cells, so the selected area of a fill by wave function collapse ([ADR 0479](0479-the-fill-by-wave-function-collapse-generator.md)) could have been learned from and changed. It is left out of the example and left as it is; a person who wants the whole sheet after drawing an example clears the selection first (Escape).
- **One area along the grid's lines keeps its points.** It is listed as cells and its points can still be changed, and a Location drawn so can still place its children; a drawing of cells of several parts is changed by its cells, as before.
- **No cell or fill option reaches the limits any more**: the finest caves (Size 96) and fills (Scale 20, 8 height lines) stay within 8,000 vertices. Their ranges are not widened here.
- The Cells tool takes at most 10,000 cells at once, the most a fill works out; what can be written is decided by the limits when it is.

## Validation and delivery

Unit tests: outlines for squares, rectangles and both hexes, with holes, straight runs joined, cells with a value kept apart, a patch that meets itself at a corner written as cells, and the round trip: the cells read from what was written are the cells written. A drawing of one part a cell still reads. Golden vectors of regions and their outlines that the TypeScript tests reproduce and the engine accepts, with each outline's corners on the grid. The limits in the engine, the mirror and the golden corpus, at and over each new bound. Browser tests against the real API: more than 256 cells drawn with the Cells tool and filled by wave function collapse, written as outlines, read back as cells, undone.

## Excluded

A part shape that stores cells by their addresses, rewriting the drawings already stored, and a cell count that differs by grid.
