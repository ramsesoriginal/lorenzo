from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship

from lorenzo_api.db import Base, CreatedAt, CreatedBy, TenantFk, UpdatedAt, UpdatedBy, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.being import Being
    from lorenzo_api.models.containment import Containment
    from lorenzo_api.models.entity_prototype import EntityPrototype
    from lorenzo_api.models.entity_stat import EntityStat
    from lorenzo_api.models.entity_stat_group import EntityStatGroup
    from lorenzo_api.models.group_member import GroupMember
    from lorenzo_api.models.information import Information
    from lorenzo_api.models.item import Item
    from lorenzo_api.models.item_instance import ItemInstance
    from lorenzo_api.models.knowledge import Knowledge
    from lorenzo_api.models.ownership import Ownership
    from lorenzo_api.models.stat_group import StatGroup
    from lorenzo_api.models.tenant import Tenant


class Entity(Base):
    """The universal domain table - see ADR 0012 and RFC 0001."""

    __tablename__ = "entity"

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    name: Mapped[str]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]
    # Bare user ids only (ADR 0029) - covers item/item_instance/being for
    # free, since none of the three ever exists independently of the entity
    # row created alongside it. No relationship() to User: nothing needs to
    # navigate this as an object today (every consumer this RFC names wants
    # a bare id back over REST), and adding one would just be another
    # lazy="raise_on_sql" trap for every existing eager-load chain to forget.
    created_by: Mapped[CreatedBy]
    updated_by: Mapped[UpdatedBy]

    tenant: Mapped[Tenant] = relationship(lazy="raise_on_sql", back_populates="entities")
    stats: Mapped[list[EntityStat]] = relationship(
        lazy="raise_on_sql",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    stat_group_links: Mapped[list[EntityStatGroup]] = relationship(
        lazy="raise_on_sql",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    information: Mapped[list[Information]] = relationship(
        lazy="raise_on_sql",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    item: Mapped[Item | None] = relationship(
        lazy="raise_on_sql",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    item_instance: Mapped[ItemInstance | None] = relationship(
        lazy="raise_on_sql",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    being: Mapped[Being | None] = relationship(
        lazy="raise_on_sql",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # ownership: ADR 0025's generic ownership table has two independent FKs
    # to this table (owned_entity_id and owner_character_id), same
    # disambiguation shape as entity_prototype/containment below.
    # owned_entity_id is that table's PK (at most one owner per entity), so
    # this side is scalar; owner_character_id is not unique, so the reverse
    # is a list.
    ownership: Mapped[Ownership | None] = relationship(
        lazy="raise_on_sql",
        foreign_keys="Ownership.owned_entity_id",
        back_populates="owned_entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    owned_entity_links: Mapped[list[Ownership]] = relationship(
        lazy="raise_on_sql",
        foreign_keys="Ownership.owner_character_id",
        back_populates="owner_character",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # entity_prototype: ADR 0015's self-referential inheritance graph has two
    # independent FKs to this table, so each direction needs its own
    # disambiguated relationship() (foreign_keys=) - see ADR 0018.
    prototype_links: Mapped[list[EntityPrototype]] = relationship(
        lazy="raise_on_sql",
        foreign_keys="EntityPrototype.entity_id",
        back_populates="entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    dependent_links: Mapped[list[EntityPrototype]] = relationship(
        lazy="raise_on_sql",
        foreign_keys="EntityPrototype.prototype_id",
        back_populates="prototype",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # containment: ADR 0016's self-referential physical relation, same
    # two-FK disambiguation as above. child_entity_id is that table's PK
    # (at most one container per entity), so this side is scalar.
    containment: Mapped[Containment | None] = relationship(
        lazy="raise_on_sql",
        foreign_keys="Containment.child_entity_id",
        back_populates="child",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    contained_links: Mapped[list[Containment]] = relationship(
        lazy="raise_on_sql",
        foreign_keys="Containment.parent_entity_id",
        back_populates="parent",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # group_member: this entity, used as a group knower (RFC 0001/ADR 0028)
    # - membership rows naming it as the group side.
    group_member_links: Mapped[list[GroupMember]] = relationship(
        lazy="raise_on_sql",
        back_populates="group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # knowledge: this entity acting as a knower (a character or a group -
    # see ADR 0028), not information *about* this entity (that's the
    # `information` relationship above).
    knowledge_links: Mapped[list[Knowledge]] = relationship(
        lazy="raise_on_sql",
        back_populates="knower_entity",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Read-only convenience accessors onto the *other side* of each join
    # above, skipping the association object (e.g. entity.stat_groups
    # instead of [l.stat_group for l in entity.stat_group_links]). viewonly
    # is load-bearing, not decorative: mixing an association-object mapping
    # with a secondary= relationship on the same tables is documented to
    # risk inconsistent reads/writes unless the secondary= side is
    # read-only - confirmed empirically that appending through one of these
    # does not persist anything, rather than silently writing a row missing
    # the columns (like tenant_id) the real association classes require.
    # Writes always go through stat_group_links/prototype_links/
    # dependent_links/containment/contained_links, or the association
    # classes directly - never through these.
    stat_groups: Mapped[list[StatGroup]] = relationship(
        lazy="raise_on_sql", secondary="entity_stat_group", viewonly=True
    )
    prototypes: Mapped[list[Entity]] = relationship(
        lazy="raise_on_sql",
        secondary="entity_prototype",
        primaryjoin="Entity.id == EntityPrototype.entity_id",
        secondaryjoin="Entity.id == EntityPrototype.prototype_id",
        viewonly=True,
    )
    instances: Mapped[list[Entity]] = relationship(
        lazy="raise_on_sql",
        secondary="entity_prototype",
        primaryjoin="Entity.id == EntityPrototype.prototype_id",
        secondaryjoin="Entity.id == EntityPrototype.entity_id",
        viewonly=True,
    )
    parent: Mapped[Entity | None] = relationship(
        lazy="raise_on_sql",
        secondary="containment",
        primaryjoin="Entity.id == Containment.child_entity_id",
        secondaryjoin="Entity.id == Containment.parent_entity_id",
        viewonly=True,
    )
    children: Mapped[list[Entity]] = relationship(
        lazy="raise_on_sql",
        secondary="containment",
        primaryjoin="Entity.id == Containment.parent_entity_id",
        secondaryjoin="Entity.id == Containment.child_entity_id",
        viewonly=True,
    )
