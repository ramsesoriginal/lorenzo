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
    ApplyUpdatesOut,
    ApplyUpdatesRequest,
    ComparisonFormulaBodyInput,
    ComputedStatOut,
    ContentsFormulaBody,
    CopyOut,
    CopyPlanOut,
    CopyRequest,
    EntityDetailOut,
    GivePackRequest,
    InformationCreate,
    InformationOut,
    InformationUpdate,
    ItemCreate,
    ItemInstanceCreate,
    ItemInstanceOut,
    ItemOut,
    LinearFormulaBodyInput,
    MeOut,
    OwnedByResponse,
    PackGivenOut,
    PageAttachmentRefOut,
    PageCharacterSummaryOut,
    PageInformationOut,
    PageItemOut,
    PageStatDefinitionOut,
    PageStatGroupOut,
    PageSubscriberOut,
    PageSubscriptionOut,
    PageTenantSummaryOut,
    ResolvedSlugOut,
    SetContainerRequest,
    SetEntityStatRequest,
    SetPrototypesRequest,
    StatDefinitionCreate,
    StatDefinitionOut,
    StatGroupCreate,
    StatGroupOut,
    SubscriberOut,
    SumFormulaBodyInput,
    TenantCreate,
    TenantOut,
    UpdatesOut,
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

