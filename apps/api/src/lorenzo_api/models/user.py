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
    # Needed for authgear_roles below - a bare (non-Mapped[]) annotation on
    # a Declarative class otherwise raises MappedAnnotationError at class-
    # definition time; this opts that one attribute out of ORM mapping
    # instead of wrapping it in ClassVar[] (which would make mypy reject the
    # per-instance assignment get_current_user/_fake_current_user need).
    __allow_unmapped__ = True

    id: Mapped[UuidPk]
    authgear_subject_id: Mapped[str] = mapped_column(unique=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    # Deliberately NOT `Mapped[...]` - a plain, non-persisted attribute, not
    # a mapped column (ADR 0033/RFC 0012). Attached per-request by
    # dependencies.get_current_user from the verified token's own Authgear
    # role claim (or by tests/conftest.py's `_fake_current_user` test
    # double), and read by dependencies.require_tenant_creator_role. A
    # second dependency reading TokenClaimsDep/verify_token's own output
    # directly would silently require a *real* signed token under the
    # `client` test fixture's get_current_user override - this sidesteps
    # that by piggybacking on the same User object every route already
    # gets. Never written back to the database - Authgear stays the single
    # source of truth for who holds this role (ADR 0009's own boundary, the
    # other direction).
    authgear_roles: frozenset[str]

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
    campaign_gms: Mapped[list[CampaignGm]] = relationship(
        lazy="raise_on_sql",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tenant_admin_campaign_opt_outs: Mapped[list[TenantAdminCampaignOptOut]] = relationship(
        lazy="raise_on_sql",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
