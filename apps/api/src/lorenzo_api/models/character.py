from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedBy, TenantFk, UpdatedBy

if TYPE_CHECKING:
    from lorenzo_api.models.being import Being
    from lorenzo_api.models.character_player import CharacterPlayer
    from lorenzo_api.models.group_member import GroupMember
    from lorenzo_api.models.player import Player


class Character(Base):
    """A tracked, named individual - layered directly under `being`, not a
    sibling extending `entity` the way `item`/`item_instance` are:
    `entity_id` is PK **and** FK to `being.entity_id`, not `entity.id`
    directly - the first three-level class-table-inheritance chain in
    this schema (entity -> being -> character). See ADR 0031/RFC 0004.

    A bare `being` with no `character` row remains perfectly valid - an
    unnamed monster stub, background NPC, or anything not worth
    individual tracking. `owner_player_id` moves here from `being` (ADR
    0025's original location): only a tracked individual is ever
    player-owned, so the column belongs on the layer that actually needs
    it, not on every sentient thing regardless.

    Same plain-Base-subclass-plus-explicit-relationship shape every other
    class-table-inheritance extension in this schema uses (Item/
    ItemInstance/Being all extend Entity this way) - not SQLAlchemy's own
    joined-table-inheritance mechanism (Python subclassing +
    polymorphic_identity), which nothing else here uses either.
    """

    __tablename__ = "character"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("being.entity_id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    owner_player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("player.id", ondelete="SET NULL"), index=True
    )
    created_by: Mapped[CreatedBy]
    updated_by: Mapped[UpdatedBy]

    being: Mapped[Being] = relationship(lazy="raise_on_sql", back_populates="character")
    owner_player: Mapped[Player | None] = relationship(
        lazy="raise_on_sql", back_populates="owned_characters"
    )
    player_links: Mapped[list[CharacterPlayer]] = relationship(
        lazy="raise_on_sql",
        back_populates="character",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    group_links: Mapped[list[GroupMember]] = relationship(
        lazy="raise_on_sql",
        back_populates="character",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
