from __future__ import annotations

import uuid
from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import StatDefinition, StatGroup, StatValueType

__all__ = [
    "SetEntityStatRequest",
    "StatDefinitionCreate",
    "StatDefinitionOut",
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


class StatGroupOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    priority: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_stat_group(cls, stat_group: StatGroup) -> Self:
        return cls(
            id=stat_group.id,
            name=stat_group.name,
            priority=stat_group.priority,
            created_at=stat_group.created_at,
            updated_at=stat_group.updated_at,
        )


class StatDefinitionCreate(BaseModel):
    """POST /stat-definitions - see ADR 0037/RFC 0008. Same tenant-admin
    tier as StatGroupCreate. stat_group_id must resolve to a stat group in
    this tenant (422 InvalidStatGroupError otherwise).
    """

    name: str
    stat_group_id: uuid.UUID
    value_type: StatValueType


class StatDefinitionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    stat_group_id: uuid.UUID
    value_type: StatValueType
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_stat_definition(cls, stat_definition: StatDefinition) -> Self:
        return cls(
            id=stat_definition.id,
            name=stat_definition.name,
            stat_group_id=stat_definition.stat_group_id,
            value_type=stat_definition.value_type,
            created_at=stat_definition.created_at,
            updated_at=stat_definition.updated_at,
        )


class SetEntityStatRequest(BaseModel):
    """PUT /tenants/{tenant_id}/entities/{entity_id}/stats/{stat_definition_id}
    - see ADR 0037/RFC 0008. `value`'s Python type must match the target
    stat_definition's declared value_type exactly (int/str/float/bool, no
    int<->float coercion) - checked explicitly by the route
    (422 InvalidStatValueTypeError otherwise), not left to entity_stat's own
    CHECK constraint (which only enforces "exactly one value_* column is
    set," not which one).
    """

    value: int | str | float | bool
