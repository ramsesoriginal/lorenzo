"""A sphere Map: positions are longitude and latitude in degrees (ADR 0357).

The sheet is the rectangle `[-180, -90, 180, 90]`; there is no wrap, so what crosses the
antimeridian is two parts. A projection only changes how the sheet is drawn and is kept in
`map.view`.
"""

from __future__ import annotations

from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.numbers import SCALE, canonical, quantise

SPHERE_KIND = "sphere"
#: What a sphere's extent must be: longitude then latitude, west and south first.
SPHERE_EXTENT = [-180, -90, 180, 90]
MAX_LONGITUDE = 180
MAX_LATITUDE = 90
PROJECTIONS = ("equirectangular", "mercator", "orthographic")


def is_sphere(system: Any) -> bool:
    return isinstance(system, dict) and system.get("kind") == SPHERE_KIND


def in_range(point: tuple[int, int]) -> bool:
    """Whether a quantised `(longitude, latitude)` is on the sheet."""
    return abs(point[0]) <= MAX_LONGITUDE * SCALE and abs(point[1]) <= MAX_LATITUDE * SCALE


def validate_projection(document: Any) -> dict[str, Any]:
    """A view's projection in its stored form, or a refusal."""
    if not isinstance(document, dict):
        raise MapDocumentError("a projection must be an object")
    kind = document.get("kind")
    if kind not in PROJECTIONS:
        raise MapDocumentError("a projection is equirectangular, mercator or orthographic")
    if set(document) - {"kind", "centre"}:
        raise MapDocumentError("a projection has a key it does not know")
    stored: dict[str, Any] = {"kind": kind}
    if "centre" in document:
        if kind != "orthographic":
            raise MapDocumentError("only a globe has a centre")
        centre = document["centre"]
        if not isinstance(centre, list | tuple) or len(centre) != 2:
            raise MapDocumentError("a centre is a longitude and a latitude")
        lon = quantise(centre[0], bound=MAX_LONGITUDE, what="a longitude")
        lat = quantise(centre[1], bound=MAX_LATITUDE, what="a latitude")
        stored["centre"] = [canonical(lon), canonical(lat)]
    return stored
