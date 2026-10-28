"""Where a picture lies on a Map's sheet: a layer's calibration and opacity (ADR 0361).

`None` is *fit the sheet*. Otherwise two or three anchors pair a point of the picture, as fractions
of its width and height from its top left, with a position on the sheet in drawing units: two give
a similarity (a turn, one scale and a move), three an affine map. The renderer owns the arithmetic;
this only says which documents make sense.
"""

from __future__ import annotations

from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.limits import MAX_COORDINATE
from lorenzo_map.numbers import SCALE, canonical, quantise

Anchor = tuple[tuple[int, int], tuple[int, int]]


def _pair(value: Any, *, bound: float, what: str) -> tuple[int, int]:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise MapDocumentError(f"{what} must be two numbers")
    return (
        quantise(value[0], bound=bound, what=what),
        quantise(value[1], bound=bound, what=what),
    )


def _cross(a: tuple[int, int], b: tuple[int, int], c: tuple[int, int]) -> int:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _spread(points: list[tuple[int, int]], what: str) -> None:
    """The points are all different, and three are not on one line."""
    if len(set(points)) != len(points):
        raise MapDocumentError(f"the anchors' {what} must all be different")
    if len(points) == 3 and _cross(*points) == 0:
        raise MapDocumentError(f"the anchors' {what} must not lie on one line")


def validate_calibration(document: Any) -> dict[str, Any] | None:
    """A calibration in its stored form, or a refusal; none is *fit the sheet*."""
    if document is None:
        return None
    if not isinstance(document, dict) or set(document) != {"anchors"}:
        raise MapDocumentError("a calibration is its anchors")
    anchors = document["anchors"]
    if not isinstance(anchors, list | tuple) or len(anchors) not in (2, 3):
        raise MapDocumentError("a calibration has two or three anchors")
    stored: list[dict[str, Any]] = []
    images: list[tuple[int, int]] = []
    sheet: list[tuple[int, int]] = []
    for anchor in anchors:
        if not isinstance(anchor, dict) or set(anchor) != {"image", "at"}:
            raise MapDocumentError("an anchor is a point of the picture and a point of the sheet")
        image = _pair(anchor["image"], bound=1, what="a point of the picture")
        if any(n < 0 for n in image):
            raise MapDocumentError("a point of the picture is a fraction from 0 to 1")
        at = _pair(anchor["at"], bound=MAX_COORDINATE, what="a position on the sheet")
        images.append(image)
        sheet.append(at)
        stored.append(
            {
                "image": [canonical(image[0]), canonical(image[1])],
                "at": [canonical(at[0]), canonical(at[1])],
            }
        )
    _spread(images, "points in the picture")
    _spread(sheet, "positions on the sheet")
    return {"anchors": stored}


def validate_opacity(value: Any) -> float | None:
    """A layer's opacity from 0 to 1, or none for opaque."""
    if value is None:
        return None
    opacity = quantise(value, bound=1, what="an opacity")
    if opacity < 0:
        raise MapDocumentError("an opacity is from 0 to 1")
    number = opacity / SCALE
    return float(number)
