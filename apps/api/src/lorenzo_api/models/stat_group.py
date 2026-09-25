from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.entity_stat_group import EntityStatGroup
    from lorenzo_api.models.stat_definition import StatDefinition
    from lorenzo_api.models.tenant import Tenant


class StatGroup(Base):
    """Clusters related stat_definitions - see ADR 0014 and RFC 0001."""

    __tablename__ = "stat_group"
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint("id", "tenant_id", name="stat_group_id_tenant_id_key"),
        UniqueConstraint("tenant_id", "name"),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    name: Mapped[str]
    # Inheritance tie-break (RFC 0001) - unused until entity_prototype exists
    # and something actually resolves effective stats through it.
    priority: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    # Display-only (ADR 0103): lets a client show the group's fields even
    # when empty. Nothing checks a mandatory group is filled in.
    mandatory: Mapped[bool] = mapped_column(server_default=text("false"))
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    tenant: Mapped[Tenant] = relationship(lazy="raise_on_sql", back_populates="stat_groups")
    stat_definitions: Mapped[list[StatDefinition]] = relationship(
        foreign_keys="StatDefinition.stat_group_id",
        lazy="raise_on_sql",
        back_populates="stat_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    entity_links: Mapped[list[EntityStatGroup]] = relationship(
        foreign_keys="EntityStatGroup.stat_group_id",
        lazy="raise_on_sql",
        back_populates="stat_group",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
