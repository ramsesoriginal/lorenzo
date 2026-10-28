"""The straight-line distance between two positions on a Map, in the author's own unit (ADR 0366).

A pure function of a validated system and two positions. It never converts a unit, never reads a
connection and never says where an entry is; the answer is a number and the unit the Map's author
chose, or the reason there is none.
"""

from __future__ import annotations

import math
from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.grid import GRID_KINDS, Point, cell_at, hex_steps
from lorenzo_map.sphere import SPHERE_KIND

#: How a square or rectangular grid counts a diagonal step (ADR 0366). Counted when absent.
METRICS = ("chebyshev", "manhattan", "euclidean", "alternating")
DEFAULT_METRIC = "euclidean"
#: Kinds whose cells a metric counts; a hex has one way to count.
METRIC_KINDS = ("square", "rect")

NO_SCALE = "the Map has no scale"
NO_MEASURE = "its cells have no size in the world"
NO_RADIUS = "the world has no radius"
NO_MEASURING = "an outline measures nothing"

Distance = dict[str, Any]


def validate_metric(document: Any) -> str:
    """A system's metric in its stored form, or a refusal."""
    if document not in METRICS:
        raise MapDocumentError("a metric is chebyshev, manhattan, euclidean or alternating")
    return str(document)


def _known(value: float, unit: str) -> Distance:
    # Six decimals, as the format allows, so that a distance reads the same everywhere.
    rounded = round(value, 6)
    return {
        "state": "known",
        "value": int(rounded) if rounded.is_integer() else rounded,
        "unit": unit,
    }


def _unknown(reason: str) -> Distance:
    return {"state": "unknown", "reason": reason}


def cells_apart(metric: str, columns: int, rows: int) -> float:
    """The distance in cells of two cells `columns` and `rows` apart."""
    dc, dr = abs(columns), abs(rows)
    if metric == "chebyshev":
        return float(max(dc, dr))
    if metric == "manhattan":
        return float(dc + dr)
    if metric == "alternating":
        return float(max(dc, dr) + min(dc, dr) // 2)
    return math.hypot(dc, dr)


def great_circle(a: Point, b: Point, radius: float) -> float:
    """The haversine distance of two `(longitude, latitude)` points on a sphere of `radius`."""
    lon1, lat1, lon2, lat2 = (math.radians(v) for v in (a[0], a[1], b[0], b[1]))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def straight_distance(system: dict[str, Any], a: Point, b: Point) -> Distance:
    """How far `a` is from `b` on a Map with this validated system: `{"state": "known", "value",
    "unit"}`, or `{"state": "unknown", "reason"}`. Positions are in the system's stored units."""
    kind = system.get("kind")
    if kind == "plane":
        scale = system.get("scale")
        if not scale:
            return _unknown(NO_SCALE)
        return _known(math.hypot(a[0] - b[0], a[1] - b[1]) * scale["per_unit"], scale["unit"])
    if kind in GRID_KINDS:
        measure = system.get("measure")
        if not measure:
            return _unknown(NO_MEASURE)
        extent = system["extent"]
        ca, cb = cell_at(system, extent, a), cell_at(system, extent, b)
        if kind == "hex":
            cells = float(hex_steps(system, ca, cb))
        else:
            cells = cells_apart(
                system.get("metric", DEFAULT_METRIC) if kind in METRIC_KINDS else DEFAULT_METRIC,
                ca[0] - cb[0],
                ca[1] - cb[1],
            )
        return _known(cells * measure["per_cell"], measure["unit"])
    if kind == SPHERE_KIND:
        radius = system.get("radius")
        if not radius:
            return _unknown(NO_RADIUS)
        return _known(great_circle(a, b, radius["value"]), radius["unit"])
    return _unknown(NO_MEASURING)
