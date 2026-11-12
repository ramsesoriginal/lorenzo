from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lorenzo_api.models import Comparator, ComputedStat, RoundMode
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.stat_evaluation import (
    ComparisonFormula,
    ContentsFormula,
    ExtremumFormula,
    Formula,
    LinearFormula,
    Operand,
    ProductFormula,
    RatioFormula,
    SelectFormula,
    SelectResult,
    SelectStep,
    SumFormula,
    SumTerm,
)

__all__ = [
    "ComparisonFormulaBody",
    "ContentsFormulaBody",
    "ComputedStatDependentOut",
    "ComputedStatOut",
    "ComputedStatPreviewIn",
    "ComputedStatPreviewOut",
    "ContentsExplanationOut",
    "ExtremumInputBody",
    "FormulaBody",
    "LinearFormulaBody",
    "MaxFormulaBody",
    "MinFormulaBody",
    "ChosenStepExplanationOut",
    "PickedExplanationOut",
    "PreviewInputOut",
    "ProductFormulaBody",
    "RatioFormulaBody",
    "SelectFormulaBody",
    "SelectResultBody",
    "SelectStepBody",
    "SumFormulaBody",
    "StatExplanationOut",
    "SumTermBody",
]

# ADR 0126: a sum reads at least one stat, and at most this many.
MAX_SUM_TERMS = 20
# ADR 0444: a min or a max takes two to five inputs.
MIN_EXTREMUM_INPUTS = 2
MAX_EXTREMUM_INPUTS = 5
# ADR 0445: a product multiplies two to five stats.
MIN_PRODUCT_FACTORS = 2
MAX_PRODUCT_FACTORS = 5
# ADR 0446: a select has one to this many steps.
MAX_SELECT_STEPS = 64


class LinearFormulaBody(BaseModel):
    """`round(source × multiplier + offset)` - ADR 0104. A D&D ability
    modifier is multiplier 0.5, offset -5, round_mode `floor`."""

    kind: Literal["linear"] = "linear"
    source_stat_definition_id: uuid.UUID
    multiplier: Decimal
    offset: Decimal = Decimal(0)
    round_mode: RoundMode = RoundMode.NONE

    def to_formula(self) -> LinearFormula:
        return LinearFormula(
            source_stat_definition_id=self.source_stat_definition_id,
            multiplier=self.multiplier,
            offset=self.offset,
            round_mode=self.round_mode,
        )


class ComparisonFormulaBody(BaseModel):
    """`left <comparator> right`, right being another stat or a constant -
    exactly one of the two (ADR 0104). A bool target gets the outcome; a
    text/enum target needs true_value and false_value."""

    kind: Literal["comparison"] = "comparison"
    left_stat_definition_id: uuid.UUID
    comparator: Comparator
    right_stat_definition_id: uuid.UUID | None = None
    right_constant: Decimal | None = None
    true_value: str | None = None
    false_value: str | None = None

    def to_formula(self) -> ComparisonFormula:
        return ComparisonFormula(
            left_stat_definition_id=self.left_stat_definition_id,
            comparator=self.comparator,
            right_stat_definition_id=self.right_stat_definition_id,
            right_constant=self.right_constant,
            true_value=self.true_value,
            false_value=self.false_value,
        )


class SumTermBody(BaseModel):
    stat_definition_id: uuid.UUID
    coefficient: Decimal = Decimal(1)


class SumFormulaBody(BaseModel):
    """`round(Σ coefficient × stat + offset)` over stats of the same entity -
    ADR 0126. `armour_class = 10 + dex_modifier + worn_ac_bonus` is two
    terms with coefficient 1 and offset 10. Each stat at most once."""

    kind: Literal["sum"] = "sum"
    terms: list[SumTermBody] = Field(min_length=1, max_length=MAX_SUM_TERMS)
    offset: Decimal = Decimal(0)
    round_mode: RoundMode = RoundMode.NONE

    def to_formula(self) -> SumFormula:
        return SumFormula(
            terms=tuple(
                SumTerm(source_stat_definition_id=t.stat_definition_id, coefficient=t.coefficient)
                for t in self.terms
            ),
            offset=self.offset,
            round_mode=self.round_mode,
        )


