"""A placement's geometry, `lorenzo.geometry/1` (ADR 0337).

`validate_geometry` is the one way geometry enters: from every API write, the repository planner and
the update applier. It returns the geometry in its stored form with its size and bounding box, or
refuses with a sentence that repeats nothing of the input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.limits import (
    MAX_COORDINATE,
    MAX_PARTS,
    MAX_PLACEMENT_BYTES,
    MAX_VALUE,
    MAX_VERTICES,
)
from lorenzo_map.numbers import SCALE, canonical, clean_text, quantise
from lorenzo_map.simple import check_polygon
from lorenzo_map.sphere import in_range

GEOMETRY_FORMAT = "lorenzo.geometry/1"
_COMMON = {"shape", "value", "unit"}
_KEYS = {
    "point": _COMMON | {"at"},
    "circle": _COMMON | {"at", "r"},
    "polyline": _COMMON | {"pts"},
    "bezier": _COMMON | {"start", "segs", "closed"},
    "polygon": _COMMON | {"rings"},
}


@dataclass(frozen=True)
class Validated:
    geometry: dict[str, Any]
    bytes: int
    vertices: int
    # A superset of the shape: the hull of a bezier's control points, the square around a circle.
    bbox: tuple[float, float, float, float]


def _point(value: Any) -> tuple[int, int]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise MapDocumentError("a point must be two numbers")
    return (
        quantise(value[0], bound=MAX_COORDINATE, what="a coordinate"),
        quantise(value[1], bound=MAX_COORDINATE, what="a coordinate"),
    )


def _out(point: tuple[int, int]) -> list[int | float]:
    return [canonical(point[0]), canonical(point[1])]


def _points(value: Any, *, minimum: int) -> list[tuple[int, int]]:
    if not isinstance(value, list | tuple) or len(value) < minimum:
        raise MapDocumentError(f"a line or ring needs at least {minimum} points")
    return [_point(p) for p in value]


def _part(raw: Any) -> tuple[dict[str, Any], int, list[tuple[int, int]]]:
    """(stored part, vertices, every point that bounds it)."""
    if not isinstance(raw, dict):
        raise MapDocumentError("a part must be an object")
    shape = raw.get("shape")
    if shape not in _KEYS:
        raise MapDocumentError("a part must be a point, circle, polyline, bezier or polygon")
    if set(raw) - _KEYS[shape]:
        raise MapDocumentError("a part has a key it does not know")
    stored: dict[str, Any] = {"shape": shape}
    bounds: list[tuple[int, int]]
    vertices: int
    if shape == "point":
        at = _point(raw.get("at"))
        stored["at"] = _out(at)
        bounds, vertices = [at], 1
    elif shape == "circle":
        at = _point(raw.get("at"))
        radius = quantise(raw.get("r"), bound=MAX_COORDINATE, what="a radius")
        if radius <= 0:
            raise MapDocumentError("a radius must be positive")
        stored["at"] = _out(at)
        stored["r"] = canonical(radius)
        bounds = [(at[0] - radius, at[1] - radius), (at[0] + radius, at[1] + radius)]
        vertices = 1
    elif shape == "polyline":
        pts = _points(raw.get("pts"), minimum=2)
        stored["pts"] = [_out(p) for p in pts]
        bounds, vertices = pts, len(pts)
    elif shape == "bezier":
        start = _point(raw.get("start"))
        segs = raw.get("segs")
        if not isinstance(segs, list | tuple) or not segs:
            raise MapDocumentError("a bezier needs at least one segment")
        bounds = [start]
        stored_segs = []
        for seg in segs:
            if not isinstance(seg, list | tuple) or len(seg) != 3:
                raise MapDocumentError("a bezier segment is two controls and an end")
            points = [_point(p) for p in seg]
            bounds.extend(points)
            stored_segs.append([_out(p) for p in points])
        closed = raw.get("closed", False)
        if not isinstance(closed, bool):
            raise MapDocumentError("closed must be true or false")
        stored["start"] = _out(start)
        stored["segs"] = stored_segs
        if "closed" in raw:
            stored["closed"] = closed
        vertices = 1 + 3 * len(stored_segs)
    else:
        rings_raw = raw.get("rings")
        if not isinstance(rings_raw, list | tuple) or not rings_raw:
            raise MapDocumentError("a polygon needs an outer ring")
        rings = [_points(ring, minimum=3) for ring in rings_raw]
        check_polygon(rings)
        stored["rings"] = [[_out(p) for p in ring] for ring in rings]
        bounds = [p for ring in rings for p in ring]
        vertices = len(bounds)
    if ("value" in raw) != ("unit" in raw):
        raise MapDocumentError("a value and its unit go together")
    if "value" in raw:
        value = quantise(raw["value"], bound=MAX_VALUE, what="a value")
        stored["value"] = canonical(value)
        stored["unit"] = clean_text(raw["unit"], what="a unit")
    return stored, vertices, bounds


def validate_geometry(document: Any, *, sphere: bool = False) -> Validated:
    """The geometry in its stored form, its size and its bounding box, or a refusal. On a `sphere`
    Map (ADR 0357) a part is a point, a polyline or a polygon and every coordinate is a longitude
    and a latitude in range."""
    if not isinstance(document, dict) or set(document) != {"format", "parts"}:
        raise MapDocumentError("a geometry is a format and its parts")
    if document["format"] != GEOMETRY_FORMAT:
        raise MapDocumentError("a geometry must name its format")
    parts_raw = document["parts"]
    if not isinstance(parts_raw, list | tuple) or not parts_raw or len(parts_raw) > MAX_PARTS:
        raise MapDocumentError(f"a geometry has between 1 and {MAX_PARTS} parts")
    parts: list[dict[str, Any]] = []
    vertices = 0
    low_x = low_y = high_x = high_y = None
    for raw in parts_raw:
        stored, count, bounds = _part(raw)
        if sphere:
            if stored["shape"] in ("circle", "bezier"):
                raise MapDocumentError("a sphere draws points, lines and areas")
            if not all(in_range(p) for p in bounds):
                raise MapDocumentError(
                    "a longitude is from -180 to 180 and a latitude from -90 to 90"
                )
        parts.append(stored)
        vertices += count
        if vertices > MAX_VERTICES:
            raise MapDocumentError(f"a placement has at most {MAX_VERTICES} vertices")
        xs = [p[0] for p in bounds]
        ys = [p[1] for p in bounds]
        low_x = min(xs) if low_x is None else min(low_x, *xs)
        low_y = min(ys) if low_y is None else min(low_y, *ys)
        high_x = max(xs) if high_x is None else max(high_x, *xs)
        high_y = max(ys) if high_y is None else max(high_y, *ys)
    assert low_x is not None and low_y is not None and high_x is not None and high_y is not None
    stored_geometry = {"format": GEOMETRY_FORMAT, "parts": parts}
    size = len(json.dumps(stored_geometry, separators=(",", ":"), ensure_ascii=False).encode())
    if size > MAX_PLACEMENT_BYTES:
        raise MapDocumentError("a placement's geometry is too large")
    return Validated(
        stored_geometry,
        size,
        vertices,
        (low_x / SCALE, low_y / SCALE, high_x / SCALE, high_y / SCALE),
    )
