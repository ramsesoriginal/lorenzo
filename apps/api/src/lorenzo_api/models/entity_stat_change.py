"""A being's recent stat changes: who set what, from which value to which (ADR 0525)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedBy, TenantFk, UuidPk, same_tenant_fk


class EntityStatChange(Base):
    """One step of an entry's own stat value, kept for a short while for the History of a
    being's sheet (BN9). Bounded: only the latest `KEEP` per entry survive a write. Not part of
    the activity log (ADR 0084): this is for the table, and it reads only what the reader may see.

    `old_value` is null when the entry had no own value before; `new_value` is null when the
    value was removed. A bool, a number or a text is stored as the JSON of itself.
    """

    __tablename__ = "entity_stat_change"
    __table_args__ = (
        same_tenant_fk(
            "entity_stat_change_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "entity_stat_change_stat_definition_fkey",
            ["stat_definition_id"],
            "stat_definition",
            ondelete="CASCADE",
        ),
    )

    KEEP = 100

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    entity_id: Mapped[uuid.UUID] = mapped_column(index=True)
    stat_definition_id: Mapped[uuid.UUID]
    old_value: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    new_value: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    actor_id: Mapped[CreatedBy]
    created_at: Mapped[datetime] = mapped_column(server_default=text("clock_timestamp()"))
