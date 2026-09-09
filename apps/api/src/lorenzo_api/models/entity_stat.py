from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.stat_definition import StatDefinition


class EntityStat(Base):
    """An entity's direct (non-inherited) value for one stat_definition - see
    ADR 0014 and RFC 0001. No resolution/inheritance walk yet - that needs
    entity_prototype, which doesn't exist.
    """

    __tablename__ = "entity_stat"
    __table_args__ = (
        CheckConstraint(
            "num_nonnulls(value_int, value_text, value_float, value_bool) = 1",
            name="entity_stat_exactly_one_value",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stat_definition.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    value_int: Mapped[int | None]
    value_text: Mapped[str | None]
    value_float: Mapped[float | None]
    value_bool: Mapped[bool | None]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    entity: Mapped[Entity] = relationship(lazy="raise_on_sql", back_populates="stats")
    stat_definition: Mapped[StatDefinition] = relationship(
        lazy="raise_on_sql", back_populates="entity_stats"
    )
