"""Explicit Event assertions; the order is derived, never stored here (ADR 0312)."""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


def event_fk(name: str, column: str) -> ForeignKeyConstraint:
    key = same_tenant_fk(name, [column], "story_event", ["entity_id"], ondelete="NO ACTION")
    key.deferrable = True
    key.initially = "DEFERRED"
    return key


class EventRelationship(Base):
    __tablename__ = "event_relationship"
    __table_args__ = (
        CheckConstraint("from_event_id <> to_event_id", name="event_relationship_distinct"),
        CheckConstraint("kind IN ('order','causes')", name="event_relationship_kind"),
        event_fk("event_relationship_from_fkey", "from_event_id"),
        event_fk("event_relationship_to_fkey", "to_event_id"),
    )
    from_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    to_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))
