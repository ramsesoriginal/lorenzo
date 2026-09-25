"""A tenant's content as plain data, for copying (ADR 0119) and diffing
(ADR 0121) repositories.

`load_content` reads everything a repository can hold for one tenant,
with an explicit `tenant_id` filter on every query: for a repository it
runs inside `reading_repository`, for the copying tenant as is. The
snapshot functions describe a row the way a copy link records it - every
id translated to its origin - so the same functions describe a
repository's row now, a snapshot taken at copy time, and a tenant's local
copy, and the three can be compared.
"""

import uuid
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    Being,
    Character,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatLinear,
    Containment,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    GroupMember,
    Information,
    Item,
    ItemInstance,
    Knowledge,
    Ownership,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    RepositoryCopy,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
)

KINDS = ("item", "item_instance", "being", "character")


@dataclass
class StatValue:
    value_int: int | None
    value_text: str | None
    value_float: float | None
    value_bool: bool | None

    def as_json(self) -> Any:
        for value in (self.value_int, self.value_text, self.value_float, self.value_bool):
            if value is not None:
                return value
        return None


@dataclass
class Formula:
    """A computed stat's formula (ADR 0104), with its input definitions."""

    kind: str
    source: uuid.UUID | None = None
    multiplier: Decimal | None = None
    offset: Decimal | None = None
    round_mode: str | None = None
    left: uuid.UUID | None = None
    comparator: str | None = None
    right: uuid.UUID | None = None
    right_constant: Decimal | None = None
    true_value: str | None = None
    false_value: str | None = None

    def inputs(self) -> list[uuid.UUID]:
        return [i for i in (self.source, self.left, self.right) if i is not None]


@dataclass
class PayloadData:
    information_id: uuid.UUID
    order: int
    kind: str  # description, number, picture, document
    fields: dict[str, Any]


@dataclass
class InformationData:
    entity_id: uuid.UUID
    title: str
    type: str
    is_public: bool
    order: int


@dataclass
class Links:
    """One tenant's copy links: local id -> origin id, per kind, plus which
    tenant each origin belongs to and whether a group or definition was
    merged. Deleted local rows (a null local id) are in `deleted`."""

    entity: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    stat_group: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    stat_definition: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    origin_tenant: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    merged: set[uuid.UUID] = field(default_factory=set)
    deleted: dict[str, set[uuid.UUID]] = field(default_factory=lambda: defaultdict(set))
    snapshots: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    copies: set[uuid.UUID] = field(default_factory=set)

    def local_of(self, kind: str) -> dict[uuid.UUID, uuid.UUID]:
        """Origin id -> local id, for one kind."""
        return {origin: local for local, origin in getattr(self, kind).items()}


