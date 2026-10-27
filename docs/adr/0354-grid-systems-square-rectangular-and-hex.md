# 0354 - Grid systems: square, rectangular and hex

Status: accepted with the maintainer on 2026-10-27; RFC 0048 slice 7. Adds three kinds to the
system document of [ADR 0336](0336-maps-the-kind-its-system-and-its-placements.md) and a visual grid
that any system can carry. Placements and their geometry ([ADR 0337](0337-geometry-roles-and-the-validator.md))
are unchanged.

## Decision

**Three kinds** join `plane` and `outline` in `lorenzo.map-system/1` (the format string does not
change; an older reader reads a kind it does not know as an outline, as ADR 0336 says):

```json
{"format": "lorenzo.map-system/1", "kind": "square", "extent": [0, 0, 1000, 800],
 "cell": {"size": 50}, "measure": {"per_cell": 5, "unit": "ft"}, "sub": {"cols": 5, "rows": 5}}
{"format": "lorenzo.map-system/1", "kind": "rect", "extent": [0, 0, 1000, 800],
 "cell": {"width": 60, "height": 40}}
{"format": "lorenzo.map-system/1", "kind": "hex", "orientation": "pointy", "extent": [0, 0, 1000, 800],
 "cell": {"size": 58}, "sub": {"aperture": 7}}
```

- `cell` is what a cell is on the sheet, in drawing units, all positive: a `square` has a `size`, a
  `rect` a `width` and a `height`, a `hex` a `size` that is the distance between two opposite sides
  (so adjacent centres are `size` apart). A grid has at most 250,000 cells.
- `measure` is what a cell is in the world: `per_cell`, a positive number, of a `unit`, a name of at
  most 32 characters in the author's words. Without it nothing is measured and no unit is invented. A
  grid takes `measure` and never a `scale`; a plane takes `scale` and never a `measure`.
- `orientation` is `flat` (flat-topped hexes, in columns) or `pointy` (pointed-top hexes, in rows).
  A `hex` must say it, with no default; the other kinds take none.
- `sub` divides a cell for the eye: a `square` or `rect` by `cols` and `rows`, each a whole number
  from 1 to 16 and not both 1; a `hex` by an `aperture` of 3, 4 or 7. A sub-grid never feeds distance
  and has no addresses of its own.

**One hex convention.** With `w` the cell's `size` and `R = w / sqrt(3)` the distance from a centre to
a corner, a cell is a pair `(col, row)` of whole numbers counted from 0 with cell `(0, 0)` at the
sheet's near corner `(x0, y0)`:

- `pointy` (rows, "odd-r"): the centre is at `x0 + w/2 + col*w + (w/2 if row is odd)`, `y0 + R + row*1.5R`;
  the corners are at angles of -90, -30, 30, 90, 150 and 210 degrees from it.
- `flat` (columns, "odd-q"): the centre is at `x0 + R + col*1.5R`, `y0 + w/2 + row*w + (w/2 if col is odd)`;
  the corners are at 0, 60, 120, 180, 240 and 300 degrees.

Angles are measured with y downward, as the sheet is. A `square` or `rect` cell `(col, row)` is the
half-open rectangle starting at `(x0 + col*width, y0 + row*height)`. **A cell is in the grid when its
centre lies in the extent** (`x0 <= x < x1` and `y0 <= y < y1`); the count that limits a grid is the
count of such cells. Cell addresses are derived, never stored: a placement is geometry in drawing
units as before and may lie anywhere on the sheet.

**The tie rule.** A point belongs to the cell whose centre is nearest it; a point equally near two or
more (within 1e-9 of a drawing unit) belongs to the one with the lower row, then the lower column. A
point on a shared edge of two squares or rectangles belongs to the cell on its higher side (the
half-open rule above); this is the one place the two rules differ and both are fixed here.

**A visual grid for any system.** `map.view` (jsonb, null) holds what is only drawn:
`{"grid": {"kind": "square" | "rect" | "hex", "cell": {...}, "orientation": "...", "sub": {...}}}`, the same
fields as a system's but no `format`, `extent` or `measure`. It can be put over a `plane` or an
`outline`; a grid system draws its own, so a view grid on one is refused. It is validated by the same
code, never measured, never addressed, and read by nothing but the renderer. The column is added by a
migration and the release document is format 20, whose v19 reader gives every Map no view.

**Writing.** `POST /maps` and `PUT /maps/{id}` take `view` as they take `system`, and the header
returns it; `PUT` replaces the system, the subject, the theme name and the view together under
`If-Match`. A Map may be made with any of the kinds above and the kind API takes the same `system`.

**Changing a system that has placements.** Turning a Map into a hex Map or out of one, or changing a
hex Map's orientation, once any placement exists, is a **409**: it would silently move every place
drawn on the old cells. Every other change (the cell, the sub-grid, the measure, the extent, a
change between the other kinds) is allowed and the answer carries `warnings`, sentences that say what
may no longer line up. Warnings are not stored; no "needs review" state is kept, since nothing would
read it.

## Validation and delivery

`packages/map-engine`: every shape of the three kinds in the golden corpus (accepted and refused: a
missing orientation, a `scale` on a grid, a zero cell, a `sub` of 1 by 1, a view grid on a grid
system, too many cells); the view; the repository round trip and the v19 reader. API: create, replace
and read each kind and a view, the 409 and the warnings, the copy of a view, and that a plane with
placements may still become a square grid.

## Excluded

Distance on a grid (a later slice), addressing of sub-cells, a sphere (slice 8), cells that are not
whole in the extent, and any stored cell address.
