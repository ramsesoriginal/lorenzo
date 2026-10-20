"""Materialized local periods and minimal Events, without causal semantics (ADR 0309)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class StoryEvent(Base):
    __tablename__ = "story_event"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="story_event_entity_tenant_key"),
        same_tenant_fk("story_event_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    entity: Mapped[Entity] = relationship(
        foreign_keys="StoryEvent.entity_id", lazy="raise_on_sql", back_populates="story_event"
    )


class CalendarPeriod(Base):
    __tablename__ = "calendar_period"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="calendar_period_entity_tenant_key"),
        UniqueConstraint(
            "entity_id",
            "calendar_entity_id",
            "tenant_id",
            name="calendar_period_calendar_tenant_key",
        ),
        UniqueConstraint(
            "calendar_entity_id",
            "year",
            "segment",
            "day",
            name="calendar_period_coordinate_key",
            postgresql_nulls_not_distinct=True,
        ),
        same_tenant_fk("calendar_period_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "calendar_period_calendar_fkey",
            ["calendar_entity_id"],
            "calendar",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
        same_tenant_fk(
            "calendar_period_parent_fkey",
            ["parent_entity_id", "calendar_entity_id"],
            "calendar_period",
            ["entity_id", "calendar_entity_id"],
            ondelete="NO ACTION",
        ),
        CheckConstraint("year BETWEEN -1000000 AND 1000000", name="calendar_period_year_range"),
        CheckConstraint(
            "(segment IS NULL AND day IS NULL AND parent_entity_id IS NULL) "
            "OR (segment IS NOT NULL AND parent_entity_id IS NOT NULL "
            "AND (day IS NULL OR day BETWEEN 1 AND 1000))",
            name="calendar_period_shape",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    calendar_entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    year: Mapped[int]
    segment: Mapped[str | None]
    day: Mapped[int | None]
    parent_entity_id: Mapped[uuid.UUID | None]
    entity: Mapped[Entity] = relationship(
        foreign_keys="CalendarPeriod.entity_id",
        lazy="raise_on_sql",
        back_populates="calendar_period",
    )


class EntryCalendarPeriod(Base):
    __tablename__ = "entry_calendar_period"
    __table_args__ = (
        same_tenant_fk(
            "entry_calendar_period_entry_fkey", ["entity_id"], "entity", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "entry_calendar_period_period_fkey",
            ["period_entity_id"],
            "calendar_period",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    period_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
