from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship

from lorenzo_api.db import Base, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.stat_definition import StatDefinition
    from lorenzo_api.models.stat_group import StatGroup


class Tenant(Base):
    """The persistent RLS boundary - a shared world a GM or team runs. See
    ADR 0013 (this minimal bootstrap) and ADR 0010 (the full model, not yet
    built).

    Only entity-anchored or independent-top-level tables get a
    back-populated collection here (see ADR 0018) - everything else's
    tenant_id stays a plain column, reachable through Entity/StatGroup
    instead of directly off Tenant.
    """

    __tablename__ = "tenant"

    id: Mapped[UuidPk]

    entities: Mapped[list[Entity]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    stat_groups: Mapped[list[StatGroup]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    stat_definitions: Mapped[list[StatDefinition]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
