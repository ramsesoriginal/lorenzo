"""Private recovery history, never repository content (ADR 0328)."""

import uuid
from typing import Any

from sqlalchemy import BigInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, CreatedAt, TenantFk, UuidPk, same_tenant_fk


class ManuscriptRevision(Base):
    __tablename__ = "manuscript_revision"
    __table_args__ = (
        same_tenant_fk(
            "manuscript_revision_information_fkey",
            ["information_id"],
            "information",
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "information_id", "transaction_id", name="manuscript_revision_transaction_key"
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    information_id: Mapped[uuid.UUID] = mapped_column(index=True)
    transaction_id: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[CreatedAt]
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