class ContentsFormulaBody(BaseModel):
    """An aggregate of a stat over what's directly inside - ADR 0127, and its options, ADR 0447.
    The default is `Σ stat × quantity`: `contents_weight` is `contents(weight)`, each thing
    inside's own weight, formulas included, times its stack count. `aggregate` may instead be
    `min`, `max` or `count`; `count` ignores the stat (leave it out), and `min`, `max` and `count`
    ignore the stack count. `only_active` skips a held thing whose `active` switch is off,
    `only_kind` keeps one kind of held thing (`item_instance` or `feature_instance`, ADR 0454),
    `where_stat_definition_id` is a
    `bool` stat that must be true on the held thing, and `if_none` is what `min` and `max` of
    nothing give (no value without it)."""

    kind: Literal["contents"] = "contents"
    source_stat_definition_id: uuid.UUID | None = None
    aggregate: Literal["sum", "min", "max", "count"] = "sum"
    only_active: bool = False
    only_kind: Literal["item_instance", "feature_instance"] | None = None
    where_stat_definition_id: uuid.UUID | None = None
    if_none: Decimal | None = None

    @model_validator(mode="after")
    def _the_options_fit_the_aggregate(self) -> ContentsFormulaBody:
        if self.aggregate != "count" and self.source_stat_definition_id is None:
            raise ValueError("source_stat_definition_id is needed unless the aggregate is count")
        if self.if_none is not None and self.aggregate not in ("min", "max"):
            raise ValueError("if_none is for a min or a max")
        return self

    def to_formula(self) -> ContentsFormula:
        return ContentsFormula(
            source_stat_definition_id=self.source_stat_definition_id,
            aggregate=self.aggregate,
            only_active=self.only_active,
            only_kind=self.only_kind,
            where_stat_definition_id=self.where_stat_definition_id,
            if_none=self.if_none,
        )


class ExtremumInputBody(BaseModel):
    """One input of a `min` or `max`: a stat of the same entity or a constant, exactly one of the
    two - ADR 0444."""

    stat_definition_id: uuid.UUID | None = None
    constant: Decimal | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> ExtremumInputBody:
        if (self.stat_definition_id is None) == (self.constant is None):
            raise ValueError("an input is exactly one of stat_definition_id or constant")
        return self


class _ExtremumBody(BaseModel):
    inputs: list[ExtremumInputBody] = Field(
        min_length=MIN_EXTREMUM_INPUTS, max_length=MAX_EXTREMUM_INPUTS
    )
    round_mode: RoundMode = RoundMode.NONE

    def _formula(self, pick: str) -> ExtremumFormula:
        return ExtremumFormula(
            pick=pick,
            inputs=tuple(
                Operand(stat_definition_id=i.stat_definition_id, constant=i.constant)
                for i in self.inputs
            ),
            round_mode=self.round_mode,
        )


class MinFormulaBody(_ExtremumBody):
    """The smallest of two to five inputs, stats of the same entity or constants - ADR 0444.
    `min(dexterity_modifier, 2)` is a cap. An int stat takes a rounding mode only when an input
    is a float stat or a fractional constant."""

    kind: Literal["min"] = "min"

    def to_formula(self) -> ExtremumFormula:
        return self._formula("min")


class MaxFormulaBody(_ExtremumBody):
    """The largest of two to five inputs, stats of the same entity or constants - ADR 0444.
    `max(hit_points, 0)` is a floor."""

    kind: Literal["max"] = "max"

    def to_formula(self) -> ExtremumFormula:
        return self._formula("max")


