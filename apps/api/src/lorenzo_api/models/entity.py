from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.containment import Containment
    from lorenzo_api.models.entity_prototype import EntityPrototype
    from lorenzo_api.models.entity_stat import EntityStat
    from lorenzo_api.models.entity_stat_group import EntityStatGroup
    from lorenzo_api.models.information import Information
    from lorenzo_api.models.tenant import Tenant


class Entity(Base):
    """The universal domain table - see ADR 0012 and RFC 0001."""

    __tablename__ = "entity"

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    name: Mapped[str]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    tenant: Mapped[Tenant] = relationship(back_populates="entities")
    stats: Mapped[list[EntityStat]] = relationship(
        back_populates="entity", cascade="all, delete-orphan", passive_deletes=True
    )
    stat_group_links: Mapped[list[EntityStatGroup]] = relationship(
        back_populates="entity", cascade="all, delete-orphan", passive_deletes=True
    )
    information: Mapped[list[Information]] = relationship(
        back_populates="entity", cascade="all, delete-orphan", passive_deletes=True
    )

    # entity_prototype: ADR 0015's self-referential inheritance graph has two
    # independent FKs to this table, so each direction needs its own
    # disambiguated relationship() (foreign_keys=) - see ADR 0018.
    prototype_links: Mapped[list[EntityPrototype]] = relationship(
        foreign_keys="EntityPrototype.entity_id",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    dependent_links: Mapped[list[EntityPrototype]] = relationship(
        foreign_keys="EntityPrototype.prototype_id",
        back_populates="prototype",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # containment: ADR 0016's self-referential physical relation, same
    # two-FK disambiguation as above. child_entity_id is that table's PK
    # (at most one container per entity), so this side is scalar.
    containment: Mapped[Containment | None] = relationship(
        foreign_keys="Containment.child_entity_id",
        back_populates="child",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    contained_links: Mapped[list[Containment]] = relationship(
        foreign_keys="Containment.parent_entity_id",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
