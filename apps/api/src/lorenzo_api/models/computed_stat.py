from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Numeric, UniqueConstraint, text
from sqlalchemy.orm import Mapped, QueryableAttribute, mapped_column, relationship, selectinload
from sqlalchemy.orm.strategy_options import _AbstractLoad

from lorenzo_api.db import Base, CreatedAt, TenantFk, UpdatedAt, same_tenant_fk

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
    ComputedStatLinear/ComputedStatComparison/ComputedStatSum has the
    matching row is the kind. The API never lets one entity hold both a formula and a direct
    value for the same stat.
    """

    __tablename__ = "computed_stat"
    __table_args__ = (
        # ADR 0117: what same-tenant keys into this table reference.
        UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_entity_id_stat_definition_id_tenant_id_key",
        ),
        same_tenant_fk("computed_stat_entity_id_fkey", ["entity_id"], "entity", ondelete="CASCADE"),
        same_tenant_fk(
            "computed_stat_stat_definition_id_fkey",
            ["stat_definition_id"],
            "stat_definition",
            ondelete="CASCADE",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    created_at: Mapped[CreatedAt]
    updated_at: Mapped[UpdatedAt]

    entity: Mapped[Entity] = relationship(
        foreign_keys="ComputedStat.entity_id", lazy="raise_on_sql"
    )
    linear: Mapped[ComputedStatLinear | None] = relationship(
        foreign_keys="[ComputedStatLinear.entity_id, ComputedStatLinear.stat_definition_id]",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    comparison: Mapped[ComputedStatComparison | None] = relationship(
        foreign_keys=(
            "[ComputedStatComparison.entity_id, ComputedStatComparison.stat_definition_id]"
        ),
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    sum: Mapped[ComputedStatSum | None] = relationship(
        foreign_keys="[ComputedStatSum.entity_id, ComputedStatSum.stat_definition_id]",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def kind(self) -> str:
        """Requires linear/comparison/sum loaded."""
        if self.linear is not None:
            return "linear"
        return "sum" if self.sum is not None else "comparison"

    def source_stat_definition_ids(self) -> list[uuid.UUID]:
        """The stats this formula reads - its edges in the definition-level
        dependency graph (ADR 0104). Requires linear/comparison/sum (and
        its terms) loaded."""
        if self.linear is not None:
            return [self.linear.source_stat_definition_id]
        if self.comparison is not None:
            ids = [self.comparison.left_stat_definition_id]
            if self.comparison.right_stat_definition_id is not None:
                ids.append(self.comparison.right_stat_definition_id)
            return ids
        if self.sum is not None:
            return [term.source_stat_definition_id for term in self.sum.terms]
        return []


def _kind_key(table: str) -> tuple[ForeignKeyConstraint]:
    return (
        same_tenant_fk(
            f"{table}_entity_id_stat_definition_id_fkey",
            ["entity_id", "stat_definition_id"],
            "computed_stat",
            ["entity_id", "stat_definition_id"],
            ondelete="CASCADE",
        ),
    )


class ComputedStatLinear(Base):
    """`round(source × multiplier + offset)` - ADR 0104."""

    __tablename__ = "computed_stat_linear"
    __table_args__ = (
        *_kind_key("computed_stat_linear"),
        same_tenant_fk(
            "computed_stat_linear_source_stat_definition_id_fkey",
            ["source_stat_definition_id"],
            "stat_definition",
        ),
        CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_linear_round_mode",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    source_stat_definition_id: Mapped[uuid.UUID] = mapped_column(index=True)
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
        *_kind_key("computed_stat_comparison"),
        same_tenant_fk(
            "computed_stat_comparison_left_stat_definition_id_fkey",
            ["left_stat_definition_id"],
            "stat_definition",
        ),
        same_tenant_fk(
            "computed_stat_comparison_right_stat_definition_id_fkey",
            ["right_stat_definition_id"],
            "stat_definition",
        ),
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
    left_stat_definition_id: Mapped[uuid.UUID] = mapped_column(index=True)
    comparator: Mapped[str]
    right_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    right_constant: Mapped[Decimal | None] = mapped_column(Numeric())
    true_value: Mapped[str | None]
    false_value: Mapped[str | None]


class ComputedStatSum(Base):
    """`round(Σ coefficient × stat + offset)` over its terms, stats of the
    same entity - ADR 0126."""

    __tablename__ = "computed_stat_sum"
    __table_args__ = (
        *_kind_key("computed_stat_sum"),
        # ADR 0117: what its terms' same-tenant key references.
        UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_sum_entity_id_stat_definition_id_tenant_id_key",
        ),
        CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_sum_round_mode",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    offset: Mapped[Decimal] = mapped_column(Numeric(), server_default=text("0"))
    round_mode: Mapped[str] = mapped_column(server_default=text("'none'"))

    terms: Mapped[list[ComputedStatSumTerm]] = relationship(
        foreign_keys="[ComputedStatSumTerm.entity_id, ComputedStatSumTerm.stat_definition_id]",
        order_by="ComputedStatSumTerm.position",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ComputedStatSumTerm(Base):
    """One `coefficient × stat` of a sum - ADR 0126. A stat appears in a sum
    at most once (the key); `position` keeps the order it was written in."""

    __tablename__ = "computed_stat_sum_term"
    __table_args__ = (
        same_tenant_fk(
            "computed_stat_sum_term_entity_id_stat_definition_id_fkey",
            ["entity_id", "stat_definition_id"],
            "computed_stat_sum",
            ["entity_id", "stat_definition_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "computed_stat_sum_term_source_stat_definition_id_fkey",
            ["source_stat_definition_id"],
            "stat_definition",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    source_stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True, index=True)
    tenant_id: Mapped[TenantFk]
    coefficient: Mapped[Decimal] = mapped_column(Numeric(), server_default=text("1"))
    position: Mapped[int]


def formula_load_options(path: _AbstractLoad | None = None) -> list[_AbstractLoad]:
    """Eager loads for every formula kind's parameters, which evaluation
    and serialization read (ADR 0104, 0126): from a query on ComputedStat
    itself, or along `path` to its computed_stat."""

    def load(attr: QueryableAttribute[Any]) -> _AbstractLoad:
        return path.selectinload(attr) if path is not None else selectinload(attr)

    return [
        load(ComputedStat.linear),
        load(ComputedStat.comparison),
        load(ComputedStat.sum).selectinload(ComputedStatSum.terms),
    ]