class ProductFormulaBody(BaseModel):
    """`round(factor1 x factor2 x ... x multiplier + offset)` over two to five stats of the same
    entity - ADR 0445. A `bool` is a factor of 1 or 0, so hit points from level are
    `product(level, average)` and a bonus that applies when a flag is set is
    `product(flag, bonus)`."""

    kind: Literal["product"] = "product"
    factors: list[uuid.UUID] = Field(min_length=MIN_PRODUCT_FACTORS, max_length=MAX_PRODUCT_FACTORS)
    multiplier: Decimal = Decimal(1)
    offset: Decimal = Decimal(0)
    round_mode: RoundMode = RoundMode.NONE

    def to_formula(self) -> ProductFormula:
        return ProductFormula(
            factors=tuple(self.factors),
            multiplier=self.multiplier,
            offset=self.offset,
            round_mode=self.round_mode,
        )


class RatioFormulaBody(BaseModel):
    """`round(numerator / denominator x multiplier + offset)`, the numerator a stat of the same
    entity and the denominator a stat or a constant, exactly one of the two - ADR 0445. A zero
    denominator gives no value. The quotient is rounded at 28 digits before the offset and the
    mode apply; an `int` stat needs a rounding mode."""

    kind: Literal["ratio"] = "ratio"
    numerator_stat_definition_id: uuid.UUID
    denominator_stat_definition_id: uuid.UUID | None = None
    denominator_constant: Decimal | None = None
    multiplier: Decimal = Decimal(1)
    offset: Decimal = Decimal(0)
    round_mode: RoundMode = RoundMode.NONE

    @model_validator(mode="after")
    def _exactly_one_denominator(self) -> RatioFormulaBody:
        if (self.denominator_stat_definition_id is None) == (self.denominator_constant is None):
            raise ValueError(
                "a ratio needs exactly one of denominator_stat_definition_id or "
                "denominator_constant"
            )
        return self

    def to_formula(self) -> RatioFormula:
        return RatioFormula(
            numerator=self.numerator_stat_definition_id,
            denominator=Operand(
                stat_definition_id=self.denominator_stat_definition_id,
                constant=self.denominator_constant,
            ),
            multiplier=self.multiplier,
            offset=self.offset,
            round_mode=self.round_mode,
        )


class SelectResultBody(BaseModel):
    """What a select gives: exactly one of a number, a text, a flag (a bool), or a stat of the
    same entity - ADR 0446. A stat is for a numeric target, and a constant is of the target's
    type."""

    number: Decimal | None = None
    text: str | None = None
    flag: bool | None = None
    stat_definition_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> SelectResultBody:
        given = [
            v for v in (self.number, self.text, self.flag, self.stat_definition_id) if v is not None
        ]
        if len(given) != 1:
            raise ValueError("a result is exactly one of number, text, flag or stat_definition_id")
        return self

    def to_result(self) -> SelectResult:
        return SelectResult(
            number=self.number,
            text=self.text,
            flag=self.flag,
            stat_definition_id=self.stat_definition_id,
        )

    @classmethod
    def of(cls, result: SelectResult) -> SelectResultBody:
        return cls(
            number=result.number,
            text=result.text,
            flag=result.flag,
            stat_definition_id=result.stat_definition_id,
        )


class SelectStepBody(BaseModel):
    """One step of a select: in `threshold` mode a `from` value, in `match` mode a `value`, and
    the result - ADR 0446."""

    model_config = ConfigDict(populate_by_name=True)

    from_: Decimal | None = Field(default=None, alias="from")
    value: str | None = None
    result: SelectResultBody


