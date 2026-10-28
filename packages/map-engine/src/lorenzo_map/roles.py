"""The closed list of roles, and a placement's style (ADR 0337).

A role says what kind of stuff a placement is, so a theme can draw it and a view can group it. It
never validates a shape, gates visibility, or feeds a distance or reach.
"""

from __future__ import annotations

from typing import Any

from lorenzo_map.errors import MapDocumentError

ROLES = (
    "water",
    "ground",
    "relief",
    "vegetation",
    "diffuse",
    "celestial",
    "built-up",
    "structure",
    "interior",
    "barrier",
    "passage",
    "route",
    "conduit",
    "territory",
    "boundary",
    "hazard",
    "presence",
    "object",
    "isoline",
    "marker",
    "site",
)
STROKES = ("solid", "dashed", "dotted", "double", "none")
WEIGHTS = ("hairline", "thin", "regular", "thick", "heavy")


def validate_role(role: Any) -> str | None:
    """A role this version knows, or None; anything else is refused on a write."""
    if role is None:
        return None
    if not isinstance(role, str) or role not in ROLES:
        raise MapDocumentError("that role is not one this version knows")
    return role


def read_role(role: Any) -> str | None:
    """How a reader treats a stored role: one it does not know is no role."""
    return role if isinstance(role, str) and role in ROLES else None


def validate_style(style: Any) -> dict[str, str] | None:
    """The style in its stored form (an empty style is none), or a refusal."""
    if style is None:
        return None
    if not isinstance(style, dict) or set(style) - {"stroke", "weight"}:
        raise MapDocumentError("a style is a stroke and a weight and nothing else")
    result: dict[str, str] = {}
    if "stroke" in style:
        if style["stroke"] not in STROKES:
            raise MapDocumentError("that stroke is not one this version knows")
        result["stroke"] = style["stroke"]
    if "weight" in style:
        if style["weight"] not in WEIGHTS:
            raise MapDocumentError("that weight is not one this version knows")
        result["weight"] = style["weight"]
    return result or None
