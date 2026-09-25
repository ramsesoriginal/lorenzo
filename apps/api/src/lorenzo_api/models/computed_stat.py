from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt

if TYPE_CHECKING:
    from lorenzo_api.models.entity import Entity


class RoundMode(enum.Enum):
    """How a linear formula's result is rounded (ADR 0104). `floor` and
    `truncate` differ for negative results: floor((9 - 10) / 2) is -1 (the
    right D&D modifier), truncation gives 0."""

    NONE = "none"
    FLOOR = "floor"
    CEIL = "ceil"
    # Half away from zero.
    ROUND = "round"
    # Toward zero.
    TRUNCATE = "truncate"


class Comparator(enum.Enum):
    LT = "lt"
    LE = "le"
    EQ = "eq"
    NE = "ne"
    GE = "ge"
    GT = "gt"


class ComputedStat(Base):
    """An entity's formula for one stat - see ADR 0104/RFC 0016. Addressed
    exactly like entity_stat, and competes with it in v_effective_stat at
    its prototype hop. No kind column, like payload (ADR 0017): which of
    ComputedStatLinear/ComputedStatComparison has the matching row is the
    kind. The API never lets one entity hold both a formula and a direct
    value for the same stat.
    """

    __tablename__ = "computed_stat"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity.id", ondelete="CASCADE"), primary_key=True
    )
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stat_definition.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_id: Mapped[TenantFk]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    entity: Mapped[Entity] = relationship(lazy="raise_on_sql")
    linear: Mapped[ComputedStatLinear | None] = relationship(
        lazy="raise_on_sql", cascade="all, delete-orphan", passive_deletes=True
    )
    comparison: Mapped[ComputedStatComparison | None] = relationship(
        lazy="raise_on_sql", cascade="all, delete-orphan", passive_deletes=True
    )

    @property
    def kind(self) -> str:
        """Requires linear/comparison loaded."""
        return "linear" if self.linear is not None else "comparison"

    def source_stat_definition_ids(self) -> list[uuid.UUID]:
        """The stats this formula reads - its edges in the definition-level
        dependency graph (ADR 0104). Requires linear/comparison loaded."""
        if self.linear is not None:
            return [self.linear.source_stat_definition_id]
        if self.comparison is not None:
            ids = [self.comparison.left_stat_definition_id]
            if self.comparison.right_stat_definition_id is not None:
                ids.append(self.comparison.right_stat_definition_id)
            return ids
        return []


def _kind_key() -> tuple[ForeignKeyConstraint]:
    return (
        ForeignKeyConstraint(
            ["entity_id", "stat_definition_id"],
            ["computed_stat.entity_id", "computed_stat.stat_definition_id"],
            ondelete="CASCADE",
        ),
    )


class ComputedStatLinear(Base):
    """`round(source × multiplier + offset)` - ADR 0104."""

    __tablename__ = "computed_stat_linear"
    __table_args__ = (
        *_kind_key(),
        CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_linear_round_mode",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    source_stat_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stat_definition.id"), index=True
    )
    multiplier: Mapped[Decimal] = mapped_column(Numeric())
    offset: Mapped[Decimal] = mapped_column(Numeric(), server_default=text("0"))
    # Plain text + CHECK rather than a Postgres enum: easier to extend.
    round_mode: Mapped[str] = mapped_column(server_default=text("'none'"))


class ComputedStatComparison(Base):
    """`left <comparator> right`, with right a stat or a constant - ADR
    0104. A bool target gets the outcome itself; a text/enum target gets
    true_value or false_value."""

    __tablename__ = "computed_stat_comparison"
    __table_args__ = (
        *_kind_key(),
        CheckConstraint(
            "comparator IN ('lt', 'le', 'eq', 'ne', 'ge', 'gt')",
            name="computed_stat_comparison_comparator",
        ),
        CheckConstraint(
            "num_nonnulls(right_stat_definition_id, right_constant) = 1",
            name="computed_stat_comparison_one_right_side",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    left_stat_definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stat_definition.id"), index=True
    )
    comparator: Mapped[str]
    right_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stat_definition.id"), index=True
    )
    right_constant: Mapped[Decimal | None] = mapped_column(Numeric())
    true_value: Mapped[str | None]
    false_value: Mapped[str | None]
