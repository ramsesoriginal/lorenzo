"""Structural contents and authored Chapter roles (ADR 0381)."""

import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class ManuscriptContents(Base):
    __tablename__ = "manuscript_contents"
    __table_args__ = (
        same_tenant_fk(
            "manuscript_contents_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB)
