"""A whole placement: geometry, role, style and drawing order (ADR 0337, ADR 0338)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.geometry import validate_geometry
from lorenzo_map.limits import MAX_Z, MIN_Z
from lorenzo_map.roles import validate_role, validate_style


@dataclass(frozen=True)
class ValidatedPlacement:
    geometry: dict[str, Any]
    role: str | None
    style: dict[str, str] | None
    z: int
    bytes: int
    bbox: tuple[float, float, float, float]


def validate_z(z: Any) -> int:
    if isinstance(z, bool) or not isinstance(z, int) or not MIN_Z <= z <= MAX_Z:
        raise MapDocumentError(f"the drawing order is a whole number from {MIN_Z} to {MAX_Z}")
    return z


def validate_placement(
    geometry: Any, role: Any = None, style: Any = None, z: Any = 0
) -> ValidatedPlacement:
    checked = validate_geometry(geometry)
    return ValidatedPlacement(
        geometry=checked.geometry,
        role=validate_role(role),
        style=validate_style(style),
        z=validate_z(z),
        bytes=checked.bytes,
        bbox=checked.bbox,
    )
