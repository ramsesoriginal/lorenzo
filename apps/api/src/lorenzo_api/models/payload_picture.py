from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.payload import Payload


class PayloadPicture(Base):
    """Binary image content for a Payload - see ADR 0017. Bytes stored
    directly in Postgres (not external object storage) as a deliberate,
    revisitable simplification for this slice.
    """

    __tablename__ = "payload_picture"

    payload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payload.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    data: Mapped[bytes]
    file_type: Mapped[str]

    payload: Mapped[Payload] = relationship(back_populates="picture")
