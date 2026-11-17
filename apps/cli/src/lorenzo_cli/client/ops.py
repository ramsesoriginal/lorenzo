"""The operations the CLI calls (ADR 0137): `operationId` to method, path and models.

A test checks every entry against apps/api's dumped OpenAPI document, which gives the
path-level safety packages/api-client gets from its generated types. Add an operation here when
a command first needs it, not before.

Models are named, not imported: the generated module is the largest the CLI loads, so it is
imported the first time an operation is called, not when a command group is (ADR 0483).
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from lorenzo_cli.client.models import (
        ApplyOut,
        ApplyUpdatesOut,
        CalendarDocumentOutput,
        CalendarImportPlan,
        CalendarImportReceipt,
        CampaignOut,
        ComparisonFormulaBodyInput,
        ComputedStatDependentOut,
        ComputedStatOut,
        ComputedStatPreviewOut,
        ContentsFormulaBodyInput,
        CopyOut,
        CopyPlanOut,
        DiceFormulaBody,
        DiceValueFormulaBody,
        EntityDetailOut,
        EntityExportPage,
        EntityStatWriteOut,
        FeatureColumnsOut,
        GrantRuleOut,
        GrantsOut,
        HeldFeatureOut,
        HeldFeaturesOut,
        InformationOut,
        ItemInstanceOut,
        ItemOut,
        LibraryCountOut,
        LinearFormulaBodyInput,
        MaxFormulaBodyInput,
        MeOut,
        MinFormulaBodyInput,
        OwnedByResponse,
        PackGivenOut,
        PageAttachmentRefOut,
        PageBeingSummaryOut,
        PageCampaignSummaryOut,
        PageCharacterSummaryOut,
        PageEntityListOut,
        PageEntryEffectiveStatsOut,
        PageFindingOut,
        PageGrantRuleOut,
        PageInformationOut,
        PageItemInstanceOut,
        PageItemOut,
        PageStatDefinitionOut,
        PageStatGroupOut,
        PageSubscriberOut,
        PageSubscriptionOut,
        PageSystemOut,
        PageTemplateSummaryOut,
        PageTenantSummaryOut,
        PrerequisitesOut,
        ProductFormulaBodyInput,
        PublishedOut,
        RatioFormulaBodyInput,
        ResolvedSlugOut,
        SelectFormulaBodyInput,
        SheetOut,
        StatDefinitionOut,
        StatGroupOut,
        SubscriberOut,
        SubscribersSummaryOut,
        SumFormulaBodyInput,
        SystemOut,
        TemplateOut,
        TemplateSummaryOut,
        TemplateViewOut,
        TenantOut,
        UpdatesOut,
    )

    # What PUT .../computed-stats/{id} accepts: the formula itself, of any kind.
    ComputedStatBody = (
        LinearFormulaBodyInput
        | ComparisonFormulaBodyInput
        | SumFormulaBodyInput
        | ContentsFormulaBodyInput
        | MinFormulaBodyInput
        | MaxFormulaBodyInput
        | ProductFormulaBodyInput
        | RatioFormulaBodyInput
        | SelectFormulaBodyInput
        | DiceValueFormulaBody
        | DiceFormulaBody
    )


_FORMULA_KINDS = (
    "LinearFormulaBodyInput",
    "ComparisonFormulaBodyInput",
    "SumFormulaBodyInput",
    "ContentsFormulaBodyInput",
    "MinFormulaBodyInput",
    "MaxFormulaBodyInput",
    "ProductFormulaBodyInput",
    "RatioFormulaBodyInput",
    "SelectFormulaBodyInput",
    "DiceValueFormulaBody",
    "DiceFormulaBody",
)


def resolve(name: Any) -> Any:
    """The type a name stands for: a generated model, `list[Model]`, or `ComputedStatBody`. A type
    given as itself (a test's own model) is returned as it is."""
    if not isinstance(name, str):
        return name
    models = vars(importlib.import_module("lorenzo_cli.client.models"))
    if name == "ComputedStatBody":
        kinds = [models[kind] for kind in _FORMULA_KINDS]
        union = kinds[0]
        for kind in kinds[1:]:
            union = union | kind
        return union
    if name.startswith("list[") and name.endswith("]"):
        return list[models[name[5:-1]]]  # type: ignore[misc]
    return models[name]


@dataclass(frozen=True)
class Op[T]:
    """One API operation. `request_type` names a model or `ComputedStatBody`, `response_type` a
    model or `list[Model]`, or is None (no body); both are resolved on first use."""

    operation_id: str
    method: str
    path: str
    request_type: Any = None
    response_type: Any = None

    @cached_property
    def request(self) -> Any:
        return resolve(self.request_type)

    @cached_property
    def response(self) -> Any:
        return resolve(self.response_type)

    @cached_property
    def adapter(self) -> TypeAdapter[T] | None:
        response = self.response
        return None if response is None else TypeAdapter(response)


_TENANT = "/tenants/{tenant_id}"

GET_ME: Op[MeOut] = Op("get_me", "GET", "/me", response_type="MeOut")
GET_TENANT: Op[TenantOut] = Op("get_tenant", "GET", _TENANT, response_type="TenantOut")
LIST_TENANTS: Op[PageTenantSummaryOut] = Op(
    "list_tenants", "GET", "/tenants", response_type="PageTenantSummaryOut"
)
CREATE_TENANT: Op[TenantOut] = Op(
    "create_tenant", "POST", "/tenants", request_type="TenantCreate", response_type="TenantOut"
)
DELETE_TENANT: Op[None] = Op("delete_tenant", "DELETE", _TENANT)

LIST_STAT_GROUPS: Op[PageStatGroupOut] = Op(
    "list_stat_groups", "GET", f"{_TENANT}/stat-groups", response_type="PageStatGroupOut"
)
CREATE_STAT_GROUP: Op[StatGroupOut] = Op(
    "create_stat_group",
    "POST",
    f"{_TENANT}/stat-groups",
    request_type="StatGroupCreate",
    response_type="StatGroupOut",
)
LIST_STAT_DEFINITIONS: Op[PageStatDefinitionOut] = Op(
    "list_stat_definitions",
    "GET",
    f"{_TENANT}/stat-definitions",
    response_type="PageStatDefinitionOut",
)
CREATE_STAT_DEFINITION: Op[StatDefinitionOut] = Op(
    "create_stat_definition",
    "POST",
    f"{_TENANT}/stat-definitions",
    request_type="StatDefinitionCreate",
    response_type="StatDefinitionOut",
)

RESOLVE_SLUGS: Op[list[ResolvedSlugOut]] = Op(
    "resolve_slugs", "GET", f"{_TENANT}/entities/resolve", response_type="list[ResolvedSlugOut]"
)
LIST_CHARACTERS: Op[PageCharacterSummaryOut] = Op(
    "list_characters", "GET", f"{_TENANT}/characters", response_type="PageCharacterSummaryOut"
)
LIST_BEINGS: Op[PageBeingSummaryOut] = Op(
    "list_beings", "GET", f"{_TENANT}/beings", response_type="PageBeingSummaryOut"
)
LIST_ITEMS: Op[PageItemOut] = Op(
    "list_items", "GET", f"{_TENANT}/items", response_type="PageItemOut"
)
GET_ITEM: Op[ItemOut] = Op(
    "get_item", "GET", f"{_TENANT}/items/{{entity_id}}", response_type="ItemOut"
)
DELETE_ITEM: Op[None] = Op("delete_item", "DELETE", f"{_TENANT}/items/{{entity_id}}")
DELETE_STAT_DEFINITION: Op[None] = Op(
    "delete_stat_definition", "DELETE", f"{_TENANT}/stat-definitions/{{stat_definition_id}}"
)
DELETE_STAT_GROUP: Op[None] = Op(
    "delete_stat_group", "DELETE", f"{_TENANT}/stat-groups/{{stat_group_id}}"
)
ENTRY_LIBRARIES: Op[LibraryCountOut] = Op(
    "count_entity_libraries",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/libraries",
    response_type="LibraryCountOut",
)
STAT_LIBRARIES: Op[LibraryCountOut] = Op(
    "count_stat_definition_libraries",
    "GET",
    f"{_TENANT}/stat-definitions/{{stat_definition_id}}/libraries",
    response_type="LibraryCountOut",
)
STAT_GROUP_LIBRARIES: Op[LibraryCountOut] = Op(
    "count_stat_group_libraries",
    "GET",
    f"{_TENANT}/stat-groups/{{stat_group_id}}/libraries",
    response_type="LibraryCountOut",
)
CREATE_ITEM: Op[ItemOut] = Op(
    "create_item", "POST", f"{_TENANT}/items", request_type="ItemCreate", response_type="ItemOut"
)
SET_ENTITY_TAG: Op[EntityStatWriteOut] = Op(
    "set_entity_tag",
    "PUT",
    f"{_TENANT}/entities/{{entity_id}}/tags/{{stat_definition_id}}",
    response_type="EntityStatWriteOut",
)
LIST_ENTITY_COMPUTED_STATS: Op[list[ComputedStatOut]] = Op(
    "list_entity_computed_stats",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/computed-stats",
    response_type="list[ComputedStatOut]",
)
SET_COMPUTED_STAT: Op[ComputedStatOut] = Op(
    "set_computed_stat",
    "PUT",
    f"{_TENANT}/entities/{{entity_id}}/computed-stats/{{stat_definition_id}}",
    request_type="ComputedStatBody",
    response_type="ComputedStatOut",
)

GET_ENTITY: Op[EntityDetailOut] = Op(
    "get_entity", "GET", f"{_TENANT}/entities/{{entity_id}}", response_type="EntityDetailOut"
)
SET_ENTITY_STAT: Op[EntityStatWriteOut] = Op(
    "set_entity_stat",
    "PUT",
    f"{_TENANT}/entities/{{entity_id}}/stats/{{stat_definition_id}}",
    request_type="SetEntityStatRequest",
    response_type="EntityStatWriteOut",
)
CREATE_INFORMATION: Op[InformationOut] = Op(
    "create_information",
    "POST",
    f"{_TENANT}/entities/{{entity_id}}/information",
    request_type="InformationCreate",
    response_type="InformationOut",
)
GET_INFORMATION: Op[InformationOut] = Op(
    "get_information",
    "GET",
    f"{_TENANT}/information/{{information_id}}",
    response_type="InformationOut",
)
UPDATE_INFORMATION: Op[InformationOut] = Op(
    "update_information",
    "PATCH",
    f"{_TENANT}/information/{{information_id}}",
    request_type="InformationUpdate",
    response_type="InformationOut",
)
CREATE_ITEM_INSTANCE: Op[ItemInstanceOut] = Op(
    "create_item_instance",
    "POST",
    f"{_TENANT}/item-instances",
    request_type="ItemInstanceCreate",
    response_type="ItemInstanceOut",
)
LIST_ENTITY_INFORMATION: Op[PageInformationOut] = Op(
    "list_entity_information",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/information",
    response_type="PageInformationOut",
)
ADD_INFORMATION_KNOWER: Op[InformationOut] = Op(
    "add_information_knower",
    "PUT",
    f"{_TENANT}/information/{{information_id}}/knowers/{{knower_entity_id}}",
    response_type="InformationOut",
)
LIST_ITEM_INSTANCES: Op[PageItemInstanceOut] = Op(
    "list_item_instances", "GET", f"{_TENANT}/item-instances", response_type="PageItemInstanceOut"
)
LIST_ITEM_INSTANCES_OWNED_BY: Op[OwnedByResponse] = Op(
    "list_item_instances_owned_by",
    "GET",
    f"{_TENANT}/item-instances/owned-by/{{owner_entity_id}}",
    response_type="OwnedByResponse",
)
DELETE_ITEM_INSTANCE: Op[None] = Op(
    "delete_item_instance", "DELETE", f"{_TENANT}/item-instances/{{entity_id}}"
)
SET_ITEM_INSTANCE_CONTAINER: Op[ItemInstanceOut] = Op(
    "set_item_instance_container",
    "PUT",
    f"{_TENANT}/item-instances/{{entity_id}}/container",
    request_type="SetContainerRequest",
    response_type="ItemInstanceOut",
)
CLEAR_ITEM_INSTANCE_CONTAINER: Op[ItemInstanceOut] = Op(
    "clear_item_instance_container",
    "DELETE",
    f"{_TENANT}/item-instances/{{entity_id}}/container",
    response_type="ItemInstanceOut",
)
CREATE_ITEM_INSTANCES_FROM_PACK: Op[PackGivenOut] = Op(
    "create_item_instances_from_pack",
    "POST",
    f"{_TENANT}/item-instances/from-pack",
    request_type="GivePackRequest",
    response_type="PackGivenOut",
)
REPLACE_ITEM_PROTOTYPES: Op[ItemOut] = Op(
    "replace_item_prototypes",
    "PUT",
    f"{_TENANT}/items/{{entity_id}}/prototypes",
    request_type="SetPrototypesRequest",
    response_type="ItemOut",
)

# A repository's own side (an owner publishes and grants) and a granted tenant's (any member
# lists, plans, copies and takes updates): ADR 0118 to 0121, the CLI's side in ADR 0159.
_REPOSITORY = f"{_TENANT}/repositories/{{repository_id}}"
PUBLISH_REPOSITORY: Op[PublishedOut] = Op(
    "publish_repository",
    "PUT",
    f"{_TENANT}/published",
    request_type="PublishRequest",
    response_type="PublishedOut",
)
UNPUBLISH_REPOSITORY: Op[TenantOut] = Op(
    "unpublish_repository", "DELETE", f"{_TENANT}/published", response_type="TenantOut"
)
LIST_SUBSCRIBERS: Op[PageSubscriberOut] = Op(
    "list_subscribers", "GET", f"{_TENANT}/subscribers", response_type="PageSubscriberOut"
)
SUBSCRIBERS_SUMMARY: Op[SubscribersSummaryOut] = Op(
    "summarize_subscribers",
    "GET",
    f"{_TENANT}/subscribers/summary",
    response_type="SubscribersSummaryOut",
)
GRANT_REPOSITORY: Op[SubscriberOut] = Op(
    "grant_repository",
    "PUT",
    f"{_TENANT}/subscribers/{{subscriber_tenant_id}}",
    response_type="SubscriberOut",
)
REVOKE_REPOSITORY: Op[None] = Op(
    "revoke_repository", "DELETE", f"{_TENANT}/subscribers/{{subscriber_tenant_id}}"
)
LIST_REPOSITORIES: Op[PageSubscriptionOut] = Op(
    "list_repositories", "GET", f"{_TENANT}/repositories", response_type="PageSubscriptionOut"
)
LIST_ATTACHMENTS: Op[PageAttachmentRefOut] = Op(
    "list_attachments", "GET", f"{_TENANT}/attachments", response_type="PageAttachmentRefOut"
)
PLAN_REPOSITORY_COPY: Op[CopyPlanOut] = Op(
    "plan_repository_copy", "GET", f"{_REPOSITORY}/copy-plan", response_type="CopyPlanOut"
)
COPY_REPOSITORY: Op[CopyOut] = Op(
    "copy_repository",
    "POST",
    f"{_REPOSITORY}/copy",
    request_type="CopyRequest",
    response_type="CopyOut",
)
LIST_REPOSITORY_UPDATES: Op[UpdatesOut] = Op(
    "list_repository_updates", "GET", f"{_REPOSITORY}/updates", response_type="UpdatesOut"
)
APPLY_REPOSITORY_UPDATES: Op[ApplyUpdatesOut] = Op(
    "apply_repository_updates",
    "POST",
    f"{_REPOSITORY}/updates",
    request_type="ApplyUpdatesRequest",
    response_type="ApplyUpdatesOut",
)

UPDATE_STAT_GROUP: Op[StatGroupOut] = Op(
    "update_stat_group",
    "PATCH",
    f"{_TENANT}/stat-groups/{{stat_group_id}}",
    request_type="StatGroupUpdate",
    response_type="StatGroupOut",
)
UPDATE_STAT_DEFINITION: Op[StatDefinitionOut] = Op(
    "update_stat_definition",
    "PATCH",
    f"{_TENANT}/stat-definitions/{{stat_definition_id}}",
    request_type="StatDefinitionUpdate",
    response_type="StatDefinitionOut",
)
UPDATE_TENANT: Op[TenantOut] = Op(
    "update_tenant",
    "PATCH",
    _TENANT,
    request_type="TenantUpdate",
    response_type="TenantOut",
)
GET_ITEM_INSTANCE: Op[ItemInstanceOut] = Op(
    "get_item_instance",
    "GET",
    f"{_TENANT}/item-instances/{{entity_id}}",
    response_type="ItemInstanceOut",
)
GET_BEING_SHEET: Op[SheetOut] = Op(
    "get_being_sheet",
    "GET",
    f"{_TENANT}/beings/{{entity_id}}/sheet",
    response_type="SheetOut",
)

PLAN_CALENDAR_IMPORT: Op[CalendarImportPlan] = Op(
    "plan_calendar_import",
    "POST",
    f"{_TENANT}/calendar-imports/plan",
    request_type="CalendarImportRequest",
    response_type="CalendarImportPlan",
)
APPLY_CALENDAR_IMPORT: Op[CalendarImportReceipt] = Op(
    "apply_calendar_import",
    "POST",
    f"{_TENANT}/calendar-imports",
    request_type="CalendarImportApply",
    response_type="CalendarImportReceipt",
)
EXPORT_CALENDAR_IMPORT: Op[CalendarDocumentOutput] = Op(
    "export_calendar_import",
    "GET",
    f"{_TENANT}/calendar-imports/{{source_key}}/document",
    response_type="CalendarDocumentOutput",
)

# --- RFC 0052 to RFC 0056: systems, templates, features, grants, the check (RFC 0057 C4) ---

LIST_SYSTEMS: Op[PageSystemOut] = Op(
    "list_systems",
    "GET",
    f"{_TENANT}/systems",
    response_type="PageSystemOut",
)

CREATE_SYSTEM: Op[SystemOut] = Op(
    "create_system",
    "POST",
    f"{_TENANT}/systems",
    request_type="SystemCreate",
    response_type="SystemOut",
)

GET_SYSTEM: Op[SystemOut] = Op(
    "get_system",
    "GET",
    f"{_TENANT}/systems/{{system_id}}",
    response_type="SystemOut",
)

UPDATE_SYSTEM: Op[SystemOut] = Op(
    "update_system",
    "PATCH",
    f"{_TENANT}/systems/{{system_id}}",
    request_type="SystemUpdate",
    response_type="SystemOut",
)

DELETE_SYSTEM: Op[None] = Op(
    "delete_system",
    "DELETE",
    f"{_TENANT}/systems/{{system_id}}",
)

GET_STAT_GROUP: Op[StatGroupOut] = Op(
    "get_stat_group",
    "GET",
    f"{_TENANT}/stat-groups/{{stat_group_id}}",
    response_type="StatGroupOut",
)

GET_STAT_DEFINITION: Op[StatDefinitionOut] = Op(
    "get_stat_definition",
    "GET",
    f"{_TENANT}/stat-definitions/{{stat_definition_id}}",
    response_type="StatDefinitionOut",
)

LIST_STAT_DEPENDENTS: Op[list[ComputedStatDependentOut]] = Op(
    "list_stat_dependents",
    "GET",
    f"{_TENANT}/stat-definitions/{{stat_definition_id}}/dependents",
    response_type="list[ComputedStatDependentOut]",
)

DELETE_COMPUTED_STAT: Op[None] = Op(
    "delete_computed_stat",
    "DELETE",
    f"{_TENANT}/entities/{{entity_id}}/computed-stats/{{stat_definition_id}}",
)

PREVIEW_COMPUTED_STAT: Op[ComputedStatPreviewOut] = Op(
    "preview_computed_stat",
    "POST",
    f"{_TENANT}/entities/{{entity_id}}/computed-stats/{{stat_definition_id}}/preview",
    request_type="ComputedStatPreviewIn",
    response_type="ComputedStatPreviewOut",
)

LIST_ENTITIES: Op[PageEntityListOut] = Op(
    "list_entities",
    "GET",
    f"{_TENANT}/entities",
    response_type="PageEntityListOut",
)

CREATE_ENTITY: Op[EntityDetailOut] = Op(
    "create_entity",
    "POST",
    f"{_TENANT}/entities",
    request_type="EntityCreate",
    response_type="EntityDetailOut",
)

GET_ENTITY_BY_SLUG: Op[EntityDetailOut] = Op(
    "get_entity_by_slug",
    "GET",
    f"{_TENANT}/entities/by-slug/{{slug}}",
    response_type="EntityDetailOut",
)

LIST_EFFECTIVE_STATS: Op[PageEntryEffectiveStatsOut] = Op(
    "list_effective_stats",
    "GET",
    f"{_TENANT}/entities/effective-stats",
    response_type="PageEntryEffectiveStatsOut",
)

ADD_ENTITY_KIND: Op[EntityDetailOut] = Op(
    "add_entity_kind",
    "PUT",
    f"{_TENANT}/entities/{{entity_id}}/kinds/{{kind}}",
    request_type="EntityKindPut",
    response_type="EntityDetailOut",
)

REMOVE_ENTITY_KIND: Op[EntityDetailOut] = Op(
    "remove_entity_kind",
    "DELETE",
    f"{_TENANT}/entities/{{entity_id}}/kinds/{{kind}}",
    response_type="EntityDetailOut",
)

LIST_TEMPLATES: Op[PageTemplateSummaryOut] = Op(
    "list_templates",
    "GET",
    f"{_TENANT}/templates",
    response_type="PageTemplateSummaryOut",
)

CREATE_TEMPLATE: Op[TemplateOut] = Op(
    "create_template",
    "POST",
    f"{_TENANT}/templates",
    request_type="TemplateIn",
    response_type="TemplateOut",
)

GET_TEMPLATE: Op[TemplateOut] = Op(
    "get_template",
    "GET",
    f"{_TENANT}/templates/{{template_id}}",
    response_type="TemplateOut",
)

REPLACE_TEMPLATE: Op[TemplateOut] = Op(
    "replace_template",
    "PUT",
    f"{_TENANT}/templates/{{template_id}}",
    request_type="TemplateIn",
    response_type="TemplateOut",
)

DELETE_TEMPLATE: Op[None] = Op(
    "delete_template",
    "DELETE",
    f"{_TENANT}/templates/{{template_id}}",
)

MATCHING_TEMPLATES: Op[list[TemplateSummaryOut]] = Op(
    "matching_templates",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/matching-templates",
    response_type="list[TemplateSummaryOut]",
)

READ_THROUGH_TEMPLATE: Op[TemplateViewOut] = Op(
    "read_through_template",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/templates/{{template_id}}",
    response_type="TemplateViewOut",
)

LIST_CAMPAIGNS: Op[PageCampaignSummaryOut] = Op(
    "list_campaigns",
    "GET",
    f"{_TENANT}/campaigns",
    response_type="PageCampaignSummaryOut",
)

CREATE_CAMPAIGN: Op[CampaignOut] = Op(
    "create_campaign",
    "POST",
    f"{_TENANT}/campaigns",
    request_type="CampaignCreate",
    response_type="CampaignOut",
)

GET_CAMPAIGN: Op[CampaignOut] = Op(
    "get_campaign",
    "GET",
    f"{_TENANT}/campaigns/{{campaign_id}}",
    response_type="CampaignOut",
)

UPDATE_CAMPAIGN: Op[CampaignOut] = Op(
    "update_campaign",
    "PATCH",
    f"{_TENANT}/campaigns/{{campaign_id}}",
    request_type="CampaignUpdate",
    response_type="CampaignOut",
)

LIST_HELD_FEATURES: Op[HeldFeaturesOut] = Op(
    "list_held_features",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/features",
    response_type="HeldFeaturesOut",
)

AWARD_FEATURE: Op[HeldFeatureOut] = Op(
    "award_feature",
    "POST",
    f"{_TENANT}/entities/{{entity_id}}/features",
    request_type="FeatureAwardIn",
    response_type="HeldFeatureOut",
)

GET_HELD_FEATURE: Op[HeldFeatureOut] = Op(
    "get_held_feature",
    "GET",
    f"{_TENANT}/features/{{instance_id}}",
    response_type="HeldFeatureOut",
)

REMOVE_FEATURE: Op[None] = Op(
    "remove_feature",
    "DELETE",
    f"{_TENANT}/features/{{instance_id}}",
)

SET_FEATURE_ACTIVE: Op[HeldFeatureOut] = Op(
    "set_feature_active",
    "PUT",
    f"{_TENANT}/features/{{instance_id}}/active",
    request_type="FeatureActiveIn",
    response_type="HeldFeatureOut",
)

GET_FEATURE_COLUMNS: Op[FeatureColumnsOut] = Op(
    "get_feature_columns",
    "GET",
    f"{_TENANT}/features/prototypes/{{feature_id}}",
    response_type="FeatureColumnsOut",
)

GET_PREREQUISITES: Op[PrerequisitesOut] = Op(
    "get_prerequisites",
    "GET",
    f"{_TENANT}/features/prototypes/{{feature_id}}/prerequisites",
    response_type="PrerequisitesOut",
)

PUT_PREREQUISITES: Op[PrerequisitesOut] = Op(
    "put_prerequisites",
    "PUT",
    f"{_TENANT}/features/prototypes/{{feature_id}}/prerequisites",
    request_type="PrerequisitesIn",
    response_type="PrerequisitesOut",
)

LIST_GRANT_RULES: Op[PageGrantRuleOut] = Op(
    "list_grant_rules",
    "GET",
    f"{_TENANT}/grant-rules",
    response_type="PageGrantRuleOut",
)

CREATE_GRANT_RULE: Op[GrantRuleOut] = Op(
    "create_grant_rule",
    "POST",
    f"{_TENANT}/grant-rules",
    request_type="GrantRuleIn",
    response_type="GrantRuleOut",
)

GET_GRANT_RULE: Op[GrantRuleOut] = Op(
    "get_grant_rule",
    "GET",
    f"{_TENANT}/grant-rules/{{rule_id}}",
    response_type="GrantRuleOut",
)

REPLACE_GRANT_RULE: Op[GrantRuleOut] = Op(
    "replace_grant_rule",
    "PUT",
    f"{_TENANT}/grant-rules/{{rule_id}}",
    request_type="GrantRuleUpdate",
    response_type="GrantRuleOut",
)

DELETE_GRANT_RULE: Op[None] = Op(
    "delete_grant_rule",
    "DELETE",
    f"{_TENANT}/grant-rules/{{rule_id}}",
)

GET_GRANTS: Op[GrantsOut] = Op(
    "get_grants",
    "GET",
    f"{_TENANT}/entities/{{entity_id}}/grants",
    response_type="GrantsOut",
)

APPLY_GRANTS: Op[ApplyOut] = Op(
    "apply_grants_route",
    "POST",
    f"{_TENANT}/entities/{{entity_id}}/grants/apply",
    request_type="ApplyIn",
    response_type="ApplyOut",
)

CHECK_VOCABULARY: Op[PageFindingOut] = Op(
    "check_vocabulary",
    "GET",
    f"{_TENANT}/vocabulary-check",
    response_type="PageFindingOut",
)


# --- The library document (RFC 0057 C5) ---

EXPORT_ENTITIES: Op[EntityExportPage] = Op(
    "export_entities", "GET", f"{_TENANT}/entities/export", response_type="EntityExportPage"
)
REPLACE_ENTITY_PARENTS: Op[EntityDetailOut] = Op(
    "replace_entity_parents",
    "PUT",
    f"{_TENANT}/entities/{{entity_id}}/parents",
    request_type="EntityParentsRequest",
    response_type="EntityDetailOut",
)
DELETE_ENTITY: Op[None] = Op("delete_entity", "DELETE", f"{_TENANT}/entities/{{entity_id}}")

ALL_OPS: tuple[Op[Any], ...] = (
    EXPORT_ENTITIES,
    REPLACE_ENTITY_PARENTS,
    DELETE_ENTITY,
    PLAN_CALENDAR_IMPORT,
    APPLY_CALENDAR_IMPORT,
    EXPORT_CALENDAR_IMPORT,
    UPDATE_STAT_GROUP,
    UPDATE_STAT_DEFINITION,
    UPDATE_TENANT,
    GET_ITEM_INSTANCE,
    GET_BEING_SHEET,
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
    LIST_BEINGS,
    LIST_ITEMS,
    GET_ITEM,
    DELETE_ITEM,
    DELETE_STAT_DEFINITION,
    DELETE_STAT_GROUP,
    ENTRY_LIBRARIES,
    STAT_GROUP_LIBRARIES,
    STAT_LIBRARIES,
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
    LIST_ITEM_INSTANCES,
    LIST_ITEM_INSTANCES_OWNED_BY,
    DELETE_ITEM_INSTANCE,
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
    LIST_SYSTEMS,
    CREATE_SYSTEM,
    GET_SYSTEM,
    UPDATE_SYSTEM,
    DELETE_SYSTEM,
    GET_STAT_GROUP,
    GET_STAT_DEFINITION,
    LIST_STAT_DEPENDENTS,
    DELETE_COMPUTED_STAT,
    PREVIEW_COMPUTED_STAT,
    LIST_ENTITIES,
    CREATE_ENTITY,
    GET_ENTITY_BY_SLUG,
    LIST_EFFECTIVE_STATS,
    ADD_ENTITY_KIND,
    REMOVE_ENTITY_KIND,
    LIST_TEMPLATES,
    CREATE_TEMPLATE,
    GET_TEMPLATE,
    REPLACE_TEMPLATE,
    DELETE_TEMPLATE,
    MATCHING_TEMPLATES,
    READ_THROUGH_TEMPLATE,
    LIST_CAMPAIGNS,
    CREATE_CAMPAIGN,
    GET_CAMPAIGN,
    UPDATE_CAMPAIGN,
    LIST_HELD_FEATURES,
    AWARD_FEATURE,
    GET_HELD_FEATURE,
    REMOVE_FEATURE,
    SET_FEATURE_ACTIVE,
    GET_FEATURE_COLUMNS,
    GET_PREREQUISITES,
    PUT_PREREQUISITES,
    LIST_GRANT_RULES,
    CREATE_GRANT_RULE,
    GET_GRANT_RULE,
    REPLACE_GRANT_RULE,
    DELETE_GRANT_RULE,
    GET_GRANTS,
    APPLY_GRANTS,
    CHECK_VOCABULARY,
)
