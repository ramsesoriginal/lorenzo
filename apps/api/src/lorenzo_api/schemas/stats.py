from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from lorenzo_api.models import StatDefinition, StatValueType

__all__ = [
    "SetEntityStatRequest",
    "StatDefinitionCreate",
    "StatDefinitionOrder",
    "StatDefinitionOut",
    "StatDefinitionUpdate",
    "StatEnumValueCreate",
    "StatGroupCreate",
    "StatGroupOrder",
    "StatGroupOut",
    "StatGroupUpdate",
]

# ADR 0278: a unit is a few characters ("ft", "lb", "in.").
UnitText = Annotated[str, Field(min_length=1, max_length=32)]


class StatGroupCreate(BaseModel):
    """POST /stat-groups - see ADR 0037/RFC 0008. Tenant-admin tier
    (get_tenant_context), the same authorization ADR 0032 already
    established for item catalog CRUD - authoring the shared stat
    vocabulary is the identical kind of concern.
    """

    name: str
    priority: int = 0
    # Display-only (ADR 0103): a client shows this group's fields even when
    # empty. Nothing checks they're filled in.
    mandatory: bool = False
    # Where it comes in the vocabulary (ADR 0278); omitted, it goes last.
    position: int | None = None


class StatGroupUpdate(BaseModel):
    """PATCH /stat-groups/{id} - ADR 0278. Merge-patch semantics
    (`exclude_unset`): an omitted field is left alone, and none of these can
    be cleared to null."""

    name: str | None = None
    priority: int | None = None
    mandatory: bool | None = None
    position: int | None = None

    @model_validator(mode="after")
    def _no_nulls(self) -> StatGroupUpdate:
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class StatGroupOrder(BaseModel):
    """PUT /stat-groups/order - every group of the tenant, once each, in the
    order they should come in (ADR 0278)."""

    stat_group_ids: list[uuid.UUID]


class StatDefinitionOrder(BaseModel):
    """PUT /stat-groups/{id}/order - every definition of the group, once
    each, in the order they should come in (ADR 0278)."""

    stat_definition_ids: list[uuid.UUID]


class StatGroupOut(BaseModel):
    """Constructed via .model_validate(stat_group) at call sites - every
    field here is a plain 1:1 column copy, so from_attributes=True already
    does the whole job; no wrapper classmethod needed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    priority: int
    mandatory: bool
    position: int
    created_at: datetime
    updated_at: datetime


class StatDefinitionCreate(BaseModel):
    """POST /stat-definitions - see ADR 0037/RFC 0008. Same tenant-admin
    tier as StatGroupCreate. stat_group_id must resolve to a stat group in
    this tenant (422 InvalidStatGroupError otherwise).
    """

    name: str
    stat_group_id: uuid.UUID
    value_type: StatValueType
    # Required and non-empty for value_type=enum, absent or empty otherwise
    # (ADR 0103). List position becomes each value's sort_order.
    enum_values: list[str] | None = None
    # How the stat is shown (ADR 0278). None of it limits or changes a value.
    unit: UnitText | None = None
    adjustable_in_play: bool = False
    pin: bool = False
    signed: bool = False
    # Where it comes in its group; omitted, it goes last.
    position: int | None = None
    # Clues, each another definition of the tenant (ADR 0279).
    max_hint_id: uuid.UUID | None = None
    min_hint_id: uuid.UUID | None = None
    resolved_hint_id: uuid.UUID | None = None


class StatDefinitionUpdate(BaseModel):
    """PATCH /stat-definitions/{id} - ADR 0278. Merge-patch semantics
    (`exclude_unset`); `unit` may be set to null to clear it. A definition's
    name, type and group are not editable here."""

    unit: UnitText | None = None
    adjustable_in_play: bool | None = None
    pin: bool | None = None
    signed: bool | None = None
    position: int | None = None
    # Each hint may be set to null to clear it (ADR 0279).
    max_hint_id: uuid.UUID | None = None
    min_hint_id: uuid.UUID | None = None
    resolved_hint_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _no_nulls(self) -> StatDefinitionUpdate:
        clearable = {"unit", "max_hint_id", "min_hint_id", "resolved_hint_id"}
        for field in self.model_fields_set - clearable:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class StatDefinitionOut(BaseModel):
    """Built via from_definition: `enum_values` flattens the
    StatDefinitionEnumValue rows (already ordered by sort_order, value) to
    their plain strings. Requires stat_definition.enum_values loaded.
    """

    id: uuid.UUID
    name: str
    stat_group_id: uuid.UUID
    value_type: StatValueType
    # The allowed values of an enum stat, in display order; empty for any
    # other type (ADR 0103).
    enum_values: list[str]
    # How the stat is shown, and where it comes in its group (ADR 0278).
    unit: str | None
    adjustable_in_play: bool
    pin: bool
    signed: bool
    position: int
    # Clues for a sheet (ADR 0279): other definitions of the tenant, or null.
    max_hint_id: uuid.UUID | None
    min_hint_id: uuid.UUID | None
    resolved_hint_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_definition(cls, stat_definition: StatDefinition) -> StatDefinitionOut:
        return cls(
            id=stat_definition.id,
            name=stat_definition.name,
            stat_group_id=stat_definition.stat_group_id,
            value_type=stat_definition.value_type,
            enum_values=[row.value for row in stat_definition.enum_values],
            unit=stat_definition.unit,
            adjustable_in_play=stat_definition.adjustable_in_play,
            pin=stat_definition.pin,
            signed=stat_definition.signed,
            position=stat_definition.position,
            max_hint_id=stat_definition.max_hint_id,
            min_hint_id=stat_definition.min_hint_id,
            resolved_hint_id=stat_definition.resolved_hint_id,
            created_at=stat_definition.created_at,
            updated_at=stat_definition.updated_at,
        )


class StatEnumValueCreate(BaseModel):
    """POST .../stat-definitions/{id}/enum-values - see ADR 0103. An
    omitted sort_order places the value after the last one.
    """

    value: str
    sort_order: int | None = None


class SetEntityStatRequest(BaseModel):
    """PUT /tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}
    - see ADR 0037/RFC 0008. `value`'s Python type must match the target
    stat_definition's declared value_type exactly (int/str/float/bool, no
    int<->float coercion; an `enum` stat takes a string that must be one of
    its allowed values, ADR 0103) - checked explicitly by the route
    (422 InvalidStatValueTypeError otherwise), not left to entity_stat's own
    CHECK constraint (which only enforces "exactly one value_* column is
    set," not which one).
    `acquire_group` (ADR 0142) also adds the stat's group to the entity, as the tag
    routes do; off by default, so nothing changes for a caller that doesn't ask.
    """

    value: int | str | float | bool
    acquire_group: bool = False
