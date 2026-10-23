"""Locations and their part-of tree (ADR 0330)."""

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from lorenzo_api.db import Base, TenantFk, same_tenant_fk


class Location(Base):
    """The marker that makes an entry a Location. It carries nothing else."""

    __tablename__ = "location"
    __table_args__ = (
        UniqueConstraint("entity_id", "tenant_id", name="location_entity_tenant_key"),
        same_tenant_fk("location_entity_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]


class LocationPart(Base):
    """One Location is a part of another. A root is a Location with no row here. Containment,
    ownership and prototypes are other relations; nothing here is read as one of them."""

    __tablename__ = "location_part"
    __table_args__ = (
        CheckConstraint("child_entity_id <> parent_entity_id", name="location_part_distinct"),
        same_tenant_fk(
            "location_part_child_fkey",
            ["child_entity_id"],
            "location",
            ["entity_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "location_part_parent_fkey",
            ["parent_entity_id"],
            "location",
            ["entity_id"],
            ondelete="CASCADE",
        ),
    )
    child_entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    parent_entity_id: Mapped[uuid.UUID]
    tenant_id: Mapped[TenantFk]
    # Orders siblings only: no zero point, unit, direction or uniqueness.
    level_ordinal: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
