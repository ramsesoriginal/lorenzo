from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

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

    payload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payload.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    data: Mapped[bytes]
    filename: Mapped[str]
    file_type: Mapped[str]

    payload: Mapped[Payload] = relationship(lazy="raise_on_sql", back_populates="document")
