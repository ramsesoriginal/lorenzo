from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class Item(Base):
    """A base item type ("Shovel," "Tool") - see ADR 0019 and RFC 0001. A
    bare marker: no columns beyond identity, since everything else about it
    (stats, information) already exists through the generic mechanisms.
    """

    __tablename__ = "item"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]

    entity: Mapped[Entity] = relationship(lazy="raise_on_sql", back_populates="item")
