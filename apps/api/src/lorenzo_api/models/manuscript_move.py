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
