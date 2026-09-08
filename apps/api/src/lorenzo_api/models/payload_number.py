from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.payload import Payload


class PayloadNumber(Base):
    """A single numeric value for a Payload - see ADR 0017. NUMERIC rather
    than FLOAT/INTEGER: nothing about "a number" payload says what it
    represents, so the type that doesn't silently lose precision wins.
    """

    __tablename__ = "payload_number"

    payload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payload.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    value: Mapped[Decimal]

    payload: Mapped[Payload] = relationship(back_populates="number")
