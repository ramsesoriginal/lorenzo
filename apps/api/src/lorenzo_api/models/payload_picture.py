import uuid

from sqlalchemy import ForeignKey, LargeBinary, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class PayloadPicture(Base):
    """Binary image content for a Payload - see ADR 0017. Bytes stored
    directly in Postgres (not external object storage) as a deliberate,
    revisitable simplification for this slice.
    """

    __tablename__ = "payload_picture"

    payload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payload.id"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )
    data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    file_type: Mapped[str] = mapped_column(Text, nullable=False)
