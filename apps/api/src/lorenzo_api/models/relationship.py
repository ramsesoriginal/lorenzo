"""Relationships: an entry that ties two entries (ADR 0399)."""

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class Relationship(Base):
    """The marker that makes an entry a relationship. `one_way` is null for a tie that goes both
    ways and true for one that goes from `end_a` to `end_b`. Deleting an end removes the marker and
    leaves the entry; nothing here is read as a route, a link, part-of, containment, placement,
    access or reach. An end is never itself a relationship (the visibility rule would recurse)."""

    __tablename__ = "relationship"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="relationship_entity_tenant_key"),
        CheckConstraint("end_a <> end_b", name="relationship_ends_differ"),
        CheckConstraint("one_way IS NOT FALSE", name="relationship_one_way_true"),
        same_tenant_fk("relationship_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk("relationship_end_a_fkey", ["end_a"], "entity", ondelete="CASCADE"),
        same_tenant_fk("relationship_end_b_fkey", ["end_b"], "entity", ondelete="CASCADE"),
        # ADR 0405: the Events that bound it in time. The database's key clears only the column
        # (ON DELETE SET NULL (starts_at)); see the migration.
        CheckConstraint(
            "starts_at IS NULL OR ends_at IS NULL OR starts_at <> ends_at",
            name="relationship_limits_differ",
        ),
        same_tenant_fk(
            "relationship_starts_at_fkey",
            ["starts_at"],
            "story_event",
            ["entity_id"],
            ondelete="SET NULL",
        ),
        same_tenant_fk(
            "relationship_ends_at_fkey",
            ["ends_at"],
            "story_event",
            ["entity_id"],
            ondelete="SET NULL",
        ),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    end_a: Mapped[uuid.UUID]
    end_b: Mapped[uuid.UUID]
    one_way: Mapped[bool | None] = mapped_column(default=None)
    # Optional limits in time, as Events (ADR 0405); neither sets an order.
    starts_at: Mapped[uuid.UUID | None] = mapped_column(default=None)
    ends_at: Mapped[uuid.UUID | None] = mapped_column(default=None)
