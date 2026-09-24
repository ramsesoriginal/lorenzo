from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import StatDefinition, StatValueType

__all__ = [
    "SetEntityStatRequest",
    "StatDefinitionCreate",
    "StatDefinitionOut",
    "StatEnumValueCreate",
    "StatGroupCreate",
    "StatGroupOut",
]


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
    """

    value: int | str | float | bool