@dataclass
class Content:
    tenant_id: uuid.UUID
    entities: dict[uuid.UUID, str] = field(default_factory=dict)
    kinds: dict[uuid.UUID, set[str]] = field(default_factory=lambda: defaultdict(set))
    in_public_catalog: dict[uuid.UUID, bool] = field(default_factory=dict)
    slugs: dict[uuid.UUID, str] = field(default_factory=dict)
    prototypes: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    groups: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    definitions: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    enum_values: dict[uuid.UUID, list[tuple[str, int]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    entity_groups: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    stats: dict[tuple[uuid.UUID, uuid.UUID], StatValue] = field(default_factory=dict)
    formulas: dict[tuple[uuid.UUID, uuid.UUID], Formula] = field(default_factory=dict)
    containment: dict[uuid.UUID, tuple[uuid.UUID, int]] = field(default_factory=dict)
    ownership: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)
    group_members: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    information: dict[uuid.UUID, InformationData] = field(default_factory=dict)
    payloads: dict[uuid.UUID, PayloadData] = field(default_factory=dict)
    knowledge: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    links: Links = field(default_factory=Links)

    def origin(self, kind: str, local_id: uuid.UUID) -> uuid.UUID:
        """A row's origin: where its copy link says it came from, or the row
        itself if it's this tenant's own."""
        origin: uuid.UUID = getattr(self.links, kind).get(local_id, local_id)
        return origin

    def own(self, kind: str, local_id: uuid.UUID) -> bool:
        """Whether a row is this tenant's own - not a copy, and not merged
        into from a copy (RFC 0024 amendment A8)."""
        return local_id not in getattr(self.links, kind)


async def load_links(session: AsyncSession, tenant_id: uuid.UUID) -> Links:
    links = Links()
    for kind, model, local in (
        ("entity", RepositoryCopyLinkEntity, RepositoryCopyLinkEntity.entity_id),
        ("stat_group", RepositoryCopyLinkStatGroup, RepositoryCopyLinkStatGroup.stat_group_id),
        (
            "stat_definition",
            RepositoryCopyLinkStatDefinition,
            RepositoryCopyLinkStatDefinition.stat_definition_id,
        ),
    ):
        mode_col = getattr(model, "mode", None)
        columns = [local, model.source_id, model.source_tenant_id, model.snapshot]
        if mode_col is not None:
            columns.append(mode_col)
        for row in await session.execute(select(*columns).where(model.tenant_id == tenant_id)):
            local_id, source_id, source_tenant, snapshot = row[0], row[1], row[2], row[3]
            links.origin_tenant[source_id] = source_tenant
            links.snapshots[source_id] = snapshot
            if local_id is None:
                links.deleted[kind].add(source_id)
                continue
            getattr(links, kind)[local_id] = source_id
            if mode_col is not None and row[4] == "merged":
                links.merged.add(source_id)
    links.copies = set(
        await session.scalars(
            select(RepositoryCopy.repository_tenant_id).where(RepositoryCopy.tenant_id == tenant_id)
        )
    )
    return links


async def load_content(session: AsyncSession, tenant_id: uuid.UUID) -> Content:
    """Everything a repository can hold, for one tenant."""
    c = Content(tenant_id=tenant_id)
    t = tenant_id

    async def rows(*columns: Any, where: Any) -> Any:
        return (await session.execute(select(*columns).where(where))).all()

    for entity_id, name in await rows(Entity.id, Entity.name, where=Entity.tenant_id == t):
        c.entities[entity_id] = name
    for entity_id, public in await rows(
        Item.entity_id, Item.in_public_catalog, where=Item.tenant_id == t
    ):
        c.kinds[entity_id].add("item")
        c.in_public_catalog[entity_id] = public
    for kind, model in (
        ("item_instance", ItemInstance),
        ("being", Being),
        ("character", Character),
    ):
        for (entity_id,) in await rows(model.entity_id, where=model.tenant_id == t):
            c.kinds[entity_id].add(kind)
    for entity_id, slug in await rows(
        EntitySlug.entity_id, EntitySlug.slug, where=EntitySlug.tenant_id == t
    ):
        c.slugs[entity_id] = slug
    c.prototypes = [
        (e, p)
        for e, p in await rows(
            EntityPrototype.entity_id,
            EntityPrototype.prototype_id,
            where=EntityPrototype.tenant_id == t,
        )
    ]
    for group_id, name, priority, mandatory in await rows(
        StatGroup.id,
        StatGroup.name,
        StatGroup.priority,
        StatGroup.mandatory,
        where=StatGroup.tenant_id == t,
    ):
        c.groups[group_id] = {"name": name, "priority": priority, "mandatory": mandatory}
    for def_id, name, value_type, group_id in await rows(
        StatDefinition.id,
        StatDefinition.name,
        StatDefinition.value_type,
        StatDefinition.stat_group_id,
        where=StatDefinition.tenant_id == t,
    ):
        c.definitions[def_id] = {"name": name, "value_type": value_type, "group": group_id}
    for def_id, value, sort_order in await rows(
        StatDefinitionEnumValue.stat_definition_id,
        StatDefinitionEnumValue.value,
        StatDefinitionEnumValue.sort_order,
        where=StatDefinitionEnumValue.tenant_id == t,
    ):
        c.enum_values[def_id].append((value, sort_order))
    c.entity_groups = [
        (e, g)
        for e, g in await rows(
            EntityStatGroup.entity_id,
            EntityStatGroup.stat_group_id,
            where=EntityStatGroup.tenant_id == t,
        )
    ]
    for e, d, vi, vt, vf, vb in await rows(
        EntityStat.entity_id,
        EntityStat.stat_definition_id,
        EntityStat.value_int,
        EntityStat.value_text,
        EntityStat.value_float,
        EntityStat.value_bool,
        where=EntityStat.tenant_id == t,
    ):
        c.stats[(e, d)] = StatValue(vi, vt, vf, vb)
    linear = {
        (row.entity_id, row.stat_definition_id): row
        for row in (
            await session.scalars(
                select(ComputedStatLinear).where(ComputedStatLinear.tenant_id == t)
            )
        )
    }
    comparison = {
        (row.entity_id, row.stat_definition_id): row
        for row in (
            await session.scalars(
                select(ComputedStatComparison).where(ComputedStatComparison.tenant_id == t)
            )
        )
    }
    for e, d in await rows(
        ComputedStat.entity_id, ComputedStat.stat_definition_id, where=ComputedStat.tenant_id == t
    ):
        if (e, d) in linear:
            lin = linear[(e, d)]
            c.formulas[(e, d)] = Formula(
                kind="linear",
                source=lin.source_stat_definition_id,
                multiplier=lin.multiplier,
                offset=lin.offset,
                round_mode=lin.round_mode,
            )
        elif (e, d) in comparison:
            cmp = comparison[(e, d)]
            c.formulas[(e, d)] = Formula(
                kind="comparison",
                left=cmp.left_stat_definition_id,
                comparator=cmp.comparator,
                right=cmp.right_stat_definition_id,
                right_constant=cmp.right_constant,
                true_value=cmp.true_value,
                false_value=cmp.false_value,
            )
    for child, parent, quantity in await rows(
        Containment.child_entity_id,
        Containment.parent_entity_id,
        Containment.quantity,
        where=Containment.tenant_id == t,
    ):
        c.containment[child] = (parent, quantity)
    for owned, owner in await rows(
        Ownership.owned_entity_id, Ownership.owner_character_id, where=Ownership.tenant_id == t
    ):
        c.ownership[owned] = owner
    c.group_members = [
        (g, m)
        for g, m in await rows(
            GroupMember.group_entity_id,
            GroupMember.character_entity_id,
            where=GroupMember.tenant_id == t,
        )
    ]
    for info_id, entity_id, title, type_, is_public, order in await rows(
        Information.id,
        Information.entity_id,
        Information.title,
        Information.type,
        Information.is_public,
        Information.order,
        where=Information.tenant_id == t,
    ):
        c.information[info_id] = InformationData(entity_id, title, type_, is_public, order)
    payload_rows = await rows(
        Payload.id, Payload.information_id, Payload.order, where=Payload.tenant_id == t
    )
    kinds_by_payload: dict[uuid.UUID, tuple[str, dict[str, Any]]] = {}
    for pid, locale, content in await rows(
        PayloadDescription.payload_id,
        PayloadDescription.locale,
        PayloadDescription.content,
        where=PayloadDescription.tenant_id == t,
    ):
        kinds_by_payload[pid] = ("description", {"locale": locale, "content": content})
    for pid, value in await rows(
        PayloadNumber.payload_id, PayloadNumber.value, where=PayloadNumber.tenant_id == t
    ):
        kinds_by_payload[pid] = ("number", {"value": value})
    for pid, data, file_type in await rows(
        PayloadPicture.payload_id,
        PayloadPicture.data,
        PayloadPicture.file_type,
        where=PayloadPicture.tenant_id == t,
    ):
        kinds_by_payload[pid] = ("picture", {"data": data, "file_type": file_type})
    for pid, data, filename, file_type in await rows(
        PayloadDocument.payload_id,
        PayloadDocument.data,
        PayloadDocument.filename,
        PayloadDocument.file_type,
        where=PayloadDocument.tenant_id == t,
    ):
        kinds_by_payload[pid] = (
            "document",
            {"data": data, "filename": filename, "file_type": file_type},
        )
    for pid, info_id, order in payload_rows:
        if pid in kinds_by_payload:
            kind, fields = kinds_by_payload[pid]
            c.payloads[pid] = PayloadData(info_id, order, kind, fields)
    c.knowledge = [
        (info_id, knower)
        for info_id, knower in await rows(
            Knowledge.information_id,
            Knowledge.knower_entity_id,
            where=(Knowledge.tenant_id == t) & Knowledge.knower_entity_id.is_not(None),
        )
    ]
    c.links = await load_links(session, t)
    return c


# --- Snapshots ---------------------------------------------------------------

# Maps one of a tenant's ids to how a snapshot names it: its origin id, or
# for a row with no origin elsewhere (the tenant's own, uncopied), a marker
# that can never equal an origin.
Namer = Callable[[str, uuid.UUID], str]


def origin_namer(content: Content) -> Namer:
    """For a repository's own content: every row is named by its origin."""
    return lambda kind, local_id: str(content.origin(kind, local_id))


def _formula_json(formula: Formula, name: Namer) -> dict[str, Any]:
    if formula.kind == "linear":
        assert formula.source is not None
        return {
            "kind": "linear",
            "source": name("stat_definition", formula.source),
            "multiplier": str(formula.multiplier),
            "offset": str(formula.offset),
            "round_mode": formula.round_mode,
        }
    assert formula.left is not None
    return {
        "kind": "comparison",
        "left": name("stat_definition", formula.left),
        "comparator": formula.comparator,
        "right": name("stat_definition", formula.right) if formula.right else None,
        "right_constant": (
            str(formula.right_constant) if formula.right_constant is not None else None
        ),
        "true_value": formula.true_value,
        "false_value": formula.false_value,
    }


@dataclass
class EntityIndex:
    """Per-entity lookups over a Content, built once for many snapshots."""

    prototypes: dict[uuid.UUID, list[uuid.UUID]]
    groups: dict[uuid.UUID, list[uuid.UUID]]
    stats: dict[uuid.UUID, dict[uuid.UUID, StatValue]]
    formulas: dict[uuid.UUID, dict[uuid.UUID, Formula]]


def index_entities(content: Content) -> EntityIndex:
    index = EntityIndex(defaultdict(list), defaultdict(list), defaultdict(dict), defaultdict(dict))
    for e, p in content.prototypes:
        index.prototypes[e].append(p)
    for e, g in content.entity_groups:
        index.groups[e].append(g)
    for (e, d), value in content.stats.items():
        index.stats[e][d] = value
    for (e, d), formula in content.formulas.items():
        index.formulas[e][d] = formula
    return index


def entity_snapshot(
    content: Content, index: EntityIndex, entity_id: uuid.UUID, name: Namer
) -> dict[str, Any]:
    """What a copy link records for an entity (ADR 0119/0121)."""
    return {
        "name": content.entities[entity_id],
        "kinds": sorted(content.kinds.get(entity_id, ())),
        "in_public_catalog": content.in_public_catalog.get(entity_id),
        "slug": content.slugs.get(entity_id),
        "prototypes": sorted(name("entity", p) for p in index.prototypes.get(entity_id, [])),
        "stat_groups": sorted(name("stat_group", g) for g in index.groups.get(entity_id, [])),
        "stats": {
            name("stat_definition", d): v.as_json()
            for d, v in index.stats.get(entity_id, {}).items()
        },
        "formulas": {
            name("stat_definition", d): _formula_json(f, name)
            for d, f in index.formulas.get(entity_id, {}).items()
        },
    }


def stat_group_snapshot(content: Content, group_id: uuid.UUID) -> dict[str, Any]:
    group = content.groups[group_id]
    return {"name": group["name"], "priority": group["priority"], "mandatory": group["mandatory"]}


def stat_definition_snapshot(
    content: Content, definition_id: uuid.UUID, name: Namer
) -> dict[str, Any]:
    definition = content.definitions[definition_id]
    return {
        "name": definition["name"],
        "value_type": definition["value_type"].value,
        "stat_group": name("stat_group", definition["group"]),
        "enum_values": sorted(v for v, _ in content.enum_values.get(definition_id, [])),
    }
