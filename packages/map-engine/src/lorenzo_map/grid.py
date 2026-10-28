"""Grids: the cell of a square, rectangular or hex map, and where a point falls (ADR 0354, 0355).

One convention, written once. A hex cell has the `size` (`w`) of the distance between two opposite
sides and a circumradius `R = w / sqrt(3)`; a cell is `(col, row)` counted from 0 with cell (0, 0)
at the sheet's near corner `(x0, y0)`; `pointy` is "odd-r" (rows), `flat` is "odd-q" (columns). A
cell is in the grid when its column and row are not negative and its centre is before the far
edges of the extent. A point belongs to the nearest centre, ties
going to the lower row and then the lower column; on a square or rectangular grid a shared edge
belongs to the cell on its higher side. The TypeScript mirror in `packages/map-renderer` reads the
same golden file.
"""

from __future__ import annotations

import math
from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.limits import MAX_CELLS, MAX_COORDINATE, MAX_SUB_DIVISIONS
from lorenzo_map.numbers import canonical, clean_text, quantise

GRID_KINDS = ("square", "rect", "hex")
ORIENTATIONS = ("flat", "pointy")
APERTURES = (3, 4, 7)

Cell = tuple[int, int]
Point = tuple[float, float]

#: Two distances this close are a tie (ADR 0354).
TIE = 1e-9
_SQRT3 = math.sqrt(3)


def _positive(value: Any, what: str) -> float:
    q = quantise(value, bound=MAX_COORDINATE, what=what)
    if q <= 0:
        raise MapDocumentError(f"{what} must be more than zero")
    return float(canonical(q))


def _whole(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= MAX_SUB_DIVISIONS:
        raise MapDocumentError(f"{what} is a whole number from 1 to {MAX_SUB_DIVISIONS}")
    return value


def validate_grid(document: dict[str, Any], *, kind: str, measured: bool) -> dict[str, Any]:
    """The grid fields of a system or a view in their stored form: `cell`, `orientation` (hex only),
    `sub`, and `measure` when `measured`. `kind` is already known to be a grid kind."""
    allowed = {"cell", "sub"} | ({"measure"} if measured else set())
    if kind == "hex":
        allowed.add("orientation")
    stray = set(document) - allowed - {"format", "kind", "extent"}
    if stray:
        raise MapDocumentError("a grid has a key it does not know")
    out: dict[str, Any] = {}
    if kind == "hex":
        if document.get("orientation") not in ORIENTATIONS:
            raise MapDocumentError("a hex grid must say whether its hexes are flat or pointy")
        out["orientation"] = document["orientation"]
    cell = document.get("cell")
    if not isinstance(cell, dict):
        raise MapDocumentError("a grid needs a cell")
    want = {"rect": {"width", "height"}}.get(kind, {"size"})
    if set(cell) != want:
        raise MapDocumentError(
            "a rectangular grid's cell is a width and a height; the others' a size"
        )
    out["cell"] = {
        key: canonical(quantise(cell[key], bound=MAX_COORDINATE, what="a cell"))
        for key in sorted(want)
    }
    for key in want:
        _positive(cell[key], "a cell")
    sub = document.get("sub")
    if sub is not None:
        out["sub"] = _validate_sub(sub, kind)
    if measured and "measure" in document:
        measure = document["measure"]
        if not isinstance(measure, dict) or set(measure) != {"per_cell", "unit"}:
            raise MapDocumentError("a measure is a per_cell number and a unit")
        per_cell = quantise(measure["per_cell"], bound=1e12, what="a measure")
        if per_cell <= 0:
            raise MapDocumentError("a measure must be positive")
        out["measure"] = {
            "per_cell": canonical(per_cell),
            "unit": clean_text(measure["unit"], what="a unit"),
        }
    return out


def _validate_sub(sub: Any, kind: str) -> dict[str, Any]:
    if kind == "hex":
        if (
            not isinstance(sub, dict)
            or set(sub) != {"aperture"}
            or sub["aperture"] not in APERTURES
        ):
            raise MapDocumentError("a hex sub-grid has an aperture of 3, 4 or 7")
        return {"aperture": sub["aperture"]}
    if not isinstance(sub, dict) or set(sub) != {"cols", "rows"}:
        raise MapDocumentError("a sub-grid is a number of cols and rows")
    cols, rows = _whole(sub["cols"], "cols"), _whole(sub["rows"], "rows")
    if cols == 1 and rows == 1:
        raise MapDocumentError("a sub-grid of 1 by 1 divides nothing")
    return {"cols": cols, "rows": rows}


# --- the cell functions ---------------------------------------------------------------------


def _sizes(grid: dict[str, Any]) -> tuple[float, float]:
    cell = grid["cell"]
    if grid["kind"] == "rect":
        return float(cell["width"]), float(cell["height"])
    return float(cell["size"]), float(cell["size"])


def _axial_to_offset(grid: dict[str, Any], q: int, r: int) -> Cell:
    if grid["orientation"] == "pointy":
        return q + (r - (r & 1)) // 2, r
    return q, r + (q - (q & 1)) // 2


def _offset_to_axial(grid: dict[str, Any], col: int, row: int) -> Cell:
    if grid["orientation"] == "pointy":
        return col - (row - (row & 1)) // 2, row
    return col, row - (col - (col & 1)) // 2


def hex_steps(grid: dict[str, Any], a: Cell, b: Cell) -> int:
    """The steps between two hex cells: the cube distance of their axial addresses, so a
    neighbour is 1 and the same cell 0."""
    qa, ra = _offset_to_axial(grid, *a)
    qb, rb = _offset_to_axial(grid, *b)
    dq, dr = qa - qb, ra - rb
    return max(abs(dq), abs(dr), abs(dq + dr))


def cell_centre(grid: dict[str, Any], extent: list[float], cell: Cell) -> Point:
    """The centre of a cell. `grid` has its `kind` (a system's own, or a view grid's)."""
    x0, y0 = float(extent[0]), float(extent[1])
    col, row = cell
    if grid["kind"] != "hex":
        w, h = _sizes(grid)
        return x0 + (col + 0.5) * w, y0 + (row + 0.5) * h
    w = float(grid["cell"]["size"])
    radius = w / _SQRT3
    if grid["orientation"] == "pointy":
        return (
            x0 + w / 2 + col * w + (w / 2 if row & 1 else 0.0),
            y0 + radius + row * 1.5 * radius,
        )
    return (
        x0 + radius + col * 1.5 * radius,
        y0 + w / 2 + row * w + (w / 2 if col & 1 else 0.0),
    )


def cell_polygon(grid: dict[str, Any], extent: list[float], cell: Cell) -> list[Point]:
    """The corners of a cell: a square or rectangle clockwise from its near corner, a hex from the
    corner at its lowest angle (-90 degrees for pointy, 0 for flat), clockwise on the sheet."""
    cx, cy = cell_centre(grid, extent, cell)
    if grid["kind"] != "hex":
        w, h = _sizes(grid)
        x, y = cx - w / 2, cy - h / 2
        return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
    radius = float(grid["cell"]["size"]) / _SQRT3
    start = -90 if grid["orientation"] == "pointy" else 0
    return [
        (
            cx + radius * math.cos(math.radians(start + 60 * k)),
            cy + radius * math.sin(math.radians(start + 60 * k)),
        )
        for k in range(6)
    ]


def cell_at(grid: dict[str, Any], extent: list[float], point: Point) -> Cell:
    """The cell a point belongs to, wherever the point is (a cell off the sheet has a negative or
    large address; `in_grid` says whether it is in the grid)."""
    x0, y0 = float(extent[0]), float(extent[1])
    px, py = point
    if grid["kind"] != "hex":
        w, h = _sizes(grid)
        return math.floor((px - x0) / w), math.floor((py - y0) / h)
    w = float(grid["cell"]["size"])
    radius = w / _SQRT3
    cx0, cy0 = cell_centre(grid, extent, (0, 0))
    dx, dy = px - cx0, py - cy0
    if grid["orientation"] == "pointy":
        fq = (_SQRT3 / 3 * dx - dy / 3) / radius
        fr = (2 / 3 * dy) / radius
    else:
        fq = (2 / 3 * dx) / radius
        fr = (-dx / 3 + _SQRT3 / 3 * dy) / radius
    q, r = _cube_round(fq, fr)
    best: tuple[float, int, int] | None = None
    for dq, dr in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)):
        col, row = _axial_to_offset(grid, q + dq, r + dr)
        ox, oy = cell_centre(grid, extent, (col, row))
        distance = math.hypot(px - ox, py - oy)
        if (
            best is None
            or distance < best[0] - TIE
            or (abs(distance - best[0]) <= TIE and (row, col) < (best[2], best[1]))
        ):
            best = (distance, col, row)
    assert best is not None
    return best[1], best[2]


