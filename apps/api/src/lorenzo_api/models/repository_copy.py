from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, same_tenant_fk

# tenant_id leads each primary key here, so it needs no index of its own
# (TenantFk would add one).


def _tenant_pk() -> Mapped[uuid.UUID]:
    return mapped_column(ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True)


class RepositoryCopy(Base):
    """That a tenant copied a repository, and when it last synced - ADR
    0119. Belongs to the copying tenant, and survives the grant being
    removed (RFC 0024 §6). `repository_tenant_id` is a plain id, not a
    foreign key: the repository is another tenant's, and may go."""

    __tablename__ = "repository_copy"

    tenant_id: Mapped[uuid.UUID] = _tenant_pk()
    repository_tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    copied_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    copied_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    synced_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


class _CopyLink:
    """Shared columns of the three copy-link tables (ADR 0119): where a
    copied row came from, and a snapshot of what was copied, with every id
    translated to its origin (ADR 0121 diffs against it). `source_id` is
    always an origin - a row that is its own repository's, never a copy of
    a copy (RFC 0024 amendment A8)."""

    tenant_id: Mapped[uuid.UUID] = _tenant_pk()
    source_tenant_id: Mapped[uuid.UUID]
    source_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    copied_at: Mapped[datetime] = mapped_column(server_default=text("now()"))


# The local id is null once the local row is deleted: the database's key is
# ON DELETE SET NULL (<local id>) (see the migration), SQLAlchemy only
# accepts the plain keyword - it matters only for DDL, which migrations own.


class RepositoryCopyLinkEntity(_CopyLink, Base):
    __tablename__ = "repository_copy_link_entity"
    __table_args__ = (
        Index("ix_repository_copy_link_entity_source_tenant_id", "tenant_id", "source_tenant_id"),
        same_tenant_fk(
            "repository_copy_link_entity_entity_id_fkey",
            ["entity_id"],
            "entity",
            ondelete="SET NULL",
        ),
    )

    entity_id: Mapped[uuid.UUID | None] = mapped_column(index=True)


class RepositoryCopyLinkStatGroup(_CopyLink, Base):
    """`mode` is `merged` when a collision was resolved by merging into the
    tenant's own group: that group is still the tenant's own, and is never
    offered for update (ADR 0121)."""

    __tablename__ = "repository_copy_link_stat_group"
    __table_args__ = (
        Index(
            "ix_repository_copy_link_stat_group_source_tenant_id", "tenant_id", "source_tenant_id"
        ),
        same_tenant_fk(
            "repository_copy_link_stat_group_stat_group_id_fkey",
            ["stat_group_id"],
            "stat_group",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "mode IN ('copied', 'merged')", name="repository_copy_link_stat_group_mode"
        ),
    )

    stat_group_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    mode: Mapped[str]


class RepositoryCopyLinkStatDefinition(_CopyLink, Base):
    """As RepositoryCopyLinkStatGroup, for a definition."""

    __tablename__ = "repository_copy_link_stat_definition"
    __table_args__ = (
        Index(
            "ix_repository_copy_link_stat_definition_source_tenant_id",
            "tenant_id",
            "source_tenant_id",
        ),
        same_tenant_fk(
            "repository_copy_link_stat_definition_stat_definition_id_fkey",
            ["stat_definition_id"],
            "stat_definition",
            ondelete="SET NULL",
        ),
        CheckConstraint(
            "mode IN ('copied', 'merged')", name="repository_copy_link_stat_definition_mode"
        ),
    )

    stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    mode: Mapped[str]
