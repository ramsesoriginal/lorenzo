from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class RepositoryReleaseBlob(Base):
    """The bytes of a picture or a document a release document refers to - ADR 0214. Keyed by
    the SHA-256 of the bytes, once for each repository, however many releases and payloads use
    them; the file type and the name stay with the payload in the document. Immutable (a
    trigger refuses an update); a tenant table of the repository, readable by the libraries it
    is granted to through the gated read (ADR 0118).
    """

    __tablename__ = "repository_release_blob"

    # tenant_id leads the primary key, so it needs no index of its own.
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenant.id", ondelete="CASCADE"), primary_key=True
    )
    sha256: Mapped[str] = mapped_column(primary_key=True)
    data: Mapped[bytes]
