"""What a Map only draws, `map.view` (ADR 0354): a visual grid over any system that has none."""

from __future__ import annotations

from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.grid import GRID_KINDS, require_room, validate_grid


def validate_view(document: Any, system: dict[str, Any]) -> dict[str, Any] | None:
    """The view in its stored form, or a refusal; none and an empty view are none. `system` is the
    Map's validated system, whose extent a grid is laid over."""
    if document is None:
        return None
    if not isinstance(document, dict):
        raise MapDocumentError("a view must be an object")
    if set(document) - {"grid"}:
        raise MapDocumentError("a view has a key it does not know")
    if "grid" not in document:
        return None
    grid = document["grid"]
    if not isinstance(grid, dict) or grid.get("kind") not in GRID_KINDS:
        raise MapDocumentError("a view's grid is a square, rect or hex grid")
    if system.get("kind") in GRID_KINDS:
        raise MapDocumentError("a grid system draws its own grid")
    kind = str(grid["kind"])
    stored = {"kind": kind, **validate_grid(grid, kind=kind, measured=False)}
    require_room(stored, system["extent"])
    return {"grid": stored}
