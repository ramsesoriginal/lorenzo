from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.payload import Payload


class PayloadNumber(Base):
    """A single numeric value for a Payload - see ADR 0017. NUMERIC rather
    than FLOAT/INTEGER: nothing about "a number" payload says what it
    represents, so the type that doesn't silently lose precision wins.
    """

    __tablename__ = "payload_number"
    __table_args__ = (
        same_tenant_fk(
            "payload_number_payload_id_fkey", ["payload_id"], "payload", ondelete="CASCADE"
        ),
    )

    payload_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    value: Mapped[Decimal]

    payload: Mapped[Payload] = relationship(
        foreign_keys="PayloadNumber.payload_id", lazy="raise_on_sql", back_populates="number"
    )
