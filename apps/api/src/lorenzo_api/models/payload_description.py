from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.payload import Payload


class PayloadDescription(Base):
    """Rich text content for a Payload, with a locale - see ADR 0017. "Rich
    text" is a content convention (e.g. markdown/HTML expected inside it),
    not a distinct Postgres type - content is plain text.
    """

    __tablename__ = "payload_description"

    payload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payload.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    locale: Mapped[str]
    content: Mapped[str]

    payload: Mapped[Payload] = relationship(lazy="raise_on_sql", back_populates="description")
