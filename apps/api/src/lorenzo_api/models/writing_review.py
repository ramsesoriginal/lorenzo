"""Operational review access and fixed-audience LorenzoScript notes (ADR 0343)."""

import uuid

from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UuidPk, same_tenant_fk


class WritingReviewGrant(Base):
    __tablename__ = "writing_review_grant"
    __table_args__ = (
        same_tenant_fk(
            "writing_review_grant_edition_fkey",
            ["edition_id"],
            "edition",
            target_columns=["entity_id"],
            ondelete="CASCADE",
        ),
    )
    tenant_id: Mapped[TenantFk]
    edition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True
    )


class WritingReviewNote(Base):
    __tablename__ = "writing_review_note"
    __table_args__ = (
        same_tenant_fk(
            "writing_review_note_edition_fkey",
            ["edition_id"],
            "edition",
            target_columns=["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "writing_review_note_entry_fkey", ["entry_id"], "entity", ondelete="CASCADE"
        ),
    )
    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    edition_id: Mapped[uuid.UUID] = mapped_column(index=True)
    entry_id: Mapped[uuid.UUID]
    author_id: Mapped[CreatedBy]
    created_at: Mapped[CreatedAt]
    content: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(server_default=text("1"))