class SelectFormulaBody(BaseModel):
    """A value from a table - ADR 0446. `threshold`: the source is a number (a `bool` is 1 or 0, an
    `enum` its `sort_order`) and the result is that of the highest `from` it reaches; the
    `from` values rise. `match`: the source is a `text` or an `enum` and the result is that of the
    step whose `value` it holds; the values differ. `otherwise` is the result when none
    applies, no value without it. One to 64 steps."""

    model_config = ConfigDict(populate_by_name=True)

    kind: Literal["select"] = "select"
    source_stat_definition_id: uuid.UUID
    mode: Literal["threshold", "match"]
    steps: list[SelectStepBody] = Field(min_length=1, max_length=MAX_SELECT_STEPS)
    otherwise: SelectResultBody | None = None

    @model_validator(mode="after")
    def _steps_fit_the_mode(self) -> SelectFormulaBody:
        for step in self.steps:
            if self.mode == "threshold" and (step.from_ is None or step.value is not None):
                raise ValueError("a threshold step has a from and no value")
            if self.mode == "match" and (step.value is None or step.from_ is not None):
                raise ValueError("a match step has a value and no from")
        return self

    def to_formula(self) -> SelectFormula:
        return SelectFormula(
            source=self.source_stat_definition_id,
            mode=self.mode,
            steps=tuple(
                SelectStep(
                    threshold=step.from_, match_value=step.value, result=step.result.to_result()
                )
                for step in self.steps
            ),
            otherwise=None if self.otherwise is None else self.otherwise.to_result(),
        )


AnyFormulaBody = (
    LinearFormulaBody
    | ComparisonFormulaBody
    | SumFormulaBody
    | ContentsFormulaBody
    | MinFormulaBody
    | MaxFormulaBody
    | ProductFormulaBody
    | RatioFormulaBody
    | SelectFormulaBody
)
FormulaBody = Annotated[AnyFormulaBody, Field(discriminator="kind")]


def formula_body_of(formula: Formula) -> AnyFormulaBody:
    if isinstance(formula, LinearFormula):
        return LinearFormulaBody(
            source_stat_definition_id=formula.source_stat_definition_id,
            multiplier=formula.multiplier,
            offset=formula.offset,
            round_mode=formula.round_mode,
        )
    if isinstance(formula, ContentsFormula):
        return ContentsFormulaBody(
            source_stat_definition_id=formula.source_stat_definition_id,
            aggregate=formula.aggregate,
            only_active=formula.only_active,
            only_kind=formula.only_kind,
            where_stat_definition_id=formula.where_stat_definition_id,
            if_none=formula.if_none,
        )
    if isinstance(formula, SelectFormula):
        return SelectFormulaBody(
            source_stat_definition_id=formula.source,
            mode=formula.mode,
            steps=[
                SelectStepBody(
                    from_=step.threshold,
                    value=step.match_value,
                    result=SelectResultBody.of(step.result),
                )
                for step in formula.steps
            ],
            otherwise=None if formula.otherwise is None else SelectResultBody.of(formula.otherwise),
        )
    if isinstance(formula, ProductFormula):
        return ProductFormulaBody(
            factors=list(formula.factors),
            multiplier=formula.multiplier,
            offset=formula.offset,
            round_mode=formula.round_mode,
        )
    if isinstance(formula, RatioFormula):
        return RatioFormulaBody(
            numerator_stat_definition_id=formula.numerator,
            denominator_stat_definition_id=formula.denominator.stat_definition_id,
            denominator_constant=formula.denominator.constant,
            multiplier=formula.multiplier,
            offset=formula.offset,
            round_mode=formula.round_mode,
        )
    if isinstance(formula, ExtremumFormula):
        inputs = [
            ExtremumInputBody(stat_definition_id=o.stat_definition_id, constant=o.constant)
            for o in formula.inputs
        ]
        extremum_body = MinFormulaBody if formula.pick == "min" else MaxFormulaBody
        return extremum_body(inputs=inputs, round_mode=formula.round_mode)
    if isinstance(formula, SumFormula):
        return SumFormulaBody(
            terms=[
                SumTermBody(
                    stat_definition_id=term.source_stat_definition_id,
                    coefficient=term.coefficient,
                )
                for term in formula.terms
            ],
            offset=formula.offset,
            round_mode=formula.round_mode,
        )
    return ComparisonFormulaBody(
        left_stat_definition_id=formula.left_stat_definition_id,
        comparator=formula.comparator,
        right_stat_definition_id=formula.right_stat_definition_id,
        right_constant=formula.right_constant,
        true_value=formula.true_value,
        false_value=formula.false_value,
    )


