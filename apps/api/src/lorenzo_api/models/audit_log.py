from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, TenantFk, UuidPk


class AuditLog(Base):
    """One tenant-admin-relevant event - see ADR 0059. A first,
    deliberately narrow slice: only membership and campaign/GM lifecycle
    events are logged (see `lorenzo_api.activity_log` for exactly which),
    not an exhaustive record of every mutation in the API.

    `tenant_id` is **not nullable** - platform-scope events (e.g. account
    suspension, ADR 0053) are explicitly out of scope for this slice, not
    a NULL case to design around yet. Plain `tenant_id = app.tenant_id`
    RLS, the ordinary shape - unlike `notification` (ADR 0054/0057), this
    is inherently a per-tenant admin view, not a cross-tenant personal
    inbox, so no self-access clause is needed.

    `action`/`target_type` are free text, not native enums - same
    `Information.type`/`Notification.type` precedent ADR 0017/0054 already
    established: caller-chosen categorization, not a fixed schema-level
    discriminant. `actor_id` is `ON DELETE SET NULL`, matching
    `created_by` everywhere else (ADR 0029).
    """

    __tablename__ = "audit_log"

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str]
    target_type: Mapped[str]
    target_id: Mapped[uuid.UUID | None]
    detail: Mapped[str | None]
    created_at: Mapped[CreatedAt]
