from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class CampaignProfilePicture(Base):
    """Links a Campaign to its one ProfilePicture - see ADR 0056. `tenant_id`
    is a denormalized copy of `campaign.tenant_id` (RLS only), same pattern
    `player`/`campaign_gm` already use for their own tenant_id column - no
    `tenant` relationship, matching those tables' own precedent for a
    denormalized-only tenant_id.
    """

    __tablename__ = "campaign_profile_picture"
    __table_args__ = (
        same_tenant_fk(
            "campaign_profile_picture_campaign_id_fkey",
            ["campaign_id"],
            "campaign",
            ondelete="CASCADE",
        ),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    profile_picture_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profile_picture.id", ondelete="CASCADE"), unique=True
    )
