from __future__ import annotations

from typing import Any

from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UuidPk


class RepositoryRelease(Base):
    """What one publish of a repository was - ADR 0207, RFC 0037 §1. A tenant
    table of the repository: its members write it, and the tenants granted the
    repository read it through the gated read (ADR 0118), so it carries
    `repository_read` as well as `tenant_isolation`.

    `number` is the server's (1, 2, 3 within the repository), `label` the
    author's words, never parsed as a version, unique within the repository
    whatever its case. `breaking` is the author's statement. Nothing has a
    foreign key to a release: a copy records the one it last took as a plain id,
    like the repository it came from (`repository_copy.synced_release_id`).
    """

    __tablename__ = "repository_release"
    __table_args__ = (
        UniqueConstraint("id", "tenant_id", name="uq_repository_release_id_tenant_id"),
        UniqueConstraint("tenant_id", "number", name="uq_repository_release_number"),
        Index("uq_repository_release_label", "tenant_id", text("lower(label)"), unique=True),
        CheckConstraint("number > 0", name="repository_release_number"),
        CheckConstraint("char_length(label) BETWEEN 1 AND 80", name="repository_release_label"),
        CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 4000", name="repository_release_notes"
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    number: Mapped[int]
    label: Mapped[str]
    notes: Mapped[str | None]
    breaking: Mapped[bool] = mapped_column(server_default="false")
    created_by: Mapped[CreatedBy]
    created_at: Mapped[CreatedAt]
    # ADR 0208: the hash over the rows it released, what it added, changed and removed, and
    # the rows a publish acknowledged as breaking. Null for a release made before digests.
    digest: Mapped[str | None]
    counts: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    breaking_rows: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
