from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.information import Information
    from lorenzo_api.models.payload_description import PayloadDescription
    from lorenzo_api.models.payload_document import PayloadDocument
    from lorenzo_api.models.payload_number import PayloadNumber
    from lorenzo_api.models.payload_picture import PayloadPicture


class Payload(Base):
    """One piece of content attached to an Information bundle - see ADR 0017
    and RFC 0001. No kind column, matching Entity's own class-table-
    inheritance pattern: which concrete table (PayloadDescription,
    PayloadNumber, PayloadPicture, PayloadDocument) has a matching row is
    what tells you the kind.
    """

    __tablename__ = "payload"

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    information_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("information.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    information: Mapped[Information] = relationship(lazy="raise_on_sql", back_populates="payloads")

    description: Mapped[PayloadDescription | None] = relationship(
        lazy="raise_on_sql",
        back_populates="payload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    number: Mapped[PayloadNumber | None] = relationship(
        lazy="raise_on_sql",
        back_populates="payload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    picture: Mapped[PayloadPicture | None] = relationship(
        lazy="raise_on_sql",
        back_populates="payload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    document: Mapped[PayloadDocument | None] = relationship(
        lazy="raise_on_sql",
        back_populates="payload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
