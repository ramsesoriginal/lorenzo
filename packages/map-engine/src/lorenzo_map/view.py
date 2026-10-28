"""What a Map only draws, `map.view`: a visual grid over a system that has none (ADR 0354) or a
sphere's projection (ADR 0357)."""

from __future__ import annotations

from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.grid import GRID_KINDS, require_room, validate_grid
from lorenzo_map.sphere import is_sphere, validate_projection


def validate_view(document: Any, system: dict[str, Any]) -> dict[str, Any] | None:
    """The view in its stored form, or a refusal; none and an empty view are none. `system` is the
    Map's validated system, whose extent a grid is laid over."""
    if document is None:
        return None
    if not isinstance(document, dict):
        raise MapDocumentError("a view must be an object")
    if set(document) - {"grid", "projection"}:
        raise MapDocumentError("a view has a key it does not know")
    stored_view: dict[str, Any] = {}
    if "grid" in document:
        grid = document["grid"]
        if not isinstance(grid, dict) or grid.get("kind") not in GRID_KINDS:
            raise MapDocumentError("a view's grid is a square, rect or hex grid")
        if system.get("kind") in GRID_KINDS:
            raise MapDocumentError("a grid system draws its own grid")
        if is_sphere(system):
            raise MapDocumentError("a sphere draws its own lines of longitude and latitude")
        kind = str(grid["kind"])
        stored = {"kind": kind, **validate_grid(grid, kind=kind, measured=False)}
        require_room(stored, system["extent"])
        stored_view["grid"] = stored
    if "projection" in document:
        if not is_sphere(system):
            raise MapDocumentError("only a sphere has a projection")
        stored_view["projection"] = validate_projection(document["projection"])
    return stored_view or None
