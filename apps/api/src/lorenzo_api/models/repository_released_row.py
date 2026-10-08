from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Index, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, UuidPk


class RepositoryReleasedRow(Base):
    """What one row the update engine compares was at the repository's last publish -
    ADR 0208, RFC 0037 §2: the SHA-256 of its snapshot (`hash`), and the few facts the
    breaking-change detector and a change list need (`name`, `facts`). One set for each
    repository, replaced at every publish, not one per release; a release's identity
    survives in `repository_release.digest`.

    `kind` is `entity`, `stat_group`, `stat_definition` or `attachment`. `row_id` is the
    row's origin id, the id a library's copy link holds; for an attachment it is the child's,
    and `parent_id` the parent's, null for every other kind. A tenant table of the
    repository, readable by the libraries it is granted to through the gated read (ADR 0118):
    a library marks its updates against these hashes.
    """

    __tablename__ = "repository_released_row"
    __table_args__ = (
        Index(
            "uq_repository_released_row_key",
            "tenant_id",
            "kind",
            "row_id",
            text("COALESCE(parent_id, '00000000-0000-0000-0000-000000000000')"),
            unique=True,
        ),
        CheckConstraint(
            "kind IN ('entity', 'stat_group', 'stat_definition', 'attachment')",
            name="repository_released_row_kind",
        ),
        CheckConstraint(
            "(kind = 'attachment') = (parent_id IS NOT NULL)",
            name="repository_released_row_parent",
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    kind: Mapped[str]
    row_id: Mapped[uuid.UUID]
    parent_id: Mapped[uuid.UUID | None]
    hash: Mapped[str]
    name: Mapped[str]
    facts: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
