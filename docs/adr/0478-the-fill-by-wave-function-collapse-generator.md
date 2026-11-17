# 0478 - The Fill by wave function collapse generator

Status: accepted, decided with the maintainer on 2026-11-17. Part of [RFC 0050](../rfcs/0050-the-web-interface.md) (slice UI-E, Maps); the third generator of [ADR 0475](0475-the-generator-contract.md), and the one it names as writing a placement for each of several entries. Tracked in [#1210](https://github.com/ramsesoriginal/lorenzo/issues/1210).

## Context

The prototype fills a grid from built-in tile sets ("coast", "caves"). Nothing in Lorenzo is seeded, and a tile set is a setting, so the tiles and their rules have to come from the person.

## Decision

- **The tool.** Fill by wave function collapse (group Generate, key W), on a Map with a grid of squares, rectangles or hexes. Not on a sphere.
- **The example is what is already drawn.** Every placement of the example Map that is a region of whole cells ([ADR 0356](0356-authoring-on-a-grid.md)) is read. The **tiles** are the entries drawn there, and **nothing** is a tile too: a cell with no entry, counted inside the box of columns and rows around the example's cells, so a result can leave gaps where the example does. Where two entries hold the same cell, the cell is the one drawn on top (the higher drawing order, then the later entry).
- **The rules are learned, not written:** for each direction a cell has a neighbour in (four on squares and rectangles, six on hexes), which tile was seen beside which in the example, and how often each tile was seen at all. Nothing is stored; the rules are worked out again from the example each time.
- **The example Map** is this Map or another Map of the library with a grid of the same kind (and, for hexes, the same orientation); the size of a cell may differ, since a cell's address is derived and never stored. It is an option, **Example**, and is this Map at first.
- **The region to fill** is the cells whose middle lies in the region ADR 0475 names: the selected area or circle, else the whole sheet. The example is read before anything changes, so the region may lie over the example itself.
- **The algorithm.** Every cell of the region may at first be any tile. Again and again the cell with the fewest tiles left (the first in order among equals) takes one of them, drawn from the seed in proportion to how often each was seen, and what its neighbours may still be is narrowed by the rules, and theirs in turn. Cells outside the region are not looked at. If a cell is left with no tile, the whole is begun again with the next draw, ten times at most; then the preview says **"No tiling fits these rules here. Roll another seed."** and there is nothing to apply.
- **Its output** is one placement of cells for each tile that is an entry, in one batch ([ADR 0351](0351-writing-placements-in-bulk.md)): the cells the entry had outside the region are kept, those it had inside are replaced by what the fill gave it, and an entry left with no cell on this Map is taken off it. A cell that keeps a value keeps it ([ADR 0337](0337-geometry-roles-and-the-validator.md)). The entries, their roles, lines and drawing order are those they have; there is no entry to choose and no Role option.
- **The limits.** A placement holds 256 cells, so a tile that would hold more after Apply, kept cells included, refuses the result in the preview, naming the tile and saying to select a smaller area. More than 100 tiles is more than one batch and is refused the same way. A region of more than 10,000 cells is not worked out at all: the page would stand still for it.
- **The preview** draws each cell of the result in the tone of its tile, one of six strengths of the overlay's colour, and the panel lists every tile by name with its tone and how many cells it would get, so the tone is never the only way to tell. The renderer's overlay gains the tones.
- **Its options** are Example and ADR 0475's Seed.
- **The history step** is "Filled by wave function collapse, seed 4821: 120 cells of 3 tiles in the whole sheet", and it holds the change to every entry, so undo puts all of them back in one batch.
- **The pure parts** are `collapse.ts` (learning and solving) and `cell-neighbours.ts` in `apps/maps/src/lib`. Golden vectors are in `packages/map-engine/golden/collapse.json`: the TypeScript tests reproduce each result, and the Python tests check with the engine's own cell functions that every cell of it is a cell of the grid.

## Validation and delivery

In two slices: the tool with this Map as its example, then the Example option for another Map.

Unit tests: the neighbours of a cell on each kind of grid, each a cell's width away and each way matched by its opposite; the rules learned from an example, nothing included and the top entry winning; a result that obeys every learned rule, across seeds and grids; the same seed twice; rules that cannot be met; the cells of a region; kept and replaced cells, a tile over 256 and its sentence; the golden vectors. Browser tests against the real API: an example drawn with the Cells tool, the preview and its list, Apply writing one batch that keeps what lay outside the region, the history step, undo; a Map without a grid does not offer the tool; axe in light and dark with the preview on.

## Excluded

Small Maps used as tiles, turning and mirroring tiles, rules a person writes, patterns larger than one cell beside another, and any change to the 256 cells a placement holds: each needs its own decision, the last a measurement.
