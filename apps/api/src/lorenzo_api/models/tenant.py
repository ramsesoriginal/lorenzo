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
    # Same reasoning as name, extended to slug (ADR 0030/RFC 0003 doesn't
    # spell this out for slug specifically, only description, but ~50
    # existing bare Tenant() fixture calls make the retrofit cost identical
    # to name's own). A random default is a placeholder, not a real slug -
    # real tenant-creation code (RFC 0012, not built yet) always supplies a
    # derived one explicitly, the same relationship name's default has to a
    # real create-tenant flow. Globally unique (tenants aren't nested under
    # anything to scope uniqueness by), so a random default can never
    # collide in practice, matching every gen_random_uuid() PK already
    # trusted throughout this schema.
    slug: Mapped[str] = mapped_column(unique=True, server_default=text("gen_random_uuid()::text"))
    description: Mapped[str] = mapped_column(server_default=text("''"))

    entities: Mapped[list[Entity]] = relationship(
        lazy="raise_on_sql",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    stat_groups: Mapped[list[StatGroup]] = relationship(
        lazy="raise_on_sql",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    stat_definitions: Mapped[list[StatDefinition]] = relationship(
        lazy="raise_on_sql",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    memberships: Mapped[list[Membership]] = relationship(
        lazy="raise_on_sql",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    campaigns: Mapped[list[Campaign]] = relationship(
        lazy="raise_on_sql",
        back_populates="tenant",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
