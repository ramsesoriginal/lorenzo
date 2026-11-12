from __future__ import annotations

import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, FetchedValue, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, UuidPk, same_tenant_fk

if TYPE_CHECKING:
    from lorenzo_api.models.entity_stat import EntityStat
    from lorenzo_api.models.stat_definition_enum_value import StatDefinitionEnumValue
    from lorenzo_api.models.stat_group import StatGroup
    from lorenzo_api.models.tenant import Tenant


class StatValueType(enum.Enum):
    """Which of entity_stat's value_* columns a stat's value lives in."""

    INT = "int"
    TEXT = "text"
    FLOAT = "float"
    BOOL = "bool"
    # Stored in value_text, one of stat_definition_enum_value's values for
    # this definition (ADR 0103).
    ENUM = "enum"


class StatDefinition(Base):
    """Describes a single stat (weight, HP, ...) - see ADR 0014 and RFC 0001."""

    __tablename__ = "stat_definition"
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint("id", "tenant_id", name="stat_definition_id_tenant_id_key"),
        same_tenant_fk(
            "stat_definition_stat_group_id_fkey",
            ["stat_group_id"],
            "stat_group",
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "name"),
        # ADR 0449: one definition holds a role in a library, from the closed list of `roles.py`.
        Index(
            "stat_definition_tenant_id_role_key",
            "tenant_id",
            "role",
            unique=True,
            postgresql_where=text("role IS NOT NULL"),
        ),
        CheckConstraint(
            "role IS NULL OR role IN ('weight', 'height', 'price', 'rarity', 'hp', 'armor', "
            "'size', 'carry_capacity', 'containment_capacity', 'max_item_size', 'binding', "
            "'is_container')",
            name="stat_definition_role",
        ),
        # ADR 0279: a hint is a link to another definition of the same tenant. The database's key
        # is ON DELETE SET NULL (<the hint column>) (see the migration): SQLAlchemy only accepts
        # the plain keyword, which matters only for DDL, and migrations own that.
        same_tenant_fk(
            "stat_definition_max_hint_id_fkey",
            ["max_hint_id"],
            "stat_definition",
            ondelete="SET NULL",
        ),
        same_tenant_fk(
            "stat_definition_min_hint_id_fkey",
            ["min_hint_id"],
            "stat_definition",
            ondelete="SET NULL",
        ),
        same_tenant_fk(
            "stat_definition_resolved_hint_id_fkey",
            ["resolved_hint_id"],
            "stat_definition",
            ondelete="SET NULL",
        ),
    )

    id: Mapped[UuidPk]
    tenant_id: Mapped[TenantFk]
    stat_group_id: Mapped[uuid.UUID] = mapped_column(index=True)
    name: Mapped[str]
    # What the API reads this stat as, by role and not by name (ADR 0449): null for most. A role-
    # holder belongs to no game system.
    role: Mapped[str | None]
    value_type: Mapped[StatValueType] = mapped_column(
        Enum(
            StatValueType,
            name="stat_value_type",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
    )
    # How the stat is shown (ADR 0278): a unit ("ft"), a leading sign, whether a person can
    # change it in play (a number's stepper, a tag's toggle), and whether the sheet's fixed bar
    # keeps it in view. None of it limits or changes a value.
    unit: Mapped[str | None]
    adjustable_in_play: Mapped[bool] = mapped_column(server_default=text("false"))
    pin: Mapped[bool] = mapped_column(server_default=text("false"))
    signed: Mapped[bool] = mapped_column(server_default=text("false"))
    # Where it comes in its group (ADR 0278): not dense, not unique. Left unset on insert, a
    # trigger appends it after the group's last definition; FetchedValue reads it back.
    position: Mapped[int] = mapped_column(server_default=FetchedValue())
    # Clues for a sheet (ADR 0279), each another definition of the tenant: its value on the same
    # entity is the maximum shown as "of N", the floor a stepper stops at, and the value shown
    # beside this one ("+3"). Nothing checks a value against them.
    max_hint_id: Mapped[uuid.UUID | None]
    min_hint_id: Mapped[uuid.UUID | None]
    resolved_hint_id: Mapped[uuid.UUID | None]
    # The scale of an int or float stat (ADR 0403): a write of an own value outside it is
    # refused; a computed value is never clamped. Either may be unset.
    min_value: Mapped[float | None]
    max_value: Mapped[float | None]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    tenant: Mapped[Tenant] = relationship(
        foreign_keys="StatDefinition.tenant_id",
        lazy="raise_on_sql",
        back_populates="stat_definitions",
    )
    stat_group: Mapped[StatGroup] = relationship(
        foreign_keys="StatDefinition.stat_group_id",
        lazy="raise_on_sql",
        back_populates="stat_definitions",
    )
    # Empty unless value_type is ENUM (ADR 0103).
    enum_values: Mapped[list[StatDefinitionEnumValue]] = relationship(
        foreign_keys="StatDefinitionEnumValue.stat_definition_id",
        lazy="raise_on_sql",
        back_populates="stat_definition",
        order_by="(StatDefinitionEnumValue.sort_order, StatDefinitionEnumValue.value)",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    entity_stats: Mapped[list[EntityStat]] = relationship(
        foreign_keys="EntityStat.stat_definition_id",
        lazy="raise_on_sql",
        back_populates="stat_definition",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
