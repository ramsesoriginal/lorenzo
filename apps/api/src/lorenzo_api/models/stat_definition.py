from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.entity_stat import EntityStat
    from lorenzo_api.models.stat_group import StatGroup
    from lorenzo_api.models.tenant import Tenant


class StatValueType(enum.Enum):
    """Which of entity_stat's value_* columns a stat's value lives in."""

    INT = "int"
    TEXT = "text"
    FLOAT = "float"
    BOOL = "bool"


class StatDefinition(Base):
    """Describes a single stat (weight, HP, ...) - see ADR 0014 and RFC 0001."""

    __tablename__ = "stat_definition"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    stat_group_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stat_group.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str]
    value_type: Mapped[StatValueType] = mapped_column(
        Enum(
            StatValueType,
            name="stat_value_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    tenant: Mapped[Tenant] = relationship(lazy="raise_on_sql", back_populates="stat_definitions")
    stat_group: Mapped[StatGroup] = relationship(
        lazy="raise_on_sql", back_populates="stat_definitions"
    )
    entity_stats: Mapped[list[EntityStat]] = relationship(
        lazy="raise_on_sql",
        back_populates="stat_definition",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
