"""Connections: an entry that joins two entries (ADR 0363)."""

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class Connection(Base):
    """The marker that makes an entry a connection. `one_way` is null for a way that goes both
    ways and true for one that goes from `end_a` to `end_b`. Deleting an end removes the marker and
    leaves the entry; nothing here is read as part-of, containment, placement or reach."""

    __tablename__ = "connection"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="connection_entity_tenant_key"),
        CheckConstraint("end_a <> end_b", name="connection_ends_differ"),
        CheckConstraint("one_way IS NOT FALSE", name="connection_one_way_true"),
        same_tenant_fk("connection_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk("connection_end_a_fkey", ["end_a"], "entity", ondelete="CASCADE"),
        same_tenant_fk("connection_end_b_fkey", ["end_b"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    end_a: Mapped[uuid.UUID]
    end_b: Mapped[uuid.UUID]
    one_way: Mapped[bool | None] = mapped_column(default=None)
