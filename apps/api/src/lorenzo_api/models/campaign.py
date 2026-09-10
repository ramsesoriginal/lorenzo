from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UpdatedAt, UpdatedBy, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.campaign_gm import CampaignGm
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.player import Player
    from lorenzo_api.models.tenant import Tenant
    from lorenzo_api.models.tenant_admin_campaign_opt_out import TenantAdminCampaignOptOut


class Campaign(Base):
    """A specific play-through inside a Tenant's persistent world - a
    tenant can host more than one. See ADR 0024/RFC 0002, and ADR 0030 for
    slug/description/secret/entity_id.
    """

    __tablename__ = "campaign"
    # Scoped to the tenant (matching stat_group/stat_definition's own
    # UNIQUE(tenant_id, name) precedent), not global like tenant.slug - two
    # unrelated tenants both running a "the-ashen-crown" campaign isn't a
    # conflict.
    __table_args__ = (UniqueConstraint("tenant_id", "slug"),)

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    name: Mapped[str]
    game_system: Mapped[str]
    # Unlike Tenant, no server default for slug/description (ADR 0030) - a
    # real create-campaign flow (RFC 0006, not built yet) always supplies
    # both explicitly, and unlike tenant.slug's global uniqueness, a shared
    # literal default here could collide within one tenant (some existing
    # tests create more than one campaign per tenant), so a random
    # placeholder wouldn't even be safe. Test fixtures use the new
    # make_campaign() conftest helper instead.
    slug: Mapped[str]
    description: Mapped[str]
    secret: Mapped[bool] = mapped_column(default=False)
    # A dedicated Entity, not a class-table-inheritance PK+FK the way
    # item/being extend entity - campaign keeps its own surrogate id, this
    # is a plain reference column so every other FK to campaign.id is
    # unaffected. unique=True: "a dedicated Entity row" (RFC 0003's own
    # words) means exactly one campaign per entity - not asked for
    # explicitly, but directly follows from "dedicated" and costs nothing
    # to enforce. ON DELETE RESTRICT (not CASCADE, the one deliberate
    # exception in this table): deleting the campaign must explicitly clean
    # up its entity first (RFC 0006, not built yet) - a FK's ondelete only
    # governs the referencing row when the *referenced* row disappears, so
    # this only actually fires if someone deletes the Entity directly,
    # out of band.
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="RESTRICT"), unique=True
    )
    created_by: Mapped[CreatedBy]
    updated_by: Mapped[UpdatedBy]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    tenant: Mapped[Tenant] = relationship(lazy="raise_on_sql", back_populates="campaigns")
    entity: Mapped[Entity] = relationship(lazy="raise_on_sql", back_populates="campaign")
    players: Mapped[list[Player]] = relationship(
        lazy="raise_on_sql",
        back_populates="campaign",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    gms: Mapped[list[CampaignGm]] = relationship(
        lazy="raise_on_sql",
        back_populates="campaign",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tenant_admin_opt_outs: Mapped[list[TenantAdminCampaignOptOut]] = relationship(
        lazy="raise_on_sql",
        back_populates="campaign",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
