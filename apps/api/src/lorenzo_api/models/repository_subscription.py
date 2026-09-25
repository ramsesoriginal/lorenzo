from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, CreatedBy


class RepositorySubscription(Base):
    """A repository's owner granting another tenant access to it - see ADR
    0118/RFC 0024 §3. The one table that spans two tenants, so it has no
    tenant_id of its own: its RLS lets either side read or remove it, and
    only the repository's side create it. A trigger refuses a grant to
    anything but a `repository` tenant.

    A grant, not a mode: while it exists the subscriber can browse, copy,
    and check for updates. Removing it never touches what a copy already
    produced (RFC 0024 §6).
    """

    __tablename__ = "repository_subscription"
    __table_args__ = (
        CheckConstraint(
            "repository_tenant_id <> subscriber_tenant_id",
            name="repository_subscription_not_self",
        ),
    )

    repository_tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True
    )
    subscriber_tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[CreatedAt]
    created_by: Mapped[CreatedBy]
