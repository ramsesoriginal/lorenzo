from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class ItemInstance(Base):
    """A specific, ownable item ("My Shovel") - see ADR 0019 and RFC 0001.
    Its entity is expected to have at least one direct entity_prototype row
    pointing at an item-typed entity - not enforced anywhere, the same kind
    of accepted limitation as entity_stat_group's tenant agreement
    (ADR 0014).

    Ownership itself lives in the generic `ownership` table (ADR 0025),
    not here - `owner_entity_id` was this table's own column until a
    character existed to actually own things (RFC 0002); the migration
    that added `being` backfilled `ownership` from it and dropped the
    column. `v_item_instance` still exposes `owner_entity_id` for REST
    consumers, now derived via a join against `ownership` instead.
    """

    __tablename__ = "item_instance"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]

    entity: Mapped[Entity] = relationship(back_populates="item_instance")
