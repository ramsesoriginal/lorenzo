from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.payload import Payload


class PayloadDocument(Base):
    """Binary document content for a Payload - see ADR 0017. Same BYTEA
    reasoning as PayloadPicture. `file_type` added in ADR 0020 - "a
    content-type column is a natural addition when a serving endpoint
    actually needs one, not before" (ADR 0017), and the binary-content
    endpoint now needs one to set a correct Content-Type header rather
    than guessing from the filename extension.
    """

    __tablename__ = "payload_document"
    __table_args__ = (
        same_tenant_fk(
            "payload_document_payload_id_fkey", ["payload_id"], "payload", ondelete="CASCADE"
        ),
    )

    payload_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    data: Mapped[bytes]
    filename: Mapped[str]
    file_type: Mapped[str]

    payload: Mapped[Payload] = relationship(
        foreign_keys="PayloadDocument.payload_id", lazy="raise_on_sql", back_populates="document"
    )