class ComputedStatOut(BaseModel):
    """One formula an entity holds itself - ADR 0104. `updated_at` is the
    If-Match source for replacing or deleting it."""

    entity_id: uuid.UUID
    stat_definition_id: uuid.UUID
    formula: FormulaBody
    updated_at: datetime

    @classmethod
    def from_row(cls, row: ComputedStat, formula: Formula) -> ComputedStatOut:
        return cls(
            entity_id=row.entity_id,
            stat_definition_id=row.stat_definition_id,
            formula=formula_body_of(formula),
            updated_at=row.updated_at,
        )


class ComputedStatPreviewIn(BaseModel):
    """POST .../computed-stats/{id}/preview - an unsaved formula to try, or
    nothing to evaluate whatever currently resolves (ADR 0104)."""

    formula: FormulaBody | None = None


class PreviewInputOut(BaseModel):
    stat_definition_id: uuid.UUID
    name: str
    value: int | float | str | bool | None


class ComputedStatPreviewOut(BaseModel):
    """What a stat evaluates to on one entity, without saving anything.
    `source` is `computed` (a formula - the candidate, if one was sent),
    `direct` (a stored value wins), or `unset`. `inputs` are the values
    the formula read, empty unless computed."""

    stat_definition_id: uuid.UUID
    value: int | float | str | bool | None
    source: Literal["computed", "direct", "unset"]
    inputs: list[PreviewInputOut]


class ContentsExplanationOut(BaseModel):
    """What a contents formula counted (ADR 0276): the things directly
    inside it took (after its options, ADR 0447), not one input per thing. The total is the
    stat's own `value`. The stat is empty for a `count`."""

    source_stat_definition_id: uuid.UUID | None
    source_name: str | None
    things: int


class PickedExplanationOut(BaseModel):
    """The input a `min` or a `max` took (ADR 0444): the stat (null for a constant) and the number
    it counted as, the first of several that tie."""

    position: int
    stat_definition_id: uuid.UUID | None
    name: str | None
    value: int | float | str | bool | None


class ChosenStepExplanationOut(BaseModel):
    """The step a select took (ADR 0446): its position and key (a `from` or a value), or that none
    applied and `otherwise` gave the result."""

    position: int | None
    otherwise: bool
    key: int | float | str | None


class StatExplanationOut(BaseModel):
    """How an entity's stat came to have its value, for any participant who
    may read the entity (ADR 0276). `formula` is the winning formula, held by
    this entity or inherited (see `from_entity`), null for a stored value;
    `inputs` are the values it read. A contents formula has no inputs of its
    own: `contents` says what it counted instead. A `min` or `max` says which
    input it took in `picked`."""

    stat_definition_id: uuid.UUID
    # ADR 0448: the group of the stat and the slug of that group's game system, null when neutral.
    group_id: uuid.UUID
    system: str | None = None
    name: str
    value: int | float | str | bool
    own: bool
    computed: bool
    from_entity: EntitySummary | None
    # Inherited from an entry the caller may not see (a hidden entry, ADR 0437): true, else null.
    from_hidden: bool | None = None
    formula: FormulaBody | None
    inputs: list[PreviewInputOut]
    contents: ContentsExplanationOut | None
    picked: PickedExplanationOut | None = None
    # A ratio: whether its division lost digits at 28 (ADR 0445), else null.
    division_rounded: bool | None = None
    # A select: the step it took (ADR 0446), else null.
    chosen: ChosenStepExplanationOut | None = None


class ComputedStatDependentOut(BaseModel):
    """One formula that reads a given stat (ADR 0104's reverse lookup)."""

    entity_id: uuid.UUID
    stat_definition_id: uuid.UUID
    kind: Literal[
        "linear", "comparison", "sum", "contents", "min", "max", "product", "ratio", "select"
    ]
