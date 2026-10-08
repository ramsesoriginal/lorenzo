from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, Enum, ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, TenantFk, UuidPk, same_tenant_fk


class InviteKind(enum.Enum):
    """What redeeming an invite does (ADR 0211). `campaign` is every link ADR 0092 and 0177
    defined; `tenant_role` makes a membership of its tenant, a library or a repository (ADR
    0210's Author, or an Organizer); `library_access` grants its repository to a library the
    redeemer owns. Never an Owner, by any kind.
    """

    CAMPAIGN = "campaign"
    TENANT_ROLE = "tenant_role"
    LIBRARY_ACCESS = "library_access"


class InviteRole(enum.Enum):
    """What redeeming an invite makes someone. `player` is every link ADR 0092 defined and
    `gm` the one narrow exception in a campaign (ADR 0177); `author` and `orga` are what a
    `tenant_role` link makes in its tenant (ADR 0211). A `library_access` link has no role.
    """

    PLAYER = "player"
    GM = "gm"
    AUTHOR = "author"
    ORGA = "orga"


class Invite(Base):
    """A shareable link, one table for every kind (ADR 0211, which renamed `campaign_invite`).

    A `campaign` link lets people join one campaign as players themselves - see ADR
    0092/RFC 0023 - or, for `role = gm`, one person as a GM (ADR 0177: single use, at most 7
    days, only ever created by someone who could grant GM directly). A `tenant_role` link
    makes an Author or an Organizer of its tenant (single use or a small cap, short-lived, an
    Owner's alone), and a `library_access` link, minted for a repository by its Owner,
    grants the repository to a library its redeemer owns. `tenant_id` is the tenant the link
    is minted in: the campaign's, the library's or repository's own, the repository's.

    The token is never stored: only its SHA-256 (`token_hash`, unique), so
    a leaked table leaks no working links. `expires_at` is required (a
    link always ends); `max_uses` is optional for a campaign link - `NULL` means
    unlimited, deliberately (ADR 0092 records that trade-off) - and always set for the
    others. `use_count` always counts, so an unlimited link's usage is still visible.

    RLS is two policies (migrations `4f1c9a7b2d3e`, renamed by `c4a2f7e91b35`): the ordinary
    tenant one, plus a **select-only** one keyed on `app.invite_token_hash`, which only the two
    public redemption routes ever set - the caller doesn't know the tenant until the token has
    been looked up, the same shape `notification` needed (ADR 0058). Holding a token can read
    that one row and nothing else, and cannot write anything. The table is on
    `repository_access`'s excluded list: an invite is never repository content.
    """

    __tablename__ = "invite"
    __table_args__ = (
        same_tenant_fk("invite_campaign_id_fkey", ["campaign_id"], "campaign", ondelete="CASCADE"),
        CheckConstraint("max_uses IS NULL OR max_uses >= 1", name="invite_max_uses"),
        CheckConstraint(
            "(kind::text = 'campaign' AND campaign_id IS NOT NULL"
            " AND role IS NOT NULL AND role::text IN ('player', 'gm'))"
            " OR (kind::text = 'tenant_role' AND campaign_id IS NULL"
            " AND role IS NOT NULL AND role::text IN ('author', 'orga'))"
            " OR (kind::text = 'library_access' AND campaign_id IS NULL AND role IS NULL)",
            name="invite_kind_shape",
        ),
        CheckConstraint(
            "kind::text = 'campaign' OR max_uses IS NOT NULL", name="invite_non_campaign_capped"
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    kind: Mapped[InviteKind] = mapped_column(
        Enum(
            InviteKind,
            name="invite_kind",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=InviteKind.CAMPAIGN,
        server_default=text("'campaign'"),
    )
    campaign_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(unique=True)
    role: Mapped[InviteRole | None] = mapped_column(
        Enum(
            InviteRole,
            name="invite_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    created_at: Mapped[CreatedAt]
    expires_at: Mapped[datetime]
    max_uses: Mapped[int | None]
    use_count: Mapped[int] = mapped_column(server_default=text("0"))
    revoked_at: Mapped[datetime | None]
