import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class PayloadNumber(Base):
    """A single numeric value for a Payload - see ADR 0017. NUMERIC rather
    than FLOAT/INTEGER: nothing about "a number" payload says what it
    represents, so the type that doesn't silently lose precision wins.
    """

    __tablename__ = "payload_number"

    payload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payload.id"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )
    value: Mapped[Decimal] = mapped_column(Numeric, nullable=False)
