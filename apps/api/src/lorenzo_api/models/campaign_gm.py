from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base

if TYPE_CHECKING:
    from lorenzo_api.models.campaign import Campaign
    from lorenzo_api.models.user import User


class CampaignGm(Base):
    """Grants a user GM access to a campaign - fully separate from Player,
    since GMing and playing track different resources and aren't mutually
    exclusive (a user can hold both a Player row and a CampaignGm row for
    the same campaign at once). See ADR 0026/RFC 0002.

    Composite primary key, tenant_id leading, matching Membership's own
    shape and reasoning (ADR 0022) - no surrogate id, since nothing needs
    to reference a specific grant by id. tenant_id is a denormalized copy
    of campaign.tenant_id (RLS only) - no tenant relationship here,
    matching Player's own precedent for the same kind of column.
    """

    __tablename__ = "campaign_gm"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped[User] = relationship(lazy="raise_on_sql", back_populates="campaign_gms")
    campaign: Mapped[Campaign] = relationship(lazy="raise_on_sql", back_populates="gms")
