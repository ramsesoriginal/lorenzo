import uuid

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class PayloadDescription(Base):
    """Rich text content for a Payload, with a locale - see ADR 0017. "Rich
    text" is a content convention (e.g. markdown/HTML expected inside it),
    not a distinct Postgres type - content is plain text.
    """

    __tablename__ = "payload_description"

    payload_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payload.id"), primary_key=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )
    locale: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
