"""Maps and their placements (ADR 0336)."""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Float, Integer, LargeBinary, SmallInteger, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class Map(Base):
    """The marker that makes an entry a Map. `system` is what its positions mean
    (`lorenzo.map-system/1`); `subject_entity_id` is the Location it depicts, an authored pointer
    that nothing reads to find where anything is."""

    __tablename__ = "map"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(system) = 'object'", name="map_system_object"),
        CheckConstraint(
            "theme_hint IS NULL OR char_length(theme_hint) BETWEEN 1 AND 32",
            name="map_theme_hint_length",
        ),
        CheckConstraint("view IS NULL OR jsonb_typeof(view) = 'object'", name="map_view_object"),
        same_tenant_fk("map_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "map_subject_fkey",
            ["subject_entity_id"],
            "location",
            ["entity_id"],
            ondelete="SET NULL (subject_entity_id)",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    system: Mapped[dict[str, Any]] = mapped_column(JSONB)
    subject_entity_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    # A theme name the renderer has (ADR 0352), kept as it is when this version does not know it.
    theme_hint: Mapped[str | None] = mapped_column(Text, default=None)
    # What is only drawn: a visual grid over a system that has none (ADR 0354).
    view: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), default=None)


class MapPlacement(Base):
    """Where one entry is drawn on one Map (ADR 0336): a drawing, never where the entry is."""

    __tablename__ = "map_placement"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(geometry) = 'object'", name="map_placement_geometry_object"),
        same_tenant_fk(
            "map_placement_map_fkey", ["map_entity_id"], "map", ["entity_id"], ondelete="CASCADE"
        ),
        same_tenant_fk(
            "map_placement_entry_fkey", ["entry_entity_id"], "entity", ondelete="CASCADE"
        ),
    )
    map_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    entry_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    geometry: Mapped[dict[str, Any]] = mapped_column(JSONB)
    role: Mapped[str | None] = mapped_column(Text, default=None)
    style: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    z: Mapped[int] = mapped_column(SmallInteger, default=0, server_default=text("0"))
    # Derived by the one write path (lorenzo_map.validate_placement), never by a client.
    bytes: Mapped[int] = mapped_column(Integer)
    minx: Mapped[float] = mapped_column(Float)
    miny: Mapped[float] = mapped_column(Float)
    maxx: Mapped[float] = mapped_column(Float)
    maxy: Mapped[float] = mapped_column(Float)


class MapLayer(Base):
    """A picture a Map is drawn over (ADR 0361): the first picture of one of the Map's own
    Information rows, so it is seen by those who see that row. `reviewed_sha256` is the fingerprint
    of the picture the layer was last set up for."""

    __tablename__ = "map_layer"
    __table_args__ = (
        CheckConstraint("position BETWEEN 0 AND 7", name="map_layer_position_range"),
        CheckConstraint(
            "opacity IS NULL OR opacity BETWEEN 0 AND 1", name="map_layer_opacity_range"
        ),
        CheckConstraint(
            "calibration IS NULL OR jsonb_typeof(calibration) = 'object'",
            name="map_layer_calibration_object",
        ),
        same_tenant_fk(
            "map_layer_map_fkey", ["map_entity_id"], "map", ["entity_id"], ondelete="CASCADE"
        ),
        same_tenant_fk(
            "map_layer_information_fkey", ["information_id"], "information", ondelete="CASCADE"
        ),
    )
    map_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    information_id: Mapped[uuid.UUID]
    tenant_id: Mapped[TenantFk] = mapped_column(primary_key=True)
    calibration: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    opacity: Mapped[float | None] = mapped_column(Float, default=None)
    reviewed_sha256: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
