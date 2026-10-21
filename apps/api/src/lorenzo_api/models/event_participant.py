"""An Event's participating beings, without dates, order or learning (ADR 0313)."""

import uuid

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


def participant_fk(name: str, column: str, table: str) -> ForeignKeyConstraint:
    key = same_tenant_fk(name, [column], table, ["entity_id"], ondelete="NO ACTION")
    key.deferrable = True
    key.initially = "DEFERRED"
    return key


class EventParticipant(Base):
    __tablename__ = "event_participant"
    __table_args__ = (
        UniqueConstraint(
            "event_entity_id", "being_entity_id", "tenant_id", name="event_participant_tenant_key"
        ),
        participant_fk("event_participant_event_fkey", "event_entity_id", "story_event"),
        participant_fk("event_participant_being_fkey", "being_entity_id", "being"),
    )
    event_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    being_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
