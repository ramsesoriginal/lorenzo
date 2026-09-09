from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

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
    __table_args__ = (UniqueConstraint("entity_id", "type"),)

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
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    entity: Mapped[Entity] = relationship(lazy="raise_on_sql", back_populates="information")
    payloads: Mapped[list[Payload]] = relationship(
        lazy="raise_on_sql",
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
