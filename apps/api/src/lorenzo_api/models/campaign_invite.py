from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, TenantFk, UuidPk, same_tenant_fk


class CampaignInvite(Base):
    """A shareable link that lets people join one campaign as players
    themselves - see ADR 0092/RFC 0023.

    The token is never stored: only its SHA-256 (`token_hash`, unique), so
    a leaked table leaks no working links. `expires_at` is required (a
    link always ends); `max_uses` is optional - `NULL` means unlimited,
    deliberately (ADR 0092 records that trade-off). `use_count` always
    counts, so an unlimited link's usage is still visible.

    RLS is two policies (migration `4f1c9a7b2d3e`): the ordinary tenant one,
    plus a **select-only** one keyed on `app.invite_token_hash`, which only
    the two public redemption routes ever set - the caller doesn't know the
    tenant until the token has been looked up, the same shape `notification`
    needed (ADR 0058). Holding a token can read that one row and nothing
    else, and cannot write anything.
    """

    __tablename__ = "campaign_invite"
    __table_args__ = (
        same_tenant_fk(
            "campaign_invite_campaign_id_fkey", ["campaign_id"], "campaign", ondelete="CASCADE"
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    campaign_id: Mapped[uuid.UUID] = mapped_column(index=True)
    token_hash: Mapped[str] = mapped_column(unique=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    created_at: Mapped[CreatedAt]
    expires_at: Mapped[datetime]
    max_uses: Mapped[int | None]
    use_count: Mapped[int] = mapped_column(server_default=text("0"))
    revoked_at: Mapped[datetime | None]
