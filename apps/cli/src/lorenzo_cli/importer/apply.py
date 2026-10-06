"""Carrying out an import plan (RFC 0025 §2, R4, R6, ADR 0144).

An item is created and named in one request (ADR 0139), then its stats are written with their
stat groups acquired (ADR 0142), then its description, and `sourcebook` last: a run that stops in
the middle leaves an item the next plan recognises as unfinished and finishes, never one it
mistakes for done.

One item failing does not stop the rest; the failures are reported and the exit code says so.

The system pass (ADR 0182) writes a prototype instead, with the system's half of the item, and
attaches it to the neutral item last: the attachment is what says the prototype is done.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

from lorenzo_cli import descriptions
from lorenzo_cli.client.errors import LorenzoApiError, StaleResourceError
from lorenzo_cli.client.models import (
    InformationCreate,
    ItemCreate,
    SetEntityStatRequest,
    SetPrototypesRequest,
    StatDefinitionCreate,
    StatDefinitionOut,
    StatGroupCreate,
    StatValueType,
)
from lorenzo_cli.client.ops import (
    CREATE_INFORMATION,
    CREATE_ITEM,
    CREATE_STAT_DEFINITION,
    CREATE_STAT_GROUP,
    GET_ITEM,
    REPLACE_ITEM_PROTOTYPES,
    SET_ENTITY_STAT,
)
from lorenzo_cli.client.transport import LorenzoClient
from lorenzo_cli.importer import tenant_view
from lorenzo_cli.importer.manifest import Manifest
from lorenzo_cli.importer.plan import MARKER_STAT, ImportPlan, PlannedItem
from lorenzo_cli.importer.transforms import StatValue
from lorenzo_cli.prototypes import add_parent


@dataclass(frozen=True)
class ApplyOptions:
    reconcile: bool = False
    public_catalog: bool = False


@dataclass
class ApplyReport:
    created: int = 0
    completed: int = 0
    retitled: int = 0
    reparented: int = 0
    # Prototypes the system pass attached to their items.
    attached: int = 0
    categories: int = 0
    definitions: int = 0
    failures: list[str] = field(default_factory=list)


def cast(value: StatValue, value_type: str) -> StatValue:
    """The value as the definition's type wants it: `PUT .../stats` does no int/float coercion."""
    if value_type == "float":
        return float(value)
    if value_type == "int":
        return int(value)
    if value_type == "bool":
        return bool(value)
    return str(value)


def apply_import(
    client: LorenzoClient,
    plan: ImportPlan,
    manifest: Manifest,
    options: ApplyOptions,
    progress: Callable[[str], None] = lambda _: None,
) -> ApplyReport:
    if plan.problems:
        raise ValueError("A plan with problems is never applied.")
    report = ApplyReport()
    tenant = {"tenant_id": plan.tenant.id}

    _create_definitions(client, plan, report)
    definitions = tenant_view.stat_definitions(client, plan.tenant.id)

    parent_ids = _create_categories(client, plan, report)
    needed = {p for i in plan.items for p in i.draft.parents} - parent_ids.keys()
    parent_ids |= {
        slug: hit.entity_id
        for slug, hit in tenant_view.resolve_slugs(client, plan.tenant.id, sorted(needed)).items()
    }

    # Packs last: their contents name items, and are written once those items exist (ADR 0145).
    todo = sorted(
        (i for i in plan.items if i.status in ("create", "complete", "retitle")),
        key=lambda i: i.draft.list_name == "packs",
    )
    for number, item in enumerate(todo, start=1):
        progress(f"{number}/{len(todo)} {item.slug}")
        try:
            _write_item(client, plan, item, parent_ids, definitions, options, report)
            token = (
                f"system:{item.draft.list_name}" if plan.part == "system" else item.draft.list_name
            )
            manifest.record(token, item.draft.key, item.slug)
        except LorenzoApiError as exc:
            report.failures.append(f"{item.slug}: {exc} (HTTP {exc.status})")

    if options.reconcile:
        for item in plan.items:
            if item.reparent and item.entity_id is not None:
                _reparent(client, tenant["tenant_id"], item, parent_ids, plan.managed_ids, report)
    return report


def _create_definitions(client: LorenzoClient, plan: ImportPlan, report: ApplyReport) -> None:
    if not plan.definitions:
        return
    tenant = {"tenant_id": plan.tenant.id}
    groups = tenant_view.stat_groups(client, plan.tenant.id)
    for definition in plan.definitions:
        if definition.group not in groups:
            groups[definition.group] = client.call(
                CREATE_STAT_GROUP, path=tenant, body=StatGroupCreate(name=definition.group)
            ).value
        client.call(
            CREATE_STAT_DEFINITION,
            path=tenant,
            body=StatDefinitionCreate(
                name=definition.name,
                stat_group_id=groups[definition.group].id,
                value_type=StatValueType(definition.value_type),
            ),
        )
        report.definitions += 1


def _create_categories(
    client: LorenzoClient, plan: ImportPlan, report: ApplyReport
) -> dict[str, UUID]:
    """Mint the categories a map row asked for (`create-under`), under their axis roots."""
    if not plan.categories:
        return {}
    tenant = {"tenant_id": plan.tenant.id}
    known = tenant_view.resolve_slugs(
        client,
        plan.tenant.id,
        sorted({c.parent for c in plan.categories} | {c.slug for c in plan.categories}),
    )
    ids = {slug: hit.entity_id for slug, hit in known.items()}
    for category in plan.categories:
        if category.slug in ids:
            continue
        created = client.call(
            CREATE_ITEM,
            path=tenant,
            body=ItemCreate(
                name=category.name,
                slug=category.slug,
                prototype_ids=[ids[category.parent]],
                in_public_catalog=False,
            ),
        )
        ids[category.slug] = created.value.entity_id
        report.categories += 1
    return ids


