from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.character_player import CharacterPlayer
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.player import Player


class Being(Base):
    """Anything sentient/agentive - a character, an NPC - see ADR 0025 and
    RFC 0001/0002. Mirrors Item's bare class-table-inheritance shape plus
    one column: owner_player_id, nullable, ON DELETE SET NULL - matching
    item_instance.owner_entity_id's old precedent (the one deliberate
    exception to ADR 0018's cascade-everything default): losing the owning
    player shouldn't destroy the character, just leave it player-less (an
    NPC - RFC 0001's own framing of "is this a PC" as a derived fact:
    owner_player_id IS NOT NULL).
    """

    __tablename__ = "being"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    owner_player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("player.id", ondelete="SET NULL"), index=True
    )
    tenant_id: Mapped[TenantFk]

    entity: Mapped[Entity] = relationship(lazy="raise_on_sql", back_populates="being")
    owner_player: Mapped[Player | None] = relationship(
        lazy="raise_on_sql", back_populates="owned_beings"
    )
    player_links: Mapped[list[CharacterPlayer]] = relationship(
        lazy="raise_on_sql",
        back_populates="character",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
