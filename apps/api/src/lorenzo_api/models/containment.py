from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class Containment(Base):
    """Where an entity physically is - an item in a backpack, a backpack on
    a character, a character in a room - see ADR 0016 and RFC 0001. No row
    means "not contained in anything". Unlike EntityPrototype, the PK is
    child_entity_id alone: an entity has at most one direct container, so
    moving it is an UPDATE of parent_entity_id, not delete-then-insert.
    Deliberately no cycle prevention - see the ADR for why.
    """

    __tablename__ = "containment"

    child_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    parent_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[TenantFk]

    child: Mapped[Entity] = relationship(
        lazy="raise_on_sql", foreign_keys=[child_entity_id], back_populates="containment"
    )
    parent: Mapped[Entity] = relationship(
        lazy="raise_on_sql", foreign_keys=[parent_entity_id], back_populates="contained_links"
    )
