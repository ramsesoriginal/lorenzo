from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class Ownership(Base):
    """Which character (or, later, some other kind of entity - RFC 0002)
    owns a given entity - see ADR 0025. owned_entity_id alone is the
    primary key, matching Containment.child_entity_id's precedent exactly:
    an entity can only have one owner at a time, globally. owner_character_id
    is a plain FK to entity.id, not being.entity_id - RFC 0002 is explicit
    that ownership "isn't restricted to characters as an owner at the
    schema level" (a faction or place could plausibly own something
    later). Both FKs are ON DELETE CASCADE, unlike Being.owner_player_id:
    the ownership fact is meaningless once either side is gone, and since
    ownership is its own row rather than a nullable column, cascading the
    row away is equivalent to what SET NULL would have been.
    """

    __tablename__ = "ownership"

    owned_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    owner_character_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[TenantFk]

    owned_entity: Mapped[Entity] = relationship(
        foreign_keys=[owned_entity_id], back_populates="ownership"
    )
    owner_character: Mapped[Entity] = relationship(
        foreign_keys=[owner_character_id], back_populates="owned_entity_links"
    )
