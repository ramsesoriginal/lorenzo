"""Retry acknowledgements and structural checkpoints for moves (ADR 0344)."""

import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UuidPk, same_tenant_fk


class ManuscriptMove(Base):
    __tablename__ = "manuscript_move"
    __table_args__ = (
        same_tenant_fk("manuscript_move_entry_fkey", ["entry_id"], "entity", ondelete="CASCADE"),
    )
    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    entry_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_id: Mapped[CreatedBy]
    created_at: Mapped[CreatedAt]
    request_hash: Mapped[str]
    acknowledgement: Mapped[dict[str, Any]] = mapped_column(JSONB)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ManuscriptExtraction(Base):
    """Operational receipt and outline checkpoint for Chapter extraction (ADR 0345)."""

    __tablename__ = "manuscript_extraction"
    __table_args__ = (
        same_tenant_fk(
            "manuscript_extraction_source_fkey", ["source_id"], "entity", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "manuscript_extraction_chapter_fkey", ["chapter_id"], "entity", ondelete="CASCADE"
        ),
    )
    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    source_id: Mapped[uuid.UUID] = mapped_column(index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_id: Mapped[CreatedBy]
    created_at: Mapped[CreatedAt]
    request_hash: Mapped[str]
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB)


class ManuscriptSceneExtraction(Base):
    """Private retry receipt for Scene extraction (ADR 0378)."""

    __tablename__ = "manuscript_scene_extraction"
    __table_args__ = tuple(
        same_tenant_fk(
            f"manuscript_scene_extraction_{name}_fkey", [f"{name}_id"], "entity", ondelete="CASCADE"
        )
        for name in ("source", "scene", "telling")
    )
    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    source_id: Mapped[uuid.UUID] = mapped_column(index=True)
    scene_id: Mapped[uuid.UUID] = mapped_column(index=True)
    telling_id: Mapped[uuid.UUID] = mapped_column(index=True)
    actor_id: Mapped[CreatedBy]
    created_at: Mapped[CreatedAt]
    request_hash: Mapped[str]
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB)
