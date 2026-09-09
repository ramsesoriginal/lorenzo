from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.campaign import Campaign
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

    user: Mapped[User] = relationship(back_populates="players")
    campaign: Mapped[Campaign] = relationship(back_populates="players")
