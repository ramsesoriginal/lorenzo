from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from lorenzo_api.models import StatValueType

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
    """Constructed via .model_validate(stat_group) at call sites - every
    field here is a plain 1:1 column copy, so from_attributes=True already
    does the whole job; no wrapper classmethod needed.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    priority: int
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


class StatDefinitionOut(BaseModel):
    """Constructed via .model_validate(stat_definition) at call sites - same
    reasoning as StatGroupOut above.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    stat_group_id: uuid.UUID
    value_type: StatValueType
    created_at: datetime
    updated_at: datetime


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
