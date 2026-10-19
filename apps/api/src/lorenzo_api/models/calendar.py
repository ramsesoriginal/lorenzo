"""An authored calendar, independent of clocks and causal order (ADR 0308)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, UpdatedAt, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class Calendar(Base):
    __tablename__ = "calendar"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="calendar_entity_id_tenant_id_key"),
        same_tenant_fk("calendar_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[UpdatedAt]
    entity: Mapped[Entity] = relationship(
        foreign_keys="Calendar.entity_id", lazy="raise_on_sql", back_populates="calendar"
    )
