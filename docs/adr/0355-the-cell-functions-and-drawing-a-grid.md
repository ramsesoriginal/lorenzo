# 0355 - The cell functions and drawing a grid

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 7. Extends
[ADR 0337](0337-geometry-roles-and-the-validator.md) (the one validator, a golden corpus) and
[ADR 0339](0339-the-map-renderer.md) (a pure layout to a Scene) for the grids of
[ADR 0354](0354-grid-systems-square-rectangular-and-hex.md).

## Decision

**The cell functions are pure and exist twice, with one golden file.** `packages/map-engine`
(Python, authoritative) and `packages/map-renderer` (TypeScript) each have, for a validated grid
(a system of a grid kind or a view's grid):

- `cell_at(grid, point)`: the `(col, row)` of the cell a point belongs to by the convention and the tie
  rule of ADR 0354, for any point (a cell outside the sheet has a negative or large address);
- `cell_centre(grid, cell)` and `cell_polygon(grid, cell)`: the centre and the corners, a square or
  rectangle clockwise from its near corner, a hex from the corner at the lowest angle given in ADR 0354;
- `in_grid(grid, extent, cell)`: whether the cell is in the grid (ADR 0354: not before column or row
  0, and its centre before the far edges);
- `cell_count(grid, extent)`: how many cells the grid has.

`packages/map-engine/golden/cells.json` holds vectors for each kind and orientation (points to cells,
including each tie and a point outside the sheet; cells to centres and corners; the counts), and both
test suites read it. Nothing else in the API reads a cell: they are for the renderer, the editor and
the distance of a later slice.

**The renderer draws the grid.** A `MapModel` may carry `overlay`, the view's grid; a system of a grid
kind is its own grid. The Scene gains grid primitives, drawn above the sheet and below every placement,
with no entry, no accessible name and no hit: cell edges in one path of class `m-grid`, and the
sub-grid in one of class `m-grid-sub`. Only what is in the viewport is generated.

- *Squares and rectangles*: the lines across the visible part of the extent.
- *Hexes*: the outline of each visible cell that is in the grid (a shared edge is drawn twice).
- *The sub-grid of a hex* is drawn from a lattice of its own, anchored at the centre of cell `(0, 0)`:
  aperture 4 has the parent's orientation and half its size, aperture 3 the other orientation and
  `size / sqrt(3)`, aperture 7 the parent's orientation turned by `atan(sqrt(3)/5)` (about 19.1
  degrees) and `size / sqrt(7)`. It is a drawing of the idea of a finer grid, never an address.
- *Level of detail*: cells whose shortest side is under 6 pixels on the screen are not drawn, and a
  sub-grid whose cells are under 8 pixels is not; at most 6,000 cells are drawn at once. `gridState`
  says `drawn`, `too_fine` or `none`, so the page can say "zoom in to see the grid".

`Groups` gains `grid` (on by default), the third switch beside Places, People, Roads, Names and Show
places; it hides the grid and the sub-grid together. The stylesheet gives `m-grid` and `m-grid-sub`
brand tokens only, in every theme, and nothing in the Scene changes for a Map without a grid.

## Validation and delivery

Renderer: the golden vectors; the grid primitives for each kind and orientation (counts, classes,
order, no hit), the level of detail and its limit, each aperture's lattice, a view grid over a plane,
and that a Map with no grid has the Scene it had. Engine: the same vectors in Python and the
properties that matter (the centre of a cell is in that cell, a cell's corners are at the distance the
convention says, every cell has six or four neighbours at the right distance).

## Excluded

Distance, neighbours and paths, snapping (the editor's, ADR 0356), a grid that follows a picture, and a
theme that draws the grid differently.
