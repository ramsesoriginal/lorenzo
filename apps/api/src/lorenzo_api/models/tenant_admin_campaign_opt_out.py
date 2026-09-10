from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base

if TYPE_CHECKING:
    from lorenzo_api.models.campaign import Campaign
    from lorenzo_api.models.user import User


class TenantAdminCampaignOptOut(Base):
    """Lets a tenant admin (Membership.role in OWNER/ORGA - widened from
    ORGA-only by ADR 0030) suppress their own blanket visibility for one
    campaign, so they can participate as an ordinary character in it
    without their tenant-wide access bleeding in. See ADR 0026/ADR 0030/RFC
    0002/RFC 0003. A row's mere existence is the opt-out - there is no
    boolean/status column; "opted back in" is just deleting the row.

    Renamed from orga_campaign_opt_out (ADR 0030/RFC 0003): the opt-out now
    applies to whichever of OWNER/ORGA the caller holds, not just ORGA, so
    the old name no longer described what it actually governs. Same shape
    as CampaignGm for the same reasons: composite primary key, tenant_id
    leading, no tenant relationship (denormalized RLS-only column, matching
    Player's precedent).
    """

    __tablename__ = "tenant_admin_campaign_opt_out"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("campaign.id", ondelete="CASCADE"), primary_key=True
    )

    user: Mapped[User] = relationship(
        lazy="raise_on_sql", back_populates="tenant_admin_campaign_opt_outs"
    )
    campaign: Mapped[Campaign] = relationship(
        lazy="raise_on_sql", back_populates="tenant_admin_opt_outs"
    )
