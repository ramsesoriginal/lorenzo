from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.payload import Payload


class PayloadPicture(Base):
    """Binary image content for a Payload - see ADR 0017. Bytes stored
    directly in Postgres (not external object storage) as a deliberate,
    revisitable simplification for this slice.
    """

    __tablename__ = "payload_picture"
    __table_args__ = (
        same_tenant_fk(
            "payload_picture_payload_id_fkey", ["payload_id"], "payload", ondelete="CASCADE"
        ),
    )

    payload_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    data: Mapped[bytes]
    file_type: Mapped[str]

    payload: Mapped[Payload] = relationship(
        foreign_keys="PayloadPicture.payload_id", lazy="raise_on_sql", back_populates="picture"
    )
