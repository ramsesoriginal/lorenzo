"""Explicit clock coordinates, independent of Event order (ADR 0320)."""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, UpdatedAt, same_tenant_fk


class Clock(Base):
    __tablename__ = "clock"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="clock_entity_tenant_key"),
        UniqueConstraint("entity_id", "tenant_id", "ticking", name="clock_ticking_key"),
        same_tenant_fk("clock_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    ticking: Mapped[bool] = mapped_column(default=True, server_default="true")
    updated_at: Mapped[UpdatedAt]


class EventClockReading(Base):
    __tablename__ = "event_clock_reading"
    __table_args__ = (
        same_tenant_fk(
            "event_clock_reading_event_fkey",
            ["event_entity_id"],
            "story_event",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
        same_tenant_fk(
            "event_clock_reading_clock_fkey",
            ["clock_entity_id", "ticking"],
            "clock",
            ["entity_id", "ticking"],
            ondelete="NO ACTION",
        ),
        CheckConstraint("ticking", name="event_clock_reading_ticking"),
        CheckConstraint("clock_range_valid(data)", name="event_clock_reading_range"),
    )
    event_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    clock_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    ticking: Mapped[bool] = mapped_column(default=True, server_default="true")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_shared: Mapped[bool] = mapped_column(default=False, server_default="false")
    updated_at: Mapped[UpdatedAt]


class CalendarReckoning(Base):
    __tablename__ = "calendar_reckoning"
    __table_args__ = (
        same_tenant_fk(
            "calendar_reckoning_calendar_fkey",
            ["calendar_entity_id"],
            "calendar",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
        same_tenant_fk(
            "calendar_reckoning_clock_fkey",
            ["clock_entity_id", "ticking"],
            "clock",
            ["entity_id", "ticking"],
            ondelete="NO ACTION",
        ),
        CheckConstraint("ticking", name="calendar_reckoning_ticking"),
        CheckConstraint(
            "clock_range_valid(jsonb_build_object('lo',data->'reading','hi',data->'reading','lo_inclusive',true,'hi_inclusive',true))",
            name="calendar_reckoning_reading",
        ),
    )
    calendar_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    clock_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    ticking: Mapped[bool] = mapped_column(default=True, server_default="true")
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_shared: Mapped[bool] = mapped_column(default=False, server_default="false")
    updated_at: Mapped[UpdatedAt]
