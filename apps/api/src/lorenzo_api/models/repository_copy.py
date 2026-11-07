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
    __table_args__ = (
        CheckConstraint(
            "inclusion IN ('show', 'include', 'hide')", name="repository_copy_inclusion"
        ),
    )

    tenant_id: Mapped[uuid.UUID] = _tenant_pk()
    repository_tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    # The repository's name at copy time, refreshed on sync (ADR 0119).
    repository_name: Mapped[str] = mapped_column(server_default=text("''"))
    copied_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    copied_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("app_user.id", ondelete="SET NULL"), index=True
    )
    synced_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
    # The repository's release that was its latest when this tenant last copied or
    # applied updates (ADR 0207): a plain id, like `repository_tenant_id`, since the
    # release is the repository's row. Null for a copy made before there was a ledger.
    synced_release_id: Mapped[uuid.UUID | None]
    # How this repository carries the one it copied when a release of it is made (ADR 0431,
    # RFC 0051): `show` leaves it a repository of its own that libraries are given beside this
    # one, `include` makes its rows this repository's own in the release document. Only a
    # repository has a use for it; a library's is always `show`.
    inclusion: Mapped[str] = mapped_column(server_default=text("'show'"))
    # What this record's repository brings separate into the tenant, as the release the tenant last
    # took says it (ADR 0437): `{<source id>: "show" | "hide"}`, and the repository's own id as
    # `show` where the tenant copied it for itself. A library's hidden rows are derived from every
    # record's (`repository_hiding.refresh_hidden`), so the derivation reads no other repository.
    carries: Mapped[dict[str, str]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))


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
    # Whether the library hides this entry (ADR 0437): true while every repository the library
    # holds that brings the row's repository hides it. Derived by `repository_hiding`, never set
    # by a request; read by the gate every read of an entry applies, for everyone.
    hidden: Mapped[bool] = mapped_column(server_default=text("false"))


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


class RepositoryCopyLinkAttachment(Base):
    """A parent a repository added to one of its copies, that a tenant took with
    its copy of the repository - ADR 0172. The pair is origin ids, plain ids with no
    key to a row: they are other tenants' rows, and may go. One row is kept for each
    attachment the tenant took, whether the copy wrote the edge or it was already
    there; copy bookkeeping, so not part of what a repository holds."""

    __tablename__ = "repository_copy_link_attachment"

    tenant_id: Mapped[uuid.UUID] = _tenant_pk()
    source_tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    child_source_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    parent_source_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    copied_at: Mapped[datetime] = mapped_column(server_default=text("now()"))
