"""Independent lived-before support, anchored to two participations (ADR 0319)."""

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class LivedBefore(Base):
    __tablename__ = "lived_before"
    __table_args__ = (
        UniqueConstraint(
            "being_entity_id",
            "from_event_id",
            "to_event_id",
            "tenant_id",
            name="lived_before_tenant_key",
        ),
        same_tenant_fk(
            "lived_before_from_participation_fkey",
            ["from_event_id", "being_entity_id"],
            "event_participant",
            ["event_entity_id", "being_entity_id"],
            ondelete="NO ACTION",
        ),
        same_tenant_fk(
            "lived_before_to_participation_fkey",
            ["to_event_id", "being_entity_id"],
            "event_participant",
            ["event_entity_id", "being_entity_id"],
            ondelete="NO ACTION",
        ),
        CheckConstraint("from_event_id <> to_event_id", name="lived_before_distinct"),
    )
    being_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    from_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    to_event_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    is_shared: Mapped[bool] = mapped_column(server_default=text("false"))
