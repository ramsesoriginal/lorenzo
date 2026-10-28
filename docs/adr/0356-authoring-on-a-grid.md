# 0356 - Authoring on a grid

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 7. Extends
[ADR 0353](0353-authoring-a-map-in-lorenzo-maps.md) for the grids of
[ADR 0354](0354-grid-systems-square-rectangular-and-hex.md), drawn as
[ADR 0355](0355-the-cell-functions-and-drawing-a-grid.md) says. Desktop only.

## Decision

**Making and setting up a Map** offers all the kinds: a plane, an outline, a square grid, a
rectangular grid and a hex grid. The choice of hex orientation has no preselected answer and the form
cannot be sent without one. A grid asks for its cell (a size, or a width and a height), and may say
what a cell is in the world (an amount of a unit); the sheet's width and height stay in drawing
units, and the form says how many cells the grid will have. A plane or an outline may be given a grid
to draw over it (*Draw a grid over it*: its kind, cell, orientation and sub-grid). A sub-grid is a
division of each cell, for the eye. When settings are saved on a Map that has places and the answer is
the 409 of ADR 0354, the page says why and keeps the draft; a warning is shown under the save.

**Looking.** A Map with a grid has a **Grid** switch beside the others; a grid too fine to draw says
"Zoom in to see the grid". Moving the pointer over a grid Map says which cell it is over, in words
(*Column 4, row 6*, counted from 1 for people, from 0 in the API and the files), and a selected pin
says the cell it is in. The same words name a cell everywhere in the app.

**Snapping.** On a grid Map the editor has **Snap to the grid**, on by default: a pin and a circle's
centre go to the centre of the cell, and the points of a line or an area and every dragged handle go
to the nearest corner of the cell the pointer is in; a circle's radius is free. The numeric fields
are never snapped, so a place can still be put anywhere with them.

**The Cells tool.** Beside Pin, Circle, Line and Area there is **Cells**, for a Map with a grid:
after choosing what is being drawn (as for any tool) a click on a cell adds it, a click on a chosen
cell takes it away, **Enter** saves and **Escape** starts again. It writes one placement whose parts
are the cells' polygons, a part each, so a region of a hex map is a set of whole hexes; at most 256
cells, which is the part limit of ADR 0337, and the tool says so. A placement whose every part is
exactly a cell of the Map's grid (to two decimals) is read back as cells: the panel lists them, each
with a remove button and a pair of fields to add one by column and row, so a region can be made without
a pointer, and the Cells tool opens on it with its cells chosen. A placement that is not whole cells
is edited as before.

**What is not here.** A cell's own address is never stored; a distance, a path and a neighbour read
come with the distance slice; a sub-cell cannot be chosen or addressed; and a role, line and drawing
order are changed in the panel as for any placement.

## Validation and delivery

Unit tests for the pure parts: snapping to a centre and to a corner on each kind, the cell words, the
cells of a geometry and the geometry of cells (round trip, the 256 limit, a part that is not a cell).
Browser tests against the real API: a writer makes a square grid, a rectangular grid and a hex grid
(the orientation required), draws on each with snapping and the Cells tool and reads the cell under the
pointer, adds a cell by number, gives a plane a grid to draw over it and sees it, is refused when the
orientation of a hex Map with places is changed, and a player sees the grid and the same cell words
with no tools; axe in light and dark with a grid, the Cells tool and a panel open.

## Excluded

Painting by dragging across cells, a grid with a picture under it, editing a sub-grid, and travel or
measurement across cells.
