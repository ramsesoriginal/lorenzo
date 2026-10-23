"""The one validator of Lorenzo map systems and geometry (ADR 0336, ADR 0337). Pure, no database."""

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.geometry import GEOMETRY_FORMAT, Validated, validate_geometry
from lorenzo_map.limits import (
    MAX_COORDINATE,
    MAX_MAPS_PER_LIBRARY,
    MAX_PARTS,
    MAX_PLACEMENT_BYTES,
    MAX_PLACEMENTS_PER_MAP,
    MAX_VERTICES,
)
from lorenzo_map.placement import ValidatedPlacement, validate_placement, validate_z
from lorenzo_map.roles import (
    ROLES,
    STROKES,
    WEIGHTS,
    read_role,
    validate_role,
    validate_style,
)
from lorenzo_map.system import SYSTEM_FORMAT, WRITABLE_KINDS, effective_kind, validate_system

__all__ = [
    "GEOMETRY_FORMAT",
    "MAX_COORDINATE",
    "MAX_MAPS_PER_LIBRARY",
    "MAX_PARTS",
    "MAX_PLACEMENTS_PER_MAP",
    "MAX_PLACEMENT_BYTES",
    "MAX_VERTICES",
    "ROLES",
    "STROKES",
    "SYSTEM_FORMAT",
    "WEIGHTS",
    "WRITABLE_KINDS",
    "MapDocumentError",
    "Validated",
    "ValidatedPlacement",
    "effective_kind",
    "read_role",
    "validate_geometry",
    "validate_placement",
    "validate_role",
    "validate_style",
    "validate_system",
    "validate_z",
]
