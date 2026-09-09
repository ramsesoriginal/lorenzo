from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.campaign_gm import CampaignGm
    from lorenzo_api.models.membership import Membership
    from lorenzo_api.models.orga_campaign_opt_out import OrgaCampaignOptOut
    from lorenzo_api.models.player import Player


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
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    players: Mapped[list[Player]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    campaign_gms: Mapped[list[CampaignGm]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    orga_campaign_opt_outs: Mapped[list[OrgaCampaignOptOut]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
