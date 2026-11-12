import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, Field, model_validator

__all__ = [
    "ComparisonIn",
    "ComparisonOut",
    "ConditionIn",
    "ConditionOut",
    "GrantRuleIn",
    "GrantRuleOut",
    "GrantRuleUpdate",
    "PrerequisitesIn",
    "PrerequisitesOut",
    "RuleOptionOut",
]

Comparator = Literal["lt", "le", "eq", "ne", "ge", "gt"]


class ComparisonIn(BaseModel):
    """One comparison, `stat <comparator> right`, with right a constant or another stat of the
    same entry (ADR 0455): a feature's prerequisite, read on the holder. The stat is a number, a
    bool or an enum, read as a number as the `comparison` formula reads it (ADR 0444)."""

    stat_definition_id: uuid.UUID
    comparator: Comparator
    right_constant: Decimal | None = None
    right_stat_definition_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _one_right_side(self) -> Self:
        if (self.right_constant is None) == (self.right_stat_definition_id is None):
            raise ValueError("Give one right side: right_constant or right_stat_definition_id")
        return self


class ConditionIn(ComparisonIn):
    """A condition of a rule: a comparison, read on the holder or on the source."""

    subject: Literal["holder", "source"] = "holder"


class GrantRuleBody(BaseModel):
    """What a rule says (ADR 0455). `mode` `all` grants every option; `choose` lets the holder pick
    between `min_count` (0 by default) and a maximum, which is `max_count` or, with
    `count_stat_definition_id`, that stat of the holder read when the rule is applied. The options
    are an explicit list of features, or `option_category_entry_id`, the features under that entry,
    not both. All the conditions must hold. `lasts` says whether a grant ends with its source
    (`while_source`) or stays (`permanent`);
    `changeable` is for a choose rule, whose pick the holder
    may swap."""

    label: str | None = None
    mode: Literal["all", "choose"]
    min_count: int = Field(default=0, ge=0)
    max_count: int | None = Field(default=None, ge=1)
    count_stat_definition_id: uuid.UUID | None = None
    option_category_entry_id: uuid.UUID | None = None
    options: list[uuid.UUID] = []
    lasts: Literal["while_source", "permanent"] = "while_source"
    changeable: bool = False
    conditions: list[ConditionIn] = []

    @model_validator(mode="after")
    def _shape(self) -> Self:
        if self.mode == "all":
            if (
                self.min_count
                or self.max_count is not None
                or self.count_stat_definition_id is not None
            ):
                raise ValueError("An `all` rule has no count: leave min_count and the maximum out")
            if self.changeable:
                raise ValueError("`changeable` is for a choose rule")
        else:
            if (self.max_count is None) == (self.count_stat_definition_id is None):
                raise ValueError(
                    "A choose rule needs one maximum: max_count or count_stat_definition_id"
                )
            if self.max_count is not None and self.min_count > self.max_count:
                raise ValueError("min_count is more than max_count")
        if self.option_category_entry_id is not None and self.options:
            raise ValueError("Name the options or a category entry, not both")
        if self.option_category_entry_id is None and not self.options:
            raise ValueError("A rule needs options or a category entry")
        if len(set(self.options)) != len(self.options):
            raise ValueError("An option is named twice")
        return self


class GrantRuleIn(GrantRuleBody):
    """POST /grant-rules: a rule on a source entry, appended after the entry's others unless
    `position` places it."""

    entry_id: uuid.UUID
    position: int | None = Field(default=None, ge=0)


class GrantRuleUpdate(GrantRuleBody):
    """PUT /grant-rules/{id}: the rule replaced, its source kept; `position` moves it among the
    source's rules (left out, it stays)."""

    position: int | None = Field(default=None, ge=0)


class PrerequisitesIn(BaseModel):
    """PUT .../features/prototypes/{feature}/prerequisites: the complete list, in order; empty
    clears it."""

    prerequisites: list[ComparisonIn] = []


class ComparisonOut(BaseModel):
    stat_definition_id: uuid.UUID
    stat_name: str
    comparator: Comparator
    right_constant: Decimal | None
    right_stat_definition_id: uuid.UUID | None
    right_stat_name: str | None


class ConditionOut(ComparisonOut):
    subject: Literal["holder", "source"]


class RuleOptionOut(BaseModel):
    """An option or a category of a rule. An entry the library hides (ADR 0437) is offered as `a
    hidden entry`, with no id (ADR 0454)."""

    id: uuid.UUID | None
    name: str
    hidden: bool = False


class GrantRuleOut(BaseModel):
    """A rule as the vocabulary reads it (ADR 0455)."""

    id: uuid.UUID
    entry_id: uuid.UUID
    entry_name: str
    label: str | None
    position: int
    mode: Literal["all", "choose"]
    min_count: int
    max_count: int | None
    count_stat_definition_id: uuid.UUID | None
    count_stat_name: str | None
    option_category: RuleOptionOut | None
    options: list[RuleOptionOut]
    lasts: Literal["while_source", "permanent"]
    changeable: bool
    conditions: list[ConditionOut]
    created_at: datetime
    updated_at: datetime


class PrerequisitesOut(BaseModel):
    """A feature's prerequisites, in order."""

    feature_id: uuid.UUID
    prerequisites: list[ComparisonOut]
