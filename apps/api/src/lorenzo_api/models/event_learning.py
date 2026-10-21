"""Explicit learning provenance, independent of audience grants (ADR 0314)."""

import uuid

from sqlalchemy import ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


def learning_fk(
    name: str, columns: list[str], table: str, targets: list[str]
) -> ForeignKeyConstraint:
    key = same_tenant_fk(name, columns, table, targets, ondelete="NO ACTION")
    key.deferrable = True
    key.initially = "DEFERRED"
    return key


class EventLearning(Base):
    __tablename__ = "event_learning"
    __table_args__ = (
        learning_fk(
            "event_learning_participant_fkey",
            ["event_entity_id", "being_entity_id"],
            "event_participant",
            ["event_entity_id", "being_entity_id"],
        ),
        learning_fk("event_learning_information_fkey", ["information_id"], "information", ["id"]),
        UniqueConstraint("event_entity_id", "being_entity_id", "information_id", "tenant_id"),
    )
    event_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    being_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    information_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
