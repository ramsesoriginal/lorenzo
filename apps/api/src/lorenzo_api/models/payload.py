from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import FetchedValue, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk, same_tenant_fk

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
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint("id", "tenant_id", name="payload_id_tenant_id_key"),
        same_tenant_fk(
            "payload_information_id_fkey", ["information_id"], "information", ondelete="CASCADE"
        ),
        UniqueConstraint("information_id", "order", name="payload_information_order"),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    information_id: Mapped[uuid.UUID] = mapped_column(index=True)
    # Position within its Information bundle (ADR 0101) - unique, not dense.
    # Left unset on insert, a BEFORE INSERT trigger appends it after the
    # last sibling (ADR 0101); FetchedValue makes the ORM read it back.
    order: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    information: Mapped[Information] = relationship(
        foreign_keys="Payload.information_id", lazy="raise_on_sql", back_populates="payloads"
    )

    description: Mapped[PayloadDescription | None] = relationship(
        foreign_keys="PayloadDescription.payload_id",
        lazy="raise_on_sql",
        back_populates="payload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    number: Mapped[PayloadNumber | None] = relationship(
        foreign_keys="PayloadNumber.payload_id",
        lazy="raise_on_sql",
        back_populates="payload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    picture: Mapped[PayloadPicture | None] = relationship(
        foreign_keys="PayloadPicture.payload_id",
        lazy="raise_on_sql",
        back_populates="payload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    document: Mapped[PayloadDocument | None] = relationship(
        foreign_keys="PayloadDocument.payload_id",
        lazy="raise_on_sql",
        back_populates="payload",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
