from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    CheckConstraint,
    ForeignKeyConstraint,
    Numeric,
    UniqueConstraint,
    false,
    text,
)
from sqlalchemy.orm import Mapped, QueryableAttribute, joinedload, mapped_column, relationship
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
    ComputedStatLinear/ComputedStatComparison/ComputedStatSum/
    ComputedStatContents has the matching row is the kind. The API never
    lets one entity hold both a formula and a direct value for the same
    stat.
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
    contents: Mapped[ComputedStatContents | None] = relationship(
        foreign_keys="[ComputedStatContents.entity_id, ComputedStatContents.stat_definition_id]",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    extremum: Mapped[ComputedStatExtremum | None] = relationship(
        foreign_keys="[ComputedStatExtremum.entity_id, ComputedStatExtremum.stat_definition_id]",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    product: Mapped[ComputedStatProduct | None] = relationship(
        foreign_keys="[ComputedStatProduct.entity_id, ComputedStatProduct.stat_definition_id]",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    ratio: Mapped[ComputedStatRatio | None] = relationship(
        foreign_keys="[ComputedStatRatio.entity_id, ComputedStatRatio.stat_definition_id]",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    select: Mapped[ComputedStatSelect | None] = relationship(
        foreign_keys="[ComputedStatSelect.entity_id, ComputedStatSelect.stat_definition_id]",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def kind(self) -> str:
        """Requires every kind's row loaded (formula_load_options)."""
        if self.linear is not None:
            return "linear"
        if self.sum is not None:
            return "sum"
        if self.extremum is not None:
            return self.extremum.pick
        if self.product is not None:
            return "product"
        if self.ratio is not None:
            return "ratio"
        if self.select is not None:
            return "select"
        return "contents" if self.contents is not None else "comparison"

    def source_stat_definition_ids(self) -> list[uuid.UUID]:
        """This formula's edges in the definition-level dependency graph
        (ADR 0104): the stats of the same entity it reads. A contents
        formula has none - it reads a level down (ADR 0127). Requires every
        kind's row (and a sum's terms) loaded."""
        if self.linear is not None:
            return [self.linear.source_stat_definition_id]
        if self.comparison is not None:
            ids = [self.comparison.left_stat_definition_id]
            if self.comparison.right_stat_definition_id is not None:
                ids.append(self.comparison.right_stat_definition_id)
            return ids
        if self.sum is not None:
            return [term.source_stat_definition_id for term in self.sum.terms]
        if self.extremum is not None:
            return [
                operand.source_stat_definition_id
                for operand in self.extremum.inputs
                if operand.source_stat_definition_id is not None
            ]
        if self.product is not None:
            return [factor.source_stat_definition_id for factor in self.product.factors]
        if self.ratio is not None:
            ids = [self.ratio.numerator_stat_definition_id]
            if self.ratio.denominator_stat_definition_id is not None:
                ids.append(self.ratio.denominator_stat_definition_id)
            return ids
        if self.select is not None:
            ids = [self.select.source_stat_definition_id]
            ids += [
                step.result_stat_definition_id
                for step in self.select.steps
                if step.result_stat_definition_id is not None
            ]
            if self.select.otherwise_stat_definition_id is not None:
                ids.append(self.select.otherwise_stat_definition_id)
            return ids
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


class ComputedStatContents(Base):
    """An aggregate of a stat over what's directly inside the entity, the stat resolved on each
    thing inside - ADR 0127, and its options, ADR 0447. The default, `Σ stat × quantity`, is
    ADR 0127's; `aggregate` may instead be `min`, `max` or `count` (which ignores the stat, so
    the source is empty then), `only_active` skips a held thing whose `active` switch is off,
    `only_kind` keeps one kind of held thing, `where` a `bool` stat that must be true on the
    held thing, and `if_none` is what `min` and `max` of nothing give."""

    __tablename__ = "computed_stat_contents"
    __table_args__ = (
        *_kind_key("computed_stat_contents"),
        same_tenant_fk(
            "computed_stat_contents_source_stat_definition_id_fkey",
            ["source_stat_definition_id"],
            "stat_definition",
        ),
        same_tenant_fk(
            "computed_stat_contents_where_stat_definition_id_fkey",
            ["where_stat_definition_id"],
            "stat_definition",
        ),
        CheckConstraint(
            "aggregate IN ('sum', 'min', 'max', 'count')", name="computed_stat_contents_aggregate"
        ),
        CheckConstraint(
            "only_kind IS NULL OR only_kind IN ('item_instance')",
            name="computed_stat_contents_only_kind",
        ),
        CheckConstraint(
            "aggregate = 'count' OR source_stat_definition_id IS NOT NULL",
            name="computed_stat_contents_source_unless_count",
        ),
        CheckConstraint(
            "if_none IS NULL OR aggregate IN ('min', 'max')",
            name="computed_stat_contents_if_none_for_min_max",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    source_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    aggregate: Mapped[str] = mapped_column(server_default=text("'sum'"))
    only_active: Mapped[bool] = mapped_column(server_default=false())
    only_kind: Mapped[str | None]
    where_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    if_none: Mapped[Decimal | None] = mapped_column(Numeric())


class ComputedStatExtremum(Base):
    """`min` or `max` of two to five inputs, each a stat of the same entity or a
    constant - ADR 0444. One table for both kinds, `pick` saying which: they hold the same
    parameters, and a shared table keeps the read of a formula at one row for both."""

    __tablename__ = "computed_stat_extremum"
    __table_args__ = (
        *_kind_key("computed_stat_extremum"),
        # ADR 0117: what its inputs' same-tenant key references.
        UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_extremum_entity_stat_tenant_key",
        ),
        CheckConstraint("pick IN ('min', 'max')", name="computed_stat_extremum_pick"),
        CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_extremum_round_mode",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    pick: Mapped[str]
    round_mode: Mapped[str] = mapped_column(server_default=text("'none'"))

    inputs: Mapped[list[ComputedStatExtremumInput]] = relationship(
        foreign_keys=(
            "[ComputedStatExtremumInput.entity_id, ComputedStatExtremumInput.stat_definition_id]"
        ),
        order_by="ComputedStatExtremumInput.position",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ComputedStatExtremumInput(Base):
    """One input of a `min` or `max`: a stat or a constant, in the order written - ADR 0444."""

    __tablename__ = "computed_stat_extremum_input"
    __table_args__ = (
        same_tenant_fk(
            "computed_stat_extremum_input_entity_id_stat_definition_id_fkey",
            ["entity_id", "stat_definition_id"],
            "computed_stat_extremum",
            ["entity_id", "stat_definition_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "computed_stat_extremum_input_source_stat_definition_id_fkey",
            ["source_stat_definition_id"],
            "stat_definition",
        ),
        CheckConstraint(
            "num_nonnulls(source_stat_definition_id, constant) = 1",
            name="computed_stat_extremum_input_one_operand",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    source_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    constant: Mapped[Decimal | None] = mapped_column(Numeric())


class ComputedStatProduct(Base):
    """`round(factor₁ × factor₂ × … × multiplier + offset)` over two to five stats of the same
    entity - ADR 0445. A flag is a factor of 1 or 0."""

    __tablename__ = "computed_stat_product"
    __table_args__ = (
        *_kind_key("computed_stat_product"),
        # ADR 0117: what its factors' same-tenant key references.
        UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_product_entity_stat_tenant_key",
        ),
        CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_product_round_mode",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    multiplier: Mapped[Decimal] = mapped_column(Numeric(), server_default=text("1"))
    offset: Mapped[Decimal] = mapped_column(Numeric(), server_default=text("0"))
    round_mode: Mapped[str] = mapped_column(server_default=text("'none'"))

    factors: Mapped[list[ComputedStatProductFactor]] = relationship(
        foreign_keys=(
            "[ComputedStatProductFactor.entity_id, ComputedStatProductFactor.stat_definition_id]"
        ),
        order_by="ComputedStatProductFactor.position",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ComputedStatProductFactor(Base):
    """One factor of a product: a stat, in the order written - ADR 0445. A stat may appear
    twice (`a × a`), which is why the key is the position."""

    __tablename__ = "computed_stat_product_factor"
    __table_args__ = (
        same_tenant_fk(
            "computed_stat_product_factor_entity_id_stat_definition_id_fkey",
            ["entity_id", "stat_definition_id"],
            "computed_stat_product",
            ["entity_id", "stat_definition_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "computed_stat_product_factor_source_stat_definition_id_fkey",
            ["source_stat_definition_id"],
            "stat_definition",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    source_stat_definition_id: Mapped[uuid.UUID] = mapped_column(index=True)


class ComputedStatRatio(Base):
    """`round(numerator ÷ denominator × multiplier + offset)`, the numerator a stat of the same
    entity and the denominator a stat or a constant - ADR 0445. The quotient is rounded at the
    default precision before the offset and the rounding mode apply."""

    __tablename__ = "computed_stat_ratio"
    __table_args__ = (
        *_kind_key("computed_stat_ratio"),
        same_tenant_fk(
            "computed_stat_ratio_numerator_stat_definition_id_fkey",
            ["numerator_stat_definition_id"],
            "stat_definition",
        ),
        same_tenant_fk(
            "computed_stat_ratio_denominator_stat_definition_id_fkey",
            ["denominator_stat_definition_id"],
            "stat_definition",
        ),
        CheckConstraint(
            "num_nonnulls(denominator_stat_definition_id, denominator_constant) = 1",
            name="computed_stat_ratio_one_denominator",
        ),
        CheckConstraint(
            "round_mode IN ('none', 'floor', 'ceil', 'round', 'truncate')",
            name="computed_stat_ratio_round_mode",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    numerator_stat_definition_id: Mapped[uuid.UUID] = mapped_column(index=True)
    denominator_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)
    denominator_constant: Mapped[Decimal | None] = mapped_column(Numeric())
    multiplier: Mapped[Decimal] = mapped_column(Numeric(), server_default=text("1"))
    offset: Mapped[Decimal] = mapped_column(Numeric(), server_default=text("0"))
    round_mode: Mapped[str] = mapped_column(server_default=text("'none'"))


class ComputedStatSelect(Base):
    """A value from a table - ADR 0446. The source is a stat of the same entity; in `threshold`
    mode the steps are `from` values and the result is that of the highest one the source
    reaches, in `match` mode the steps are values and the result is that of the one the source
    holds. When none applies the formula gives `otherwise`, or no value when that is empty. A
    result is a constant (one of the number, text and bool columns) or a stat of the same
    entity, exactly one of the four."""

    __tablename__ = "computed_stat_select"
    __table_args__ = (
        *_kind_key("computed_stat_select"),
        # ADR 0117: what its steps' same-tenant key references.
        UniqueConstraint(
            "entity_id",
            "stat_definition_id",
            "tenant_id",
            name="computed_stat_select_entity_stat_tenant_key",
        ),
        same_tenant_fk(
            "computed_stat_select_source_stat_definition_id_fkey",
            ["source_stat_definition_id"],
            "stat_definition",
        ),
        same_tenant_fk(
            "computed_stat_select_otherwise_stat_definition_id_fkey",
            ["otherwise_stat_definition_id"],
            "stat_definition",
        ),
        CheckConstraint("mode IN ('threshold', 'match')", name="computed_stat_select_mode"),
        CheckConstraint(
            "num_nonnulls(otherwise_number, otherwise_text, otherwise_bool,"
            " otherwise_stat_definition_id) <= 1",
            name="computed_stat_select_one_otherwise",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    source_stat_definition_id: Mapped[uuid.UUID] = mapped_column(index=True)
    mode: Mapped[str]
    otherwise_number: Mapped[Decimal | None] = mapped_column(Numeric())
    otherwise_text: Mapped[str | None]
    otherwise_bool: Mapped[bool | None]
    otherwise_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)

    steps: Mapped[list[ComputedStatSelectStep]] = relationship(
        foreign_keys=(
            "[ComputedStatSelectStep.entity_id, ComputedStatSelectStep.stat_definition_id]"
        ),
        order_by="ComputedStatSelectStep.position",
        lazy="raise_on_sql",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ComputedStatSelectStep(Base):
    """One step of a select, in the order written - ADR 0446: a `from` value (`threshold`) or a
    value to match (`match_value`), and its result."""

    __tablename__ = "computed_stat_select_step"
    __table_args__ = (
        same_tenant_fk(
            "computed_stat_select_step_entity_id_stat_definition_id_fkey",
            ["entity_id", "stat_definition_id"],
            "computed_stat_select",
            ["entity_id", "stat_definition_id"],
            ondelete="CASCADE",
        ),
        same_tenant_fk(
            "computed_stat_select_step_result_stat_definition_id_fkey",
            ["result_stat_definition_id"],
            "stat_definition",
        ),
        CheckConstraint(
            "num_nonnulls(threshold, match_value) = 1", name="computed_stat_select_step_one_key"
        ),
        CheckConstraint(
            "num_nonnulls(result_number, result_text, result_bool, result_stat_definition_id) = 1",
            name="computed_stat_select_step_one_result",
        ),
    )

    entity_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    stat_definition_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[TenantFk]
    threshold: Mapped[Decimal | None] = mapped_column(Numeric())
    match_value: Mapped[str | None]
    result_number: Mapped[Decimal | None] = mapped_column(Numeric())
    result_text: Mapped[str | None]
    result_bool: Mapped[bool | None]
    result_stat_definition_id: Mapped[uuid.UUID | None] = mapped_column(index=True)


def formula_load_options(path: _AbstractLoad | None = None) -> list[_AbstractLoad]:
    """Eager loads for every formula kind's parameters, which evaluation
    and serialization read (ADR 0104, 0126): from a query on ComputedStat
    itself, or along `path` to its computed_stat.

    A kind with one row per formula is joined into the query for the formula (ADR 0444), a kind
    with a list of rows is one more statement: a new kind adds a join, not a statement, so a
    read costs no more than it did before the kinds that came after the four of ADR 0104."""

    def join(attr: QueryableAttribute[Any]) -> _AbstractLoad:
        return path.joinedload(attr) if path is not None else joinedload(attr)

    return [
        join(ComputedStat.linear),
        join(ComputedStat.comparison),
        join(ComputedStat.sum).selectinload(ComputedStatSum.terms),
        join(ComputedStat.contents),
        join(ComputedStat.extremum).selectinload(ComputedStatExtremum.inputs),
        join(ComputedStat.product).selectinload(ComputedStatProduct.factors),
        join(ComputedStat.ratio),
        join(ComputedStat.select).selectinload(ComputedStatSelect.steps),
    ]
