from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, UuidPk

if TYPE_CHECKING:
    from lorenzo_api.models.campaign import Campaign
    from lorenzo_api.models.entity import Entity
    from lorenzo_api.models.membership import Membership
    from lorenzo_api.models.stat_definition import StatDefinition
    from lorenzo_api.models.stat_group import StatGroup


class Tenant(Base):
    """The persistent RLS boundary - a shared world a GM or team runs. See
    ADR 0013 (this minimal bootstrap) and ADR 0022 (the full model).

    Only entity-anchored or independent-top-level tables get a
    back-populated collection here (see ADR 0018) - everything else's
    tenant_id stays a plain column, reachable through Entity/StatGroup
    instead of directly off Tenant.
    """

    __tablename__ = "tenant"

    id: Mapped[UuidPk]
    # Server-side default (not a hardcoded Python one) so the many existing
    # bare Tenant() fixture calls across the test suite - none of which
    # actually test the name itself - don't all need retrofitting; real
    # callers that care about the name (none yet - no create-tenant REST
    # flow exists) pass it explicitly. See ADR 0022.
    name: Mapped[str] = mapped_column(server_default=text("'Unnamed Tenant'"))

    entities: Mapped[list[Entity]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    stat_groups: Mapped[list[StatGroup]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    stat_definitions: Mapped[list[StatDefinition]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
    campaigns: Mapped[list[Campaign]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan", passive_deletes=True
    )
