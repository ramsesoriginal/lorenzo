from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk, same_tenant_fk


class System(Base):
    """A game system a library holds the vocabulary of - ADR 0448, RFC 0052. A thing, not a
    convention: stat groups carry one (`stat_group.system_id`), and a definition of such a group
    starts with the system's slug and an underscore, so two systems cannot collide on a name.
    Neutral content has no system, and a library has none until someone makes one.

    The slug is a short lowercase word that does not change once a stat group uses it; the name
    may be edited. The root entry is the system root of ADR 0181, optional.
    """

    __tablename__ = "system"
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint("id", "tenant_id", name="system_id_tenant_id_key"),
        UniqueConstraint("tenant_id", "slug", name="system_tenant_id_slug_key"),
        # The database's key is SET NULL (root_entry_id), so deleting an entry never tries to null
        # tenant_id too (ADR 0117). SQLAlchemy only accepts the plain keyword; it only matters for
        # DDL, which migrations own.
        same_tenant_fk(
            "system_root_entry_id_fkey", ["root_entry_id"], "entity", ondelete="SET NULL"
        ),
        CheckConstraint("slug ~ '^[a-z][a-z0-9]{0,31}$'", name="system_slug_is_a_short_word"),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    slug: Mapped[str]
    name: Mapped[str]
    root_entry_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