def _cube_round(fq: float, fr: float) -> Cell:
    fs = -fq - fr
    rq, rr, rs = round(fq), round(fr), round(fs)
    dq, dr, ds = abs(rq - fq), abs(rr - fr), abs(rs - fs)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return int(rq), int(rr)


def in_grid(grid: dict[str, Any], extent: list[float], cell: Cell) -> bool:
    """Whether the cell is in the grid: its column and row are not negative and its centre lies
    before the extent's far edges."""
    if cell[0] < 0 or cell[1] < 0:
        return False
    cx, cy = cell_centre(grid, extent, cell)
    return cx < extent[2] and cy < extent[3]


def _span(length: float, first: float, step: float) -> int:
    """How many `first + n*step` (n from 0) are below `length`."""
    if length <= first:
        return 0
    return math.ceil((length - first) / step - 1e-12)


def cell_count(grid: dict[str, Any], extent: list[float]) -> int:
    """How many cells are in the grid (see `in_grid`)."""
    width, height = float(extent[2]) - float(extent[0]), float(extent[3]) - float(extent[1])
    if grid["kind"] != "hex":
        w, h = _sizes(grid)
        return _span(width, w / 2, w) * _span(height, h / 2, h)
    w = float(grid["cell"]["size"])
    radius = w / _SQRT3
    if grid["orientation"] == "pointy":
        rows = _span(height, radius, 1.5 * radius)
        even = _span(width, w / 2, w)
        odd = _span(width, w, w)
        return ((rows + 1) // 2) * even + (rows // 2) * odd
    cols = _span(width, radius, 1.5 * radius)
    even = _span(height, w / 2, w)
    odd = _span(height, w, w)
    return ((cols + 1) // 2) * even + (cols // 2) * odd


def require_room(grid: dict[str, Any], extent: list[float]) -> None:
    if cell_count(grid, extent) > MAX_CELLS:
        raise MapDocumentError(f"a grid has at most {MAX_CELLS} cells")
