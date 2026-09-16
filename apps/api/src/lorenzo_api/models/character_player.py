from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.character import Character
    from lorenzo_api.models.player import Player


class CharacterPlayer(Base):
    """Which player rows can currently pilot a character - a genuine n:m
    join, deliberately separate from `Character.owner_player_id` ("who
    primarily owns this character," singular). See ADR 0025: a single
    player can control more than one character at once (a Vampire
    coterie), and a single character can be linked into more than one
    campaign's player row (roster reuse). No surrogate id, matching every
    other pure n:m join in this schema (EntityPrototype, EntityStatGroup).

    `character_entity_id` retargeted from `being.entity_id` to
    `character.entity_id` (ADR 0031/RFC 0004): a being now has to be
    "promoted" to a character row before it can be rostered - a plain,
    untracked NPC can't be. A deliberate tightening from ADR 0025's
    original design, not a side effect.
    """

    __tablename__ = "character_player"

    character_entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("character.entity_id", ondelete="CASCADE"), primary_key=True
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("player.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]

    character: Mapped[Character] = relationship(lazy="raise_on_sql", back_populates="player_links")
    player: Mapped[Player] = relationship(lazy="raise_on_sql", back_populates="character_links")
