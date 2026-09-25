from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import (
    Base,
    CreatedAt,
    CreatedBy,
    TenantFk,
    UpdatedAt,
    UpdatedBy,
    UuidPk,
    same_tenant_fk,
)

if TYPE_CHECKING:
    from lorenzo_api.models.campaign import Campaign
    from lorenzo_api.models.character import Character
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
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint("id", "tenant_id", name="player_id_tenant_id_key"),
        same_tenant_fk("player_campaign_id_fkey", ["campaign_id"], "campaign", ondelete="CASCADE"),
        UniqueConstraint("campaign_id", "user_id"),
    )

    id: Mapped[UuidPk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(index=True)
    tenant_id: Mapped[TenantFk]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    # ADR 0029/0036: always the managing GM/tenant admin who added this
    # player - self-service joining doesn't exist yet (RFC 0007's own Open
    # questions), so there's no other actor this could ever be.
    # updated_by never diverges from created_by in practice (no PATCH
    # /players exists), kept anyway for consistency with created_at/
    # updated_at's own identical never-actually-updated precedent.
    created_by: Mapped[CreatedBy]
    updated_by: Mapped[UpdatedBy]

    # foreign_keys explicit: player gained created_by/updated_by (ADR 0036),
    # a second and third FK to app_user alongside user_id - same
    # disambiguation User.campaign_gms/tenant_admin_campaign_opt_outs
    # already needed.
    user: Mapped[User] = relationship(
        lazy="raise_on_sql", foreign_keys=[user_id], back_populates="players"
    )
    campaign: Mapped[Campaign] = relationship(
        foreign_keys="Player.campaign_id", lazy="raise_on_sql", back_populates="players"
    )
    # owned_characters: SET NULL, not CASCADE (ADR 0025) - passive_deletes=True
    # so a deleted player leaves its characters player-less via the DB's own
    # ON DELETE SET NULL, rather than the ORM loading and updating them.
    # No delete-orphan: losing this player must not delete the character.
    # Renamed from owned_beings, following owner_player_id's move to
    # Character (ADR 0031/RFC 0004) - a plain being was never a valid
    # target, so nothing meaningful is lost, just made accurate.
    owned_characters: Mapped[list[Character]] = relationship(
        foreign_keys="Character.owner_player_id",
        lazy="raise_on_sql",
        back_populates="owner_player",
        passive_deletes=True,
    )
    character_links: Mapped[list[CharacterPlayer]] = relationship(
        foreign_keys="CharacterPlayer.player_id",
        lazy="raise_on_sql",
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    knowledge_links: Mapped[list[Knowledge]] = relationship(
        foreign_keys="Knowledge.knower_player_id",
        lazy="raise_on_sql",
        back_populates="knower_player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
