from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, FetchedValue, Index, Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity_stat_group import EntityStatGroup
    from lorenzo_api.models.stat_definition import StatDefinition
    from lorenzo_api.models.system import System
    from lorenzo_api.models.tenant import Tenant


class StatGroup(Base):
    """Clusters related stat_definitions - see ADR 0014 and RFC 0001."""

    __tablename__ = "stat_group"
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint("id", "tenant_id", name="stat_group_id_tenant_id_key"),
        UniqueConstraint("tenant_id", "name"),
        # ADR 0449: one group holds a role in a library, from the closed list of `roles.py`.
        Index(
            "stat_group_tenant_id_role_key",
            "tenant_id",
            "role",
            unique=True,
            postgresql_where=text("role IS NOT NULL"),
        ),
        CheckConstraint(
            "role IS NULL OR role IN ('physical', 'economic', 'destroyable', 'damaging', 'tags')",
            name="stat_group_role",
        ),
        # RFC 0052: the system it belongs to, or none (neutral). Deleting a system is refused while
        # a group has it, so the key does not clear it.
        same_tenant_fk("stat_group_system_id_fkey", ["system_id"], "system"),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    name: Mapped[str]
    # What the API reads this group as, by role and not by name (ADR 0449): null for most. A
    # role-holder belongs to no game system.
    role: Mapped[str | None]
    # Inheritance tie-break (RFC 0001, ADR 0037): the effective-stat views prefer the
    # highest priority among inherited values at the same distance.
    priority: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # The game system this group (and so its definitions) belongs to, or none (ADR 0448). A
    # definition of a group with a system starts with the system's slug and an underscore.
    system_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    # Display-only (ADR 0103): lets a client show the group's fields even
    # when empty. Nothing checks a mandatory group is filled in.
    mandatory: Mapped[bool] = mapped_column(server_default=text("false"))
    # Where it comes in the tenant's vocabulary (ADR 0278): not dense, not unique. `priority` is
    # the rank that breaks ties between inherited values, not a display order. Left unset on
    # insert, a trigger appends it after the tenant's last group.
    position: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    # ADR 0281: the tenant also points at one of its groups, so this names the key it means.
    tenant: Mapped[Tenant] = relationship(
        foreign_keys="StatGroup.tenant_id", lazy="raise_on_sql", back_populates="stat_groups"
    )
    stat_definitions: Mapped[list[StatDefinition]] = relationship(
        foreign_keys="StatDefinition.stat_group_id",
        lazy="raise_on_sql",
        back_populates="stat_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    # Read-only, for the slug a stat row says (ADR 0448).
    system: Mapped[System | None] = relationship(
        primaryjoin="StatGroup.system_id == System.id",
        foreign_keys="StatGroup.system_id",
        viewonly=True,
        lazy="raise_on_sql",
    )
    entity_links: Mapped[list[EntityStatGroup]] = relationship(
        foreign_keys="EntityStatGroup.stat_group_id",
        lazy="raise_on_sql",
        back_populates="stat_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
