from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.stat_definition import StatDefinition


class StatDefinitionEnumValue(Base):
    """One allowed value of an `enum` stat_definition - see ADR 0103/RFC
    0016. `sort_order` is a display hint (`common` before `legendary`), not
    unique.
    """

    __tablename__ = "stat_definition_enum_value"
    __table_args__ = (
        UniqueConstraint("stat_definition_id", "value", name="stat_definition_enum_value_unique"),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stat_definition.id", ondelete="CASCADE"), index=True
    )
    value: Mapped[str]
    sort_order: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    stat_definition: Mapped[StatDefinition] = relationship(
        lazy="raise_on_sql", back_populates="enum_values"
    )