def _write_item(
    client: LorenzoClient,
    plan: ImportPlan,
    item: PlannedItem,
    parent_ids: dict[str, UUID],
    definitions: dict[str, StatDefinitionOut],
    options: ApplyOptions,
    report: ApplyReport,
) -> None:
    if item.status == "retitle":
        # Only the title: whatever else the item lacks is not this status's business.
        _retitle(client, plan.tenant.id, item, report)
        return
    draft = item.draft
    name = draft.name or item.slug
    tenant = {"tenant_id": plan.tenant.id}
    entity_id = item.entity_id
    have_stats, has_description = item.have_stats, item.has_description
    have_information = item.have_information
    if item.status == "create":
        try:
            created = client.call(
                CREATE_ITEM,
                path=tenant,
                body=ItemCreate(
                    name=name,
                    slug=item.slug,
                    prototype_ids=[parent_ids[p] for p in draft.parents],
                    # A prototype is never public: players list the neutral items (ADR 0182).
                    in_public_catalog=options.public_catalog and plan.part != "system",
                ),
            )
            entity_id = created.value.entity_id
            report.created += 1
        except LorenzoApiError as exc:
            if exc.status != 409:
                raise
            # It is there already (an earlier run, or another machine): finish it instead.
            entity_id = tenant_view.resolve_slugs(client, plan.tenant.id, [item.slug])[
                item.slug
            ].entity_id
            detail = tenant_view.entity_detail(client, plan.tenant.id, entity_id)
            have_stats = frozenset(s.name for s in detail.stats if s.own)
            has_description = any(i.type == "description" for i in detail.information)
            have_information = frozenset(i.type for i in detail.information)
            stale = descriptions.placeholder_description(detail)
            item.retitle = (stale.id, detail.name) if stale is not None else None
            report.completed += 1
    else:
        report.completed += 1
    assert entity_id is not None

    def write(stat: str) -> None:
        if stat in have_stats:
            return
        definition = definitions[stat]
        client.call(
            SET_ENTITY_STAT,
            path={**tenant, "entity_id": entity_id, "stat_definition_id": definition.id},
            body=SetEntityStatRequest(
                value=cast(draft.stats[stat], definition.value_type.value), acquire_group=True
            ),
        )

    for stat in sorted(s for s in draft.stats if s != MARKER_STAT):
        write(stat)
    if draft.description and not has_description:
        client.call(
            CREATE_INFORMATION,
            path={**tenant, "entity_id": entity_id},
            body=InformationCreate(
                title=name,
                type="description",
                is_public=True,
                content=draft.description,
                locale="en-US",
            ),
        )
    for entry in draft.information:
        if entry.type not in have_information:
            client.call(
                CREATE_INFORMATION,
                path={**tenant, "entity_id": entity_id},
                body=InformationCreate(
                    title=entry.title,
                    type=entry.type,
                    is_public=True,
                    content=entry.content,
                    locale="en-US",
                ),
            )
    if item.retitle is not None:
        _retitle(client, plan.tenant.id, item, report)
    if MARKER_STAT in draft.stats:
        write(MARKER_STAT)  # last: its presence says the item is finished
    if plan.part == "system":
        _attach(client, plan, item, entity_id, report)


def _attach(
    client: LorenzoClient,
    plan: ImportPlan,
    item: PlannedItem,
    prototype_id: UUID,
    report: ApplyReport,
) -> None:
    """Add the prototype to the neutral item's parents, last (ADR 0182). In a bridge the item is a
    copy of the equipment's, so the parent is an attachment (ADR 0172)."""
    assert item.neutral_id is not None
    try:
        if add_parent(client, plan.tenant.id, item.neutral_id, prototype_id):
            report.attached += 1
    except StaleResourceError:
        # The prototype is written; the next run finds it unattached and attaches it.
        report.failures.append(
            f"{item.neutral_slug} changed while attaching {item.slug}; run it again"
        )


def _retitle(
    client: LorenzoClient, tenant_id: UUID, item: PlannedItem, report: ApplyReport
) -> None:
    """Give a description that has the old placeholder title its item's name (ADR 0165)."""
    assert item.retitle is not None
    information_id, title = item.retitle
    try:
        descriptions.retitle(client, tenant_id, information_id, title)
        report.retitled += 1
    except StaleResourceError:
        report.failures.append(
            f"{item.slug}: its description changed while retitling; run it again"
        )


def _reparent(
    client: LorenzoClient,
    tenant_id: UUID,
    item: PlannedItem,
    parent_ids: dict[str, UUID],
    managed_ids: frozenset[UUID],
    report: ApplyReport,
) -> None:
    path = {"tenant_id": tenant_id, "entity_id": item.entity_id}
    try:
        current = client.call(GET_ITEM, path=path)
        # Replace the parents the importer places and keep the others: a prototype attached by
        # the system pass, or a parent an author added, stays (ADR 0182).
        kept = [p for p in current.value.prototype_ids if p not in managed_ids]
        client.call(
            REPLACE_ITEM_PROTOTYPES,
            path=path,
            body=SetPrototypesRequest(
                prototype_ids=[*kept, *(parent_ids[p] for p in item.draft.parents)]
            ),
            if_match=current.etag,
        )
        report.reparented += 1
    except StaleResourceError:
        report.failures.append(f"{item.slug}: changed while re-parenting; run it again")
    except LorenzoApiError as exc:
        report.failures.append(f"{item.slug}: {exc} (HTTP {exc.status})")
