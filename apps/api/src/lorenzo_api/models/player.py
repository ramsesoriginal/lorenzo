from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.being import Being
    from lorenzo_api.models.campaign import Campaign
    from lorenzo_api.models.character_player import CharacterPlayer
    from lorenzo_api.models.knowledge import Knowledge
    from lorenzo_api.models.user import User


class Player(Base):
    """The per-user, per-campaign instance, sitting between User and
    Character - see ADR 0024/RFC 0002. `tenant_id` is a denormalized copy
    of `campaign.tenant_id` (RLS only) - no `tenant` relationship here,
    matching how other denormalized-only tenant_id columns in this schema
    (e.g. `entity_stat_group.tenant_id`) stay plain FK columns rather than
    each getting their own redundant relationship object.
    """

    __tablename__ = "player"
    __table_args__ = (UniqueConstraint("campaign_id", "user_id"),)

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[TenantFk]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    user: Mapped[User] = relationship(lazy="raise_on_sql", back_populates="players")
    campaign: Mapped[Campaign] = relationship(lazy="raise_on_sql", back_populates="players")
    # owned_beings: SET NULL, not CASCADE (ADR 0025) - passive_deletes=True
    # so a deleted player leaves its beings player-less via the DB's own
    # ON DELETE SET NULL, rather than the ORM loading and updating them.
    # No delete-orphan: losing this player must not delete the being.
    owned_beings: Mapped[list[Being]] = relationship(
        lazy="raise_on_sql", back_populates="owner_player", passive_deletes=True
    )
    character_links: Mapped[list[CharacterPlayer]] = relationship(
        lazy="raise_on_sql",
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    knowledge_links: Mapped[list[Knowledge]] = relationship(
        lazy="raise_on_sql",
        back_populates="knower_player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
