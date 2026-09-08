from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class ItemInstance(Base):
    """A specific, ownable item ("My Shovel") - see ADR 0019 and RFC 0001.
    Its entity is expected to have at least one direct entity_prototype row
    pointing at an item-typed entity - not enforced anywhere, the same kind
    of accepted limitation as entity_stat_group's tenant agreement
    (ADR 0014).

    owner_entity_id references a character, which doesn't exist yet (RFC
    0002) - referencing entity.id generically for now, ON DELETE SET NULL
    rather than CASCADE like every other FK in this schema (ADR 0018): the
    owner disappearing shouldn't delete the item, just leave it ownerless.
    """

    __tablename__ = "item_instance"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    owner_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entity.id", ondelete="SET NULL"), index=True
    )
    tenant_id: Mapped[TenantFk]

    entity: Mapped[Entity] = relationship(foreign_keys=[entity_id], back_populates="item_instance")
    owner: Mapped[Entity | None] = relationship(foreign_keys=[owner_entity_id])
