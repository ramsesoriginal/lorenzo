"""Relationship through: the relationships another one is stated to hold through (ADR 0402)."""

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class RelationshipThrough(Base):
    """One step of an authored chain: `relationship_entity_id` holds through `via_entity_id`,
    in `step` order. Nothing derives a value, a direction or a type from it, and nothing checks
    that the steps join the ends. The chain is acyclic (checked by the write under a lock)."""

    __tablename__ = "relationship_through"
    __table_args__ = (
        UniqueConstraint(
            "relationship_entity_id", "via_entity_id", name="relationship_through_via_key"
        ),
        CheckConstraint(
            "relationship_entity_id <> via_entity_id", name="relationship_through_not_self"
        ),
        same_tenant_fk(
            "relationship_through_relationship_fkey",
            ["relationship_entity_id"],
            "relationship",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "relationship_through_via_fkey",
            ["via_entity_id"],
            "relationship",
            ["entity_id"],
            ondelete="CASCADE",
        ),
    )
    relationship_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    step: Mapped[int] = mapped_column(primary_key=True)
    via_entity_id: Mapped[uuid.UUID]
    tenant_id: Mapped[TenantFk]
