from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class Item(Base):
    """A base item type ("Shovel," "Tool") - see ADR 0019 and RFC 0001.
    Nearly a bare marker, since everything else about it (stats,
    information) already exists through the generic mechanisms. Its one
    column of its own is in_public_catalog (ADR 0116): whether players, not
    just tenant members, may list it.
    """

    __tablename__ = "item"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    in_public_catalog: Mapped[bool] = mapped_column(server_default=false(), default=False)

    entity: Mapped[Entity] = relationship(lazy="raise_on_sql", back_populates="item")
