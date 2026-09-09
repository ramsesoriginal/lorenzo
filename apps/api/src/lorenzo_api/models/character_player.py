from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.being import Being
    from lorenzo_api.models.player import Player


class CharacterPlayer(Base):
    """Which player rows can currently pilot a character - a genuine n:m
    join, deliberately separate from `Being.owner_player_id` ("who
    primarily owns this character," singular). See ADR 0025: a single
    player can control more than one character at once (a Vampire
    coterie), and a single character can be linked into more than one
    campaign's player row (roster reuse). No surrogate id, matching every
    other pure n:m join in this schema (EntityPrototype, EntityStatGroup).
    """

    __tablename__ = "character_player"

    character_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("being.entity_id", ondelete="CASCADE"), primary_key=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("player.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]

    character: Mapped[Being] = relationship(lazy="raise_on_sql", back_populates="player_links")
    player: Mapped[Player] = relationship(lazy="raise_on_sql", back_populates="character_links")