GET_ME: Op[MeOut] = Op("get_me", "GET", "/me", response_type=MeOut)
GET_TENANT: Op[TenantOut] = Op("get_tenant", "GET", _TENANT, response_type=TenantOut)
LIST_TENANTS: Op[PageTenantSummaryOut] = Op(
    "list_tenants", "GET", "/tenants", response_type=PageTenantSummaryOut
)
CREATE_TENANT: Op[TenantOut] = Op(
    "create_tenant", "POST", "/tenants", request_type=TenantCreate, response_type=TenantOut
)
DELETE_TENANT: Op[None] = Op("delete_tenant", "DELETE", _TENANT)

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
LIST_CHARACTERS: Op[PageCharacterSummaryOut] = Op(
    "list_characters", "GET", f"{_TENANT}/characters", response_type=PageCharacterSummaryOut
)
LIST_ITEMS: Op[PageItemOut] = Op("list_items", "GET", f"{_TENANT}/items", response_type=PageItemOut)
GET_ITEM: Op[ItemOut] = Op(
    "get_item", "GET", f"{_TENANT}/items/{{entity_id}}", response_type=ItemOut
)
DELETE_ITEM: Op[None] = Op("delete_item", "DELETE", f"{_TENANT}/items/{{entity_id}}")
DELETE_STAT_DEFINITION: Op[None] = Op(
    "delete_stat_definition", "DELETE", f"{_TENANT}/stat-definitions/{{stat_definition_id}}"
)
DELETE_STAT_GROUP: Op[None] = Op(
    "delete_stat_group", "DELETE", f"{_TENANT}/stat-groups/{{stat_group_id}}"
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
GET_INFORMATION: Op[InformationOut] = Op(
    "get_information",
    "GET",
    f"{_TENANT}/information/{{information_id}}",
    response_type=InformationOut,
)
UPDATE_INFORMATION: Op[InformationOut] = Op(
    "update_information",
    "PATCH",
    f"{_TENANT}/information/{{information_id}}",
    request_type=InformationUpdate,
    response_type=InformationOut,
)
CREATE_ITEM_INSTANCE: Op[ItemInstanceOut] = Op(
    "create_item_instance",
    "POST",
    f"{_TENANT}/item-instances",
    request_type=ItemInstanceCreate,
    response_type=ItemInstanceOut,
)
LIST_ENTITY_INFORMATION: Op[PageInformationOut] = Op(
    "list_entity_information",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/information",
    response_type=PageInformationOut,
)
ADD_INFORMATION_KNOWER: Op[InformationOut] = Op(
    "add_information_knower",
    "PUT",
    f"{_TENANT}/information/{{information_id}}/knowers/{{knower_entity_id}}",
    response_type=InformationOut,
)
LIST_ITEM_INSTANCES_OWNED_BY: Op[OwnedByResponse] = Op(
    "list_item_instances_owned_by",
    "GET",
    f"{_TENANT}/item-instances/owned-by/{{owner_entity_id}}",
    response_type=OwnedByResponse,
)
SET_ITEM_INSTANCE_CONTAINER: Op[ItemInstanceOut] = Op(
    "set_item_instance_container",
    "PUT",
    f"{_TENANT}/item-instances/{{entity_id}}/container",
    request_type=SetContainerRequest,
    response_type=ItemInstanceOut,
)
CLEAR_ITEM_INSTANCE_CONTAINER: Op[ItemInstanceOut] = Op(
    "clear_item_instance_container",
    "DELETE",
    f"{_TENANT}/item-instances/{{entity_id}}/container",
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

# A repository's own side (an owner publishes and grants) and a granted tenant's (any member
# lists, plans, copies and takes updates): ADR 0118 to 0121, the CLI's side in ADR 0159.
_REPOSITORY = f"{_TENANT}/repositories/{{repository_id}}"
PUBLISH_REPOSITORY: Op[TenantOut] = Op(
    "publish_repository", "PUT", f"{_TENANT}/published", response_type=TenantOut
)
UNPUBLISH_REPOSITORY: Op[TenantOut] = Op(
    "unpublish_repository", "DELETE", f"{_TENANT}/published", response_type=TenantOut
)
LIST_SUBSCRIBERS: Op[PageSubscriberOut] = Op(
    "list_subscribers", "GET", f"{_TENANT}/subscribers", response_type=PageSubscriberOut
)
GRANT_REPOSITORY: Op[SubscriberOut] = Op(
    "grant_repository",
    "PUT",
    f"{_TENANT}/subscribers/{{subscriber_tenant_id}}",
    response_type=SubscriberOut,
)
REVOKE_REPOSITORY: Op[None] = Op(
    "revoke_repository", "DELETE", f"{_TENANT}/subscribers/{{subscriber_tenant_id}}"
)
LIST_REPOSITORIES: Op[PageSubscriptionOut] = Op(
    "list_repositories", "GET", f"{_TENANT}/repositories", response_type=PageSubscriptionOut
)
LIST_ATTACHMENTS: Op[PageAttachmentRefOut] = Op(
    "list_attachments", "GET", f"{_TENANT}/attachments", response_type=PageAttachmentRefOut
)
PLAN_REPOSITORY_COPY: Op[CopyPlanOut] = Op(
    "plan_repository_copy", "GET", f"{_REPOSITORY}/copy-plan", response_type=CopyPlanOut
)
COPY_REPOSITORY: Op[CopyOut] = Op(
    "copy_repository",
    "POST",
    f"{_REPOSITORY}/copy",
    request_type=CopyRequest,
    response_type=CopyOut,
)
LIST_REPOSITORY_UPDATES: Op[UpdatesOut] = Op(
    "list_repository_updates", "GET", f"{_REPOSITORY}/updates", response_type=UpdatesOut
)
APPLY_REPOSITORY_UPDATES: Op[ApplyUpdatesOut] = Op(
    "apply_repository_updates",
    "POST",
    f"{_REPOSITORY}/updates",
    request_type=ApplyUpdatesRequest,
    response_type=ApplyUpdatesOut,
)

ALL_OPS: tuple[Op[Any], ...] = (
    GET_ME,
    GET_TENANT,
    LIST_TENANTS,
    CREATE_TENANT,
    DELETE_TENANT,
    LIST_STAT_GROUPS,
    CREATE_STAT_GROUP,
    LIST_STAT_DEFINITIONS,
    CREATE_STAT_DEFINITION,
    RESOLVE_SLUGS,
    LIST_CHARACTERS,
    LIST_ITEMS,
    GET_ITEM,
    DELETE_ITEM,
    DELETE_STAT_DEFINITION,
    DELETE_STAT_GROUP,
    CREATE_ITEM,
    SET_ENTITY_TAG,
    LIST_ENTITY_COMPUTED_STATS,
    SET_COMPUTED_STAT,
    GET_ENTITY,
    SET_ENTITY_STAT,
    CREATE_INFORMATION,
    GET_INFORMATION,
    UPDATE_INFORMATION,
    REPLACE_ITEM_PROTOTYPES,
    CREATE_ITEM_INSTANCE,
    LIST_ENTITY_INFORMATION,
    ADD_INFORMATION_KNOWER,
    LIST_ITEM_INSTANCES_OWNED_BY,
    SET_ITEM_INSTANCE_CONTAINER,
    CLEAR_ITEM_INSTANCE_CONTAINER,
    CREATE_ITEM_INSTANCES_FROM_PACK,
    PUBLISH_REPOSITORY,
    UNPUBLISH_REPOSITORY,
    LIST_SUBSCRIBERS,
    GRANT_REPOSITORY,
    REVOKE_REPOSITORY,
    LIST_REPOSITORIES,
    LIST_ATTACHMENTS,
    PLAN_REPOSITORY_COPY,
    COPY_REPOSITORY,
    LIST_REPOSITORY_UPDATES,
    APPLY_REPOSITORY_UPDATES,
)
