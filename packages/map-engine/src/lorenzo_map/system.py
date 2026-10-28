"""A Map's coordinate system, `lorenzo.map-system/1` (ADR 0336)."""

from __future__ import annotations

from typing import Any

from lorenzo_map.distance import METRIC_KINDS, validate_metric
from lorenzo_map.errors import MapDocumentError
from lorenzo_map.grid import GRID_KINDS, require_room, validate_grid
from lorenzo_map.limits import MAX_COORDINATE
from lorenzo_map.numbers import canonical, clean_text, quantise
from lorenzo_map.sphere import SPHERE_EXTENT, SPHERE_KIND

SYSTEM_FORMAT = "lorenzo.map-system/1"
# The systems this version can write: all six of RFC 0048.
WRITABLE_KINDS = ("plane", "outline", "square", "rect", "hex", SPHERE_KIND)


def validate_system(document: Any) -> dict[str, Any]:
    """The system in its stored form, or a refusal. The kind must be one this version writes."""
    if not isinstance(document, dict):
        raise MapDocumentError("a system must be an object")
    if document.get("format") != SYSTEM_FORMAT:
        raise MapDocumentError("a system must name its format")
    kind = document.get("kind")
    if kind not in WRITABLE_KINDS:
        raise MapDocumentError("this kind of system cannot be written yet")
    if kind in GRID_KINDS:
        allowed = {"format", "kind", "extent", "cell", "measure", "sub", "orientation"}
        if kind in METRIC_KINDS:
            allowed.add("metric")
    elif kind == SPHERE_KIND:
        allowed = {"format", "kind", "extent", "radius"}
    else:
        allowed = {"format", "kind", "extent"} | ({"scale"} if kind == "plane" else set())
    if set(document) - allowed:
        raise MapDocumentError("a system has a key it does not know")
    extent = document.get("extent")
    if not isinstance(extent, list | tuple) or len(extent) != 4:
        raise MapDocumentError("a system's extent must be four numbers")
    x0, y0, x1, y1 = (
        quantise(v, bound=MAX_COORDINATE, what="an extent coordinate") for v in extent
    )
    if x1 <= x0 or y1 <= y0:
        raise MapDocumentError("an extent must have its far corner beyond its near one")
    if kind == SPHERE_KIND and [canonical(v) for v in (x0, y0, x1, y1)] != SPHERE_EXTENT:
        raise MapDocumentError("a sphere's extent is longitude -180 to 180 and latitude -90 to 90")
    result: dict[str, Any] = {
        "format": SYSTEM_FORMAT,
        "kind": kind,
        "extent": [canonical(x0), canonical(y0), canonical(x1), canonical(y1)],
    }
    if kind in GRID_KINDS:
        grid = validate_grid(
            {key: value for key, value in document.items() if key != "metric"},
            kind=str(kind),
            measured=True,
        )
        result.update(grid)
        if "metric" in document:
            result["metric"] = validate_metric(document["metric"])
        require_room(
            {"kind": kind, **grid}, [canonical(x0), canonical(y0), canonical(x1), canonical(y1)]
        )
    if "scale" in document:
        scale = document["scale"]
        if not isinstance(scale, dict) or set(scale) != {"per_unit", "unit"}:
            raise MapDocumentError("a scale is a per_unit number and a unit")
        per_unit = quantise(scale["per_unit"], bound=1e12, what="a scale")
        if per_unit <= 0:
            raise MapDocumentError("a scale must be positive")
        result["scale"] = {
            "per_unit": canonical(per_unit),
            "unit": clean_text(scale["unit"], what="a unit"),
        }
    if "radius" in document:
        radius = document["radius"]
        if not isinstance(radius, dict) or set(radius) != {"value", "unit"}:
            raise MapDocumentError("a radius is a value and a unit")
        value = quantise(radius["value"], bound=1e12, what="a radius")
        if value <= 0:
            raise MapDocumentError("a radius must be positive")
        result["radius"] = {
            "value": canonical(value),
            "unit": clean_text(radius["unit"], what="a unit"),
        }
    return result


def effective_kind(document: Any) -> str:
    """How a reader treats a stored system: a kind this version does not know measures nothing and
    is drawn as an outline."""
    if isinstance(document, dict) and document.get("kind") in WRITABLE_KINDS:
        return str(document["kind"])
    return "outline"
