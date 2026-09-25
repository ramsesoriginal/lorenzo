from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, TenantFk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.stat_group import StatGroup


class EntityStatGroup(Base):
    """Which stat groups an entity/prototype has acquired - the n:m join
    between entity and stat_group. See ADR 0014 and RFC 0001.
    """

    __tablename__ = "entity_stat_group"
    __table_args__ = (
        same_tenant_fk(
            "entity_stat_group_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"
        ),
        same_tenant_fk(
            "entity_stat_group_stat_group_id_fkey",
            ["stat_group_id"],
            "stat_group",
            ondelete="CASCADE",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_group_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]

    entity: Mapped[Entity] = relationship(
        foreign_keys="EntityStatGroup.entity_id",
        lazy="raise_on_sql",
        back_populates="stat_group_links",
    )
    stat_group: Mapped[StatGroup] = relationship(
        foreign_keys="EntityStatGroup.stat_group_id",
        lazy="raise_on_sql",
        back_populates="entity_links",
    )
