from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class EntitySlug(Base):
    """An entity's one slug, the name LorenzoScript text links it by
    (`[text](ashfang)`, `[[Ashfang]]`) - see ADR 0107. Unique per tenant;
    an entity without a slug simply has no row, so a plain unique
    constraint suffices where ADR 0043's nullable item_instance.slug needed
    a partial index. That column's values moved here in the same migration.
    """

    __tablename__ = "entity_slug"
    __table_args__ = (
        same_tenant_fk("entity_slug_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        UniqueConstraint("tenant_id", "slug"),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    slug: Mapped[str]

    entity: Mapped[Entity] = relationship(
        foreign_keys="EntitySlug.entity_id", lazy="raise_on_sql", back_populates="slug"
    )
