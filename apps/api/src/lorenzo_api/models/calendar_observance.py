"""A recurring observance is a rule, not a recorded occurrence (ADR 0310)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class CalendarObservance(Base):
    __tablename__ = "calendar_observance"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="calendar_observance_entity_tenant_key"),
        same_tenant_fk(
            "calendar_observance_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "calendar_observance_calendar_fkey",
            ["calendar_entity_id"],
            "calendar",
            ["entity_id"],
            ondelete="NO ACTION",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    calendar_entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    rule: Mapped[dict[str, Any]] = mapped_column(JSONB)
    entity: Mapped[Entity] = relationship(
        foreign_keys="CalendarObservance.entity_id",
        lazy="raise_on_sql",
        back_populates="calendar_observance",
    )
