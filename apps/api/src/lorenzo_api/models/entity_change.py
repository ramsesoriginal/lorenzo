from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk


class EntityChange(Base):
    """One row of a player's change feed: something happened to an item one
    of their characters owns or carries - see ADR 0099.

    Fanned out at write time, one row per recipient (ADR 0058's shape), so
    `GET /me/changes` is a single flat query. `entity_id` is deliberately
    not a foreign key - a `deleted` row must outlive its item - and
    `entity_name` is copied in for the same reason.

    `id` and `occurred_at` are generated in Python, never by the database:
    RLS here admits reads only to the recipient (`user_id = app.user_id`),
    and the writer is usually someone else, so an `INSERT ... RETURNING`
    read-back would fail the SELECT policy (the trap ADR 0058 hit). With
    nothing server-generated there is no RETURNING.
    """

    __tablename__ = "entity_change"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[TenantFk]
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), index=True
    )
    character_entity_id: Mapped[uuid.UUID]
    entity_id: Mapped[uuid.UUID]
    kind: Mapped[str]
    entity_name: Mapped[str]
    detail: Mapped[str | None]
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL")
    )
    actor_visible: Mapped[bool]
    occurred_at: Mapped[datetime]
