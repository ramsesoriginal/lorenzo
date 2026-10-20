"""Local import provenance and retry receipts, never repository content (ADR 0311)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, UpdatedAt, same_tenant_fk


class CalendarImport(Base):
    __tablename__ = "calendar_import"
    __table_args__ = (
        same_tenant_fk(
            "calendar_import_calendar_fkey",
            ["calendar_entity_id"],
            "calendar",
            ["entity_id"],
            ondelete="CASCADE",
        ),
    )
    tenant_id: Mapped[TenantFk] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(primary_key=True)
    calendar_entity_id: Mapped[uuid.UUID]
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    bindings: Mapped[dict[str, Any]] = mapped_column(JSONB)
    last_token: Mapped[str | None]
    last_request_hash: Mapped[str | None]
    receipt: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[UpdatedAt]
