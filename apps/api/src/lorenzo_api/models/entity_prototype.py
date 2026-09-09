from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class EntityPrototype(Base):
    """An entity's prototypes (the inheritance graph) - see ADR 0015 and RFC
    0001. Cycle prevention: direct self-loops are rejected by the CHECK
    below; transitive cycles are rejected by a BEFORE INSERT trigger (see
    the migration) that this model can't express.
    """

    __tablename__ = "entity_prototype"
    __table_args__ = (
        CheckConstraint("entity_id <> prototype_id", name="entity_prototype_no_self_loop"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    prototype_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]

    entity: Mapped[Entity] = relationship(
        lazy="raise_on_sql", foreign_keys=[entity_id], back_populates="prototype_links"
    )
    prototype: Mapped[Entity] = relationship(
        lazy="raise_on_sql", foreign_keys=[prototype_id], back_populates="dependent_links"
    )
