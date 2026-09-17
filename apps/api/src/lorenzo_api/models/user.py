from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, ForeignKey, Text
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
    domain-relevant (ADR 0010/0022). No password or OAuth token lives here -
    those stay in Authgear. `email`/`nickname` (ADR 0050) are the one
    deliberate exception: `email` is a read-only cache of Authgear's own
    verified claim, `nickname` is genuinely local data with no Authgear
    equivalent - see each field's own comment below.

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
    # Both optional and globally unique (ADR 0050) - `unique=True` relies on
    # Postgres already treating every NULL as distinct from every other NULL
    # in a plain unique constraint (same reasoning ADR 0028 gives for
    # `knowledge`'s own UniqueConstraints), matching the migration's actual
    # partial unique indexes. `email` is synced read-only from Authgear's
    # verified `email` claim (dependencies.get_current_user) - never written
    # anywhere else. `nickname` has no Authgear equivalent and is set
    # directly via `PATCH /me`.
    email: Mapped[str | None] = mapped_column(unique=True)
    nickname: Mapped[str | None] = mapped_column(unique=True)
    # ADR 0053 - a suspended account is rejected on its very next request
    # (dependencies.get_current_user), anywhere in the API. Nullable: most
    # users are never suspended, and a fresh auto-provisioned user never is
    # by construction. suspended_by is ON DELETE SET NULL, same reasoning
    # created_by/updated_by already use (ADR 0029) - the suspending
    # operator's own account disappearing doesn't lift the suspension.
    suspended_at: Mapped[datetime | None]
    suspended_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    suspension_reason: Mapped[str | None]
    # ADR 0056 - a fuller profile. display_name is a friendly label,
    # deliberately not unique (unlike nickname, ADR 0050/0051's own lookup
    # handle) - two users can both be "Alex". locales is this codebase's
    # first native Postgres array column: a short, homogeneous,
    # order-not-load-bearing list of locale tags doesn't earn a join table
    # the way a genuine many-to-many domain relationship does. user_color
    # is validated as #RRGGBB at the schema boundary (schemas/users.py),
    # not here - same "format-checking is an application concern" precedent
    # PayloadDescription.locale (ADR 0017) already established.
    display_name: Mapped[str | None]
    pronouns: Mapped[str | None]
    bio: Mapped[str | None]
    locales: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    user_color: Mapped[str | None]
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

    # foreign_keys explicit on every one of these: membership/player each
    # gained a second and third FK to app_user (created_by/updated_by, ADR
    # 0036) alongside user_id, and campaign_gm/tenant_admin_campaign_opt_out
    # each gained a second FK (created_by, ADR 0034) alongside user_id -
    # every one must be pointed at user_id explicitly rather than left for
    # SQLAlchemy to guess between.
    memberships: Mapped[list[Membership]] = relationship(
        lazy="raise_on_sql",
        foreign_keys="Membership.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    players: Mapped[list[Player]] = relationship(
        lazy="raise_on_sql",
        foreign_keys="Player.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
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
