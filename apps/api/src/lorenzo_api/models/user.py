from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.campaign_gm import CampaignGm
    from lorenzo_api.models.membership import Membership
    from lorenzo_api.models.player import Player
    from lorenzo_api.models.tenant_admin_campaign_opt_out import TenantAdminCampaignOptOut


class User(Base):
    """Global identity, not tenant-scoped - a link back to Authgear's
    verified subject id (ADR 0009), holding only what's actually
    domain-relevant (ADR 0010/0022). No email, name, password, or OAuth
    token lives here - those stay in Authgear.

    Table is `app_user`, not `user` - `user` is a reserved word in Postgres
    (confirmed empirically, not assumed - see ADR 0022).
    """

    __tablename__ = "app_user"

    id: Mapped[UuidPk]
    authgear_subject_id: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    memberships: Mapped[list[Membership]] = relationship(
        lazy="raise_on_sql",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    players: Mapped[list[Player]] = relationship(
        lazy="raise_on_sql",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # foreign_keys explicit on both of these: campaign_gm/
    # tenant_admin_campaign_opt_out each gained a second FK to app_user
    # (created_by, ADR 0034) alongside user_id, which this relationship
    # must be pointed at explicitly rather than left for SQLAlchemy to
    # guess between.
    campaign_gms: Mapped[list[CampaignGm]] = relationship(
        lazy="raise_on_sql",
        foreign_keys="CampaignGm.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tenant_admin_campaign_opt_outs: Mapped[list[TenantAdminCampaignOptOut]] = relationship(
        lazy="raise_on_sql",
        foreign_keys="TenantAdminCampaignOptOut.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
