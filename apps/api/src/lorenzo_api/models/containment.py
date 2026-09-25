from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

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
    __table_args__ = (
        same_tenant_fk(
            "containment_child_entity_id_fkey", ["child_entity_id"], "entity", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "containment_parent_entity_id_fkey", ["parent_entity_id"], "entity", ondelete="CASCADE"
        ),
        CheckConstraint("quantity >= 1", name="containment_quantity_positive"),
    )

    child_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    parent_entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    tenant_id: Mapped[TenantFk]
    # How many indistinguishable copies of child_entity_id this row
    # represents - see ADR 0041. DEFAULT 1 (not nullable) so an ordinary,
    # non-stacked containment link is trivially and correctly "a stack of
    # one," not a special case every aggregate query has to COALESCE
    # around - mirrors stat_group.priority's identical server_default
    # shape (ADR 0014).
    quantity: Mapped[int] = mapped_column(Integer, server_default=text("1"))

    child: Mapped[Entity] = relationship(
        lazy="raise_on_sql", foreign_keys=[child_entity_id], back_populates="containment"
    )
    parent: Mapped[Entity] = relationship(
        lazy="raise_on_sql", foreign_keys=[parent_entity_id], back_populates="contained_links"
    )
