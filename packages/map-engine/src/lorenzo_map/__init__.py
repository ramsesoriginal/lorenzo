"""The one validator of Lorenzo map systems and geometry (ADR 0336, ADR 0337). Pure, no database."""

from lorenzo_map.errors import MapDocumentError
from lorenzo_map.geometry import GEOMETRY_FORMAT, Validated, validate_geometry
from lorenzo_map.grid import (
    APERTURES,
    GRID_KINDS,
    ORIENTATIONS,
    cell_at,
    cell_centre,
    cell_count,
    cell_polygon,
    in_grid,
)
from lorenzo_map.limits import (
    MAX_BATCH_OPERATIONS,
    MAX_COORDINATE,
    MAX_MAPS_PER_LIBRARY,
    MAX_PARTS,
    MAX_PLACEMENT_BYTES,
    MAX_PLACEMENTS_PER_MAP,
    MAX_THEME_NAME,
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
from lorenzo_map.themes import THEME_NAMES, keep_theme_hint, read_theme_hint, validate_theme_hint
from lorenzo_map.view import validate_view

__all__ = [
    "APERTURES",
    "GRID_KINDS",
    "ORIENTATIONS",
    "cell_at",
    "cell_centre",
    "cell_count",
    "cell_polygon",
    "in_grid",
    "validate_view",
    "GEOMETRY_FORMAT",
    "MAX_BATCH_OPERATIONS",
    "MAX_COORDINATE",
    "MAX_MAPS_PER_LIBRARY",
    "MAX_PARTS",
    "MAX_PLACEMENTS_PER_MAP",
    "MAX_PLACEMENT_BYTES",
    "MAX_THEME_NAME",
    "MAX_VERTICES",
    "ROLES",
    "STROKES",
    "SYSTEM_FORMAT",
    "THEME_NAMES",
    "WEIGHTS",
    "WRITABLE_KINDS",
    "MapDocumentError",
    "Validated",
    "ValidatedPlacement",
    "effective_kind",
    "keep_theme_hint",
    "read_role",
    "read_theme_hint",
    "validate_geometry",
    "validate_placement",
    "validate_role",
    "validate_style",
    "validate_system",
    "validate_theme_hint",
    "validate_z",
]
