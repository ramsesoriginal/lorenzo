from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import FetchedValue, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UpdatedAt, UuidPk
from lorenzo_api.models.information_type import SINGLETON_INFORMATION_TYPES

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.knowledge import Knowledge
    from lorenzo_api.models.payload import Payload


class Information(Base):
    """A titled, categorized piece of information about an entity - see
    ADR 0017 and RFC 0001. The actual content lives in one or more Payload
    rows attached to this one.
    """

    __tablename__ = "information"
    # ADR 0101: only the singleton types (information_type.is_singleton)
    # are one per entity; every other type repeats.
    __table_args__ = (
        Index(
            "information_singleton_type",
            "entity_id",
            "type",
            unique=True,
            postgresql_where=text(
                "type IN (" + ", ".join(f"'{t}'" for t in SINGLETON_INFORMATION_TYPES) + ")"
            ),
        ),
        UniqueConstraint("entity_id", "order", name="information_entity_order"),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str]
    type: Mapped[str]
    # False by default - GM-only is the default, not a separate flag
    # (RFC 0001). True bypasses the knower lookup entirely: "known to
    # everyone" doesn't need any Knowledge rows at all - see ADR 0028.
    is_public: Mapped[bool] = mapped_column(server_default=text("false"))
    # Position among this entity's information rows (ADR 0101) - unique,
    # not dense: a delete leaves a gap and nothing renumbers.
    # Left unset on insert, a BEFORE INSERT trigger appends it after the
    # last sibling (ADR 0101); FetchedValue makes the ORM read it back.
    order: Mapped[int] = mapped_column(server_default=FetchedValue())
    # Who authored the row (ADR 0101, completing ADR 0029's deferral): the
    # author may edit a restricted row even without a knower grant.
    created_by: Mapped[CreatedBy]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    entity: Mapped[Entity] = relationship(lazy="raise_on_sql", back_populates="information")
    payloads: Mapped[list[Payload]] = relationship(
        lazy="raise_on_sql",
        order_by="Payload.order",
        back_populates="information",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    knowledge_links: Mapped[list[Knowledge]] = relationship(
        lazy="raise_on_sql",
        back_populates="information",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
