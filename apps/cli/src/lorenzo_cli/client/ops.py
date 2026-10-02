"""The operations the CLI calls (ADR 0137): `operationId` to method, path and models.

A test checks every entry against apps/api's dumped OpenAPI document, which gives the
path-level safety packages/api-client gets from its generated types. Add an operation here when
a command first needs it, not before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter

from lorenzo_cli.client.models import (
    ComparisonFormulaBodyInput,
    ComputedStatOut,
    ContentsFormulaBody,
    EntityDetailOut,
    GivePackRequest,
    InformationCreate,
    InformationOut,
    ItemCreate,
    ItemInstanceCreate,
    ItemInstanceOut,
    ItemOut,
    LinearFormulaBodyInput,
    PackGivenOut,
    PageStatDefinitionOut,
    PageStatGroupOut,
    PageTenantSummaryOut,
    ResolvedSlugOut,
    SetEntityStatRequest,
    SetPrototypesRequest,
    StatDefinitionCreate,
    StatDefinitionOut,
    StatGroupCreate,
    StatGroupOut,
    SumFormulaBodyInput,
    TenantCreate,
    TenantOut,
)

# What PUT .../computed-stats/{id} accepts: the formula itself, of any kind.
ComputedStatBody = (
    LinearFormulaBodyInput | ComparisonFormulaBodyInput | SumFormulaBodyInput | ContentsFormulaBody
)


@dataclass(frozen=True)
class Op[T]:
    """One API operation. `request_type` is a model class or a union of them, `response_type` a
    model class, `list[Model]`, or None (no body)."""

    operation_id: str
    method: str
    path: str
    request_type: Any = None
    response_type: Any = None
    adapter: TypeAdapter[T] | None = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.response_type is not None:
            object.__setattr__(self, "adapter", TypeAdapter(self.response_type))


_TENANT = "/tenants/{tenant_id}"

GET_TENANT: Op[TenantOut] = Op("get_tenant", "GET", _TENANT, response_type=TenantOut)
LIST_TENANTS: Op[PageTenantSummaryOut] = Op(
    "list_tenants", "GET", "/tenants", response_type=PageTenantSummaryOut
)
CREATE_TENANT: Op[TenantOut] = Op(
    "create_tenant", "POST", "/tenants", request_type=TenantCreate, response_type=TenantOut
)

LIST_STAT_GROUPS: Op[PageStatGroupOut] = Op(
    "list_stat_groups", "GET", f"{_TENANT}/stat-groups", response_type=PageStatGroupOut
)
CREATE_STAT_GROUP: Op[StatGroupOut] = Op(
    "create_stat_group",
    "POST",
    f"{_TENANT}/stat-groups",
    request_type=StatGroupCreate,
    response_type=StatGroupOut,
)
LIST_STAT_DEFINITIONS: Op[PageStatDefinitionOut] = Op(
    "list_stat_definitions",
    "GET",
    f"{_TENANT}/stat-definitions",
    response_type=PageStatDefinitionOut,
)
CREATE_STAT_DEFINITION: Op[StatDefinitionOut] = Op(
    "create_stat_definition",
    "POST",
    f"{_TENANT}/stat-definitions",
    request_type=StatDefinitionCreate,
    response_type=StatDefinitionOut,
)

RESOLVE_SLUGS: Op[list[ResolvedSlugOut]] = Op(
    "resolve_slugs", "GET", f"{_TENANT}/entities/resolve", response_type=list[ResolvedSlugOut]
)
GET_ITEM: Op[ItemOut] = Op(
    "get_item", "GET", f"{_TENANT}/items/{{entity_id}}", response_type=ItemOut
)
CREATE_ITEM: Op[ItemOut] = Op(
    "create_item", "POST", f"{_TENANT}/items", request_type=ItemCreate, response_type=ItemOut
)
SET_ENTITY_TAG: Op[EntityDetailOut] = Op(
    "set_entity_tag",
    "PUT",
    f"{_TENANT}/entities/{{entity_id}}/tags/{{stat_definition_id}}",
    response_type=EntityDetailOut,
)
LIST_ENTITY_COMPUTED_STATS: Op[list[ComputedStatOut]] = Op(
    "list_entity_computed_stats",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/computed-stats",
    response_type=list[ComputedStatOut],
)
SET_COMPUTED_STAT: Op[ComputedStatOut] = Op(
    "set_computed_stat",
    "PUT",
    f"{_TENANT}/entities/{{entity_id}}/computed-stats/{{stat_definition_id}}",
    request_type=ComputedStatBody,
    response_type=ComputedStatOut,
)

GET_ENTITY: Op[EntityDetailOut] = Op(
    "get_entity", "GET", f"{_TENANT}/entities/{{entity_id}}", response_type=EntityDetailOut
)
SET_ENTITY_STAT: Op[EntityDetailOut] = Op(
    "set_entity_stat",
    "PUT",
    f"{_TENANT}/entities/{{entity_id}}/stats/{{stat_definition_id}}",
    request_type=SetEntityStatRequest,
    response_type=EntityDetailOut,
)
CREATE_INFORMATION: Op[InformationOut] = Op(
    "create_information",
    "POST",
    f"{_TENANT}/entities/{{entity_id}}/information",
    request_type=InformationCreate,
    response_type=InformationOut,
)
CREATE_ITEM_INSTANCE: Op[ItemInstanceOut] = Op(
    "create_item_instance",
    "POST",
    f"{_TENANT}/item-instances",
    request_type=ItemInstanceCreate,
    response_type=ItemInstanceOut,
)
CREATE_ITEM_INSTANCES_FROM_PACK: Op[PackGivenOut] = Op(
    "create_item_instances_from_pack",
    "POST",
    f"{_TENANT}/item-instances/from-pack",
    request_type=GivePackRequest,
    response_type=PackGivenOut,
)
REPLACE_ITEM_PROTOTYPES: Op[ItemOut] = Op(
    "replace_item_prototypes",
    "PUT",
    f"{_TENANT}/items/{{entity_id}}/prototypes",
    request_type=SetPrototypesRequest,
    response_type=ItemOut,
)

ALL_OPS: tuple[Op[Any], ...] = (
    GET_TENANT,
    LIST_TENANTS,
    CREATE_TENANT,
    LIST_STAT_GROUPS,
    CREATE_STAT_GROUP,
    LIST_STAT_DEFINITIONS,
    CREATE_STAT_DEFINITION,
    RESOLVE_SLUGS,
    GET_ITEM,
    CREATE_ITEM,
    SET_ENTITY_TAG,
    LIST_ENTITY_COMPUTED_STATS,
    SET_COMPUTED_STAT,
    GET_ENTITY,
    SET_ENTITY_STAT,
    CREATE_INFORMATION,
    REPLACE_ITEM_PROTOTYPES,
    CREATE_ITEM_INSTANCE,
    CREATE_ITEM_INSTANCES_FROM_PACK,
)
