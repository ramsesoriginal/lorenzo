from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import EntityKind, EntityStatValueOut, InformationOut

__all__ = [
    "HeldOrder",
    "SlotKind",
    "TemplateCellOut",
    "TemplateColumnOut",
    "TemplateFeatureGroupOut",
    "TemplateFeatureRowOut",
    "TemplateHeldRowOut",
    "TemplateIn",
    "TemplateOut",
    "TemplateSlotIn",
    "TemplateSlotOut",
    "TemplateSlotStatOut",
    "TemplateStatIn",
    "TemplateStatOut",
    "TemplateSummaryOut",
    "TemplateViewOut",
    "TemplateViewSlotOut",
]

SlotKind = Literal["stats", "information", "held", "tags", "features"]
HeldOrder = Literal["name", "prototype"]
LabelText = Annotated[str, Field(min_length=1, max_length=200)]


class TemplateStatIn(BaseModel):
    """A stat a slot lists, with the label it is shown under (the stat's own name when left out)."""

    stat_definition_id: uuid.UUID
    label: LabelText | None = None


class TemplateSlotIn(BaseModel):
    """One block of a template (ADR 0451). By `kind`:

    - `stats`: a stat group (`stat_group_id`, with `exclude` for the stats of it to leave out) or an
      ordered list (`stats`), one of the two.
    - `held`: the things the entry holds, a column for each stat of a group or a list, as `stats`;
      `held_order` is `name` (the default) or `prototype` (by the name of the thing's prototype,
      then its name).
    - `features`: the features the entry holds, grouped by type, a column for each stat of a group
      or a list, as `held` has them (ADR 0457).
    - `information`: the entry's notes of `information_type`.
    - `tags`: the `bool` stats that are true, of `stat_group_id` or, left out, of any group.
    """

    kind: SlotKind
    label: LabelText | None = None
    stat_group_id: uuid.UUID | None = None
    stats: list[TemplateStatIn] = Field(default_factory=list, max_length=200)
    exclude: list[uuid.UUID] = Field(default_factory=list, max_length=200)
    information_type: Annotated[str, Field(min_length=1, max_length=200)] | None = None
    held_order: HeldOrder | None = None

    @model_validator(mode="after")
    def _fits_its_kind(self) -> Self:
        kind = self.kind
        if kind in ("stats", "held", "features"):
            if (self.stat_group_id is None) == (not self.stats):
                raise ValueError(f"a {kind} slot has a stat group or a list of stats, one of them")
            if self.exclude and self.stat_group_id is None:
                raise ValueError("exclude leaves stats out of a group, so it needs stat_group_id")
            if self.information_type is not None:
                raise ValueError(f"a {kind} slot has no information_type")
        elif kind == "information":
            if self.information_type is None:
                raise ValueError("an information slot needs information_type")
            if self.stat_group_id is not None or self.stats or self.exclude:
                raise ValueError("an information slot has no stats")
        else:  # tags
            if self.stats or self.exclude or self.information_type is not None:
                raise ValueError("a tags slot has at most a stat group")
        if kind == "held":
            if self.held_order is None:
                self.held_order = "name"
        elif self.held_order is not None:
            raise ValueError("held_order is for a held slot")
        return self


class TemplateIn(BaseModel):
    """POST and PUT /templates (ADR 0451, RFC 0052). The filter is the kind and the ancestor entry
    the template is for, both optional and applied together; `system_id` only names its game
    system, for a campaign that picks templates by system. A PUT replaces the whole template,
    its slots included."""

    name: LabelText
    system_id: uuid.UUID | None = None
    required_kind: EntityKind | None = None
    required_ancestor_entry_id: uuid.UUID | None = None
    slots: list[TemplateSlotIn] = Field(default_factory=list, max_length=50)


class TemplateSlotStatOut(BaseModel):
    stat_definition_id: uuid.UUID
    label: str | None


class TemplateSlotOut(BaseModel):
    """A slot as written, in its position."""

    id: uuid.UUID
    position: int
    kind: SlotKind
    label: str | None
    stat_group_id: uuid.UUID | None
    stats: list[TemplateSlotStatOut]
    exclude: list[uuid.UUID]
    information_type: str | None
    held_order: HeldOrder | None


class TemplateOut(BaseModel):
    """A template of the library (ADR 0451)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    system_id: uuid.UUID | None
    # The slug of its system, null when it has none.
    system: str | None
    required_kind: EntityKind | None
    required_ancestor_entry_id: uuid.UUID | None
    slots: list[TemplateSlotOut]
    created_at: datetime
    updated_at: datetime


class TemplateSummaryOut(BaseModel):
    """A template in a list: what it is for, without its slots."""

    id: uuid.UUID
    name: str
    system_id: uuid.UUID | None
    system: str | None
    required_kind: EntityKind | None
    required_ancestor_entry_id: uuid.UUID | None


class TemplateStatOut(EntityStatValueOut):
    """A stat of a `stats` slot: the value as the entry's own read gives it, the label the slot
    shows it under (the stat's name when the slot sets none) and its unit."""

    label: str
    unit: str | None = None


class TemplateColumnOut(BaseModel):
    """A column of a `held` slot: a stat, its label and unit."""

    stat_definition_id: uuid.UUID
    name: str
    label: str
    unit: str | None = None


class TemplateCellOut(BaseModel):
    """One cell of a held row, in the order of the columns: the typed value, or null when the
    thing has none."""

    stat_definition_id: uuid.UUID
    value: int | str | float | bool | None = None


class TemplateHeldRowOut(BaseModel):
    """One thing the entry holds: it, its quantity and a cell for each column."""

    entity: EntitySummary
    quantity: int | None
    cells: list[TemplateCellOut]


class TemplateFeatureRowOut(BaseModel):
    """One feature the entry has: the instance, the feature, its switch and a cell for each column
    (ADR 0457)."""

    id: uuid.UUID
    name: str
    feature: EntitySummary
    active: bool
    cells: list[TemplateCellOut]


class TemplateFeatureGroupOut(BaseModel):
    """The features of one type (the first category entry among a feature's parents), by name; the
    group of the features with no type has none, and comes last (ADR 0457)."""

    type: EntitySummary | None
    features: list[TemplateFeatureRowOut]


class TemplateViewSlotOut(BaseModel):
    """A slot of the assembled view, in its position. Only the fields of its kind are filled:
    `stats` for a stats slot, `columns` and `rows` for a held slot, `columns` and `feature_groups`
    for a features slot, `information` for an information slot, `tags` for a tags slot. A slot the
    caller may not read is left out of the view."""

    position: int
    kind: SlotKind
    label: str | None
    stats: list[TemplateStatOut] | None = None
    information: list[InformationOut] | None = None
    columns: list[TemplateColumnOut] | None = None
    rows: list[TemplateHeldRowOut] | None = None
    feature_groups: list[TemplateFeatureGroupOut] | None = None
    tags: list[TemplateStatOut] | None = None


class TemplateViewOut(BaseModel):
    """GET /entities/{id}/templates/{template_id}: the entry as the template shows it, an
    ordered array of slots (ADR 0451)."""

    template: TemplateSummaryOut
    entity: EntitySummary
    slots: list[TemplateViewSlotOut]
