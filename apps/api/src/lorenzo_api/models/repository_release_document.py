from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, TenantFk, same_tenant_fk


class RepositoryReleaseDocument(Base):
    """A release's content as it was - ADR 0214, RFC 0037 §4: the repository's `Content`
    serialised (`release_document.py`), gzipped JSON, one document for each release. `format`
    is the version of the format it was written in, which says which reader reads it.
    `blobs` lists, sorted, the SHA-256 of every file the document refers to
    (`repository_release_blob`), so that retention can ask which files a retained document
    keeps without opening it.

    Immutable: a trigger refuses an update, for every role; a delete is allowed, since it goes
    when its release does and with its repository. A tenant table of the repository, readable
    by the libraries it is granted to through the gated read (ADR 0118).
    """

    __tablename__ = "repository_release_document"
    __table_args__ = (
        same_tenant_fk(
            "repository_release_document_release_id_fkey",
            ["release_id"],
            "repository_release",
            ondelete="CASCADE",
        ),
        CheckConstraint("format > 0", name="repository_release_document_format"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    format: Mapped[int]
    content: Mapped[bytes]
    blobs: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    created_at: Mapped[CreatedAt]
