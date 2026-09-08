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
    reasoning as PayloadPicture.
    """

    __tablename__ = "payload_document"

    payload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payload.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    data: Mapped[bytes]
    filename: Mapped[str]

    payload: Mapped[Payload] = relationship(back_populates="document")
