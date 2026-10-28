"""Frames and axes (ADR 0369): an entry is a frame on an axis, and an entry is on a frame."""

import uuid

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

AXIS_FORMAT = "axis ~ '^[a-z][a-z0-9_]{0,31}$'"


class Frame(Base):
    """The entry is a frame on the axis: a designation, not a kind. An entry may be a frame on
    several axes. Nothing here is read as containment, a place or reach."""

    __tablename__ = "frame"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", "axis", name="frame_entity_tenant_axis_key"),
        CheckConstraint(AXIS_FORMAT, name="frame_axis_format"),
        same_tenant_fk("frame_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    axis: Mapped[str] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]


class EntityFrame(Base):
    """The entry is on a frame of the axis: at most one per axis, no time, never inherited. The key
    to `frame` carries the axis, so a row and its frame always agree on it."""

    __tablename__ = "entity_frame"
    __table_args__ = (
        CheckConstraint("entity_id <> frame_entity_id", name="entity_frame_distinct"),
        CheckConstraint(AXIS_FORMAT, name="entity_frame_axis_format"),
        same_tenant_fk("entity_frame_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        ForeignKeyConstraint(
            ["frame_entity_id", "tenant_id", "axis"],
            ["frame.entity_id", "frame.tenant_id", "frame.axis"],
            name="entity_frame_frame_fkey",
            ondelete="CASCADE",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    axis: Mapped[str] = mapped_column(primary_key=True)
    frame_entity_id: Mapped[uuid.UUID]
    tenant_id: Mapped[TenantFk]
