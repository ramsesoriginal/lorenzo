"""Joined source identity and operational join checkpoints (ADR 0348)."""

import uuid
from typing import Any

from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UuidPk, same_tenant_fk


class ManuscriptRedirect(Base):
    __tablename__ = "manuscript_redirect"
    __table_args__ = (
        CheckConstraint("source_id <> destination_id", name="manuscript_redirect_not_self"),
        CheckConstraint(
            "payload_id IS NULL OR child_id IS NULL", name="manuscript_redirect_one_anchor"
        ),
        same_tenant_fk(
            "manuscript_redirect_source_fkey", ["source_id"], "entity", ondelete="CASCADE"
        ),
        # Migrations restrict SET NULL to the reference column, preserving tenant_id.
        same_tenant_fk(
            "manuscript_redirect_destination_fkey",
            ["destination_id"],
            "entity",
            ondelete="SET NULL",
        ),
        same_tenant_fk(
            "manuscript_redirect_payload_fkey", ["payload_id"], "payload", ondelete="SET NULL"
        ),
        same_tenant_fk(
            "manuscript_redirect_child_fkey", ["child_id"], "entity", ondelete="SET NULL"
        ),
    )
    source_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    destination_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    payload_id: Mapped[uuid.UUID | None]
    child_id: Mapped[uuid.UUID | None]


class ManuscriptJoin(Base):
    __tablename__ = "manuscript_join"
    __table_args__ = (
        same_tenant_fk("manuscript_join_source_fkey", ["source_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "manuscript_join_destination_fkey", ["destination_id"], "entity", ondelete="CASCADE"
        ),
    )
    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    source_id: Mapped[uuid.UUID] = mapped_column(index=True)
    destination_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_id: Mapped[CreatedBy]
    created_at: Mapped[CreatedAt]
    request_hash: Mapped[str]
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB)
