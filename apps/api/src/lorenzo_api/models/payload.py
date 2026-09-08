import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, text
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base


class Payload(Base):
    """One piece of content attached to an Information bundle - see ADR 0017
    and RFC 0001. No kind column, matching Entity's own class-table-
    inheritance pattern: which concrete table (PayloadDescription,
    PayloadNumber, PayloadPicture, PayloadDocument) has a matching row is
    what tells you the kind.
    """

    __tablename__ = "payload"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant.id"), nullable=False, index=True
    )
    information_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("information.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=text("now()"),
        onupdate=text("now()"),
        nullable=False,
    )
