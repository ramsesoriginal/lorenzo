from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class RepositoryShowcase(Base):
    """An entry an Owner features in a repository's preview - ADR 0293, RFC 0038 section 5: what
    a visitor may look at before they copy, when the preview is `showcase`, in the order the Owner
    chose. A key to the repository's own entry, gone with it. A tenant table of the repository,
    read by the libraries and visitors that look at the preview through the gated read (ADR 0118),
    never copied.
    """

    __tablename__ = "repository_showcase"
    __table_args__ = (
        same_tenant_fk(
            "repository_showcase_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"
        ),
        CheckConstraint("position >= 0", name="repository_showcase_position"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    position: Mapped[int]
