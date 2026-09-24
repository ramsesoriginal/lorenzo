from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from lorenzo_api.models import Comparator, ComputedStat, RoundMode
from lorenzo_api.stat_evaluation import ComparisonFormula, Formula, LinearFormula

__all__ = [
    "ComparisonFormulaBody",
    "ComputedStatDependentOut",
    "ComputedStatOut",
    "ComputedStatPreviewIn",
    "ComputedStatPreviewOut",
    "FormulaBody",
    "LinearFormulaBody",
    "PreviewInputOut",
]


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


FormulaBody = Annotated[LinearFormulaBody | ComparisonFormulaBody, Field(discriminator="kind")]


def formula_body_of(formula: Formula) -> LinearFormulaBody | ComparisonFormulaBody:
    if isinstance(formula, LinearFormula):
        return LinearFormulaBody(
            source_stat_definition_id=formula.source_stat_definition_id,
            multiplier=formula.multiplier,
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


class ComputedStatDependentOut(BaseModel):
    """One formula that reads a given stat (ADR 0104's reverse lookup)."""

    entity_id: uuid.UUID
    stat_definition_id: uuid.UUID
    kind: Literal["linear", "comparison"]
