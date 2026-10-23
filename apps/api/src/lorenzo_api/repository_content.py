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
    Calendar,
    CalendarObservance,
    CalendarPeriod,
    CalendarReckoning,
    Character,
    Clock,
    ClockRelationship,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatContents,
    ComputedStatLinear,
    ComputedStatSum,
    ComputedStatSumTerm,
    Containment,
    Entity,
    EntityAudience,
    EntityKnowledge,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    EntityStatGroup,
    EntryCalendarPeriod,
    EventClockReading,
    EventLearning,
    EventParticipant,
    EventRelationship,
    Fact,
    FactAbout,
    GroupMember,
    Information,
    Item,
    ItemInstance,
    Knowledge,
    LivedBefore,
    Location,
    LocationPart,
    Ownership,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    RepositoryCopy,
    RepositoryCopyLinkAttachment,
    RepositoryCopyLinkEntity,
    RepositoryCopyLinkStatDefinition,
    RepositoryCopyLinkStatGroup,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StoryEvent,
)
from lorenzo_api.models.story_context import SceneBeing, SceneEvent, SceneFact
from lorenzo_api.models.story_session import Scene, SceneAppearance, StorySession

KINDS = (
    "item",
    "item_instance",
    "being",
    "character",
    "fact",
    "calendar",
    "clock",
    "location",
    "calendar_period",
    "event",
    "observance",
)


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
    # A sum's (source, coefficient) terms, in order (ADR 0126).
    terms: list[tuple[uuid.UUID, Decimal]] | None = None

    def inputs(self) -> list[uuid.UUID]:
        own = [i for i in (self.source, self.left, self.right) if i is not None]
        return own + [source for source, _ in self.terms or []]


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
    # The attachments taken from each repository (ADR 0172), as (child origin
    # id, parent origin id) pairs, by the repository's tenant id.
    attachments: dict[uuid.UUID, set[tuple[uuid.UUID, uuid.UUID]]] = field(
        default_factory=lambda: defaultdict(set)
    )

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
    calendar_periods: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    entry_dates: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    event_relationships: list[tuple[uuid.UUID, uuid.UUID, str]] = field(default_factory=list)
    event_participants: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    event_learning: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID]] = field(default_factory=list)
    lived_before: list[tuple[uuid.UUID, uuid.UUID, uuid.UUID, bool]] = field(default_factory=list)
    shared_event_relationships: list[tuple[uuid.UUID, uuid.UUID, str]] = field(default_factory=list)
    scene_facts: dict[tuple[uuid.UUID, uuid.UUID], bool] = field(default_factory=dict)
    scene_events: dict[tuple[uuid.UUID, uuid.UUID], bool] = field(default_factory=dict)
    scene_beings: dict[tuple[uuid.UUID, uuid.UUID], bool] = field(default_factory=dict)
    scenes: dict[uuid.UUID, uuid.UUID | None] = field(default_factory=dict)
    observances: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    calendars: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    clocks: dict[uuid.UUID, bool] = field(default_factory=dict)
    # child -> {parent, ordinal}: the part-of tree (ADR 0330). The ordinal is a string.
    location_parts: dict[uuid.UUID, dict[str, Any]] = field(default_factory=dict)
    clock_readings: dict[tuple[uuid.UUID, uuid.UUID], dict[str, Any]] = field(default_factory=dict)
    clock_relationships: dict[tuple[uuid.UUID, uuid.UUID], dict[str, Any]] = field(
        default_factory=dict
    )
    calendar_reckonings: dict[tuple[uuid.UUID, uuid.UUID], dict[str, Any]] = field(
        default_factory=dict
    )
    participant_entry_audiences: list[uuid.UUID] = field(default_factory=list)
    participant_information_audiences: list[uuid.UUID] = field(default_factory=list)
    entry_audiences: dict[uuid.UUID, bool] = field(default_factory=dict)
    entry_knowledge: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
    fact_about: list[tuple[uuid.UUID, uuid.UUID]] = field(default_factory=list)
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
    for source_tenant, child, parent in await session.execute(
        select(
            RepositoryCopyLinkAttachment.source_tenant_id,
            RepositoryCopyLinkAttachment.child_source_id,
            RepositoryCopyLinkAttachment.parent_source_id,
        ).where(RepositoryCopyLinkAttachment.tenant_id == tenant_id)
    ):
        links.attachments[source_tenant].add((child, parent))
    return links


async def load_content(session: AsyncSession, tenant_id: uuid.UUID) -> Content:
    """Everything a repository can hold, for one tenant."""
    c = Content(tenant_id=tenant_id)
    t = tenant_id

    async def rows(*columns: Any, where: Any) -> Any:
        return (await session.execute(select(*columns).where(where))).all()

    for entity_id, name in await rows(Entity.id, Entity.name, where=Entity.tenant_id == t):
        c.entities[entity_id] = name
    excluded = set(
        await session.scalars(select(StorySession.entity_id).where(StorySession.tenant_id == t))
    ) | set(
        await session.scalars(
            select(SceneAppearance.entity_id).where(SceneAppearance.tenant_id == t)
        )
    )
    for entity_id in excluded:
        c.entities.pop(entity_id, None)
    for field_name, source_column, target, sharing_column, tenant_column in [
        (
            "scene_facts",
            SceneFact.scene_entity_id,
            SceneFact.fact_entity_id,
            SceneFact.is_shared,
            SceneFact.tenant_id,
        ),
        (
            "scene_events",
            SceneEvent.scene_entity_id,
            SceneEvent.event_entity_id,
            SceneEvent.is_shared,
            SceneEvent.tenant_id,
        ),
        (
            "scene_beings",
            SceneBeing.scene_entity_id,
            SceneBeing.being_entity_id,
            SceneBeing.is_shared,
            SceneBeing.tenant_id,
        ),
    ]:
        setattr(
            c,
            field_name,
            {
                (source, dest): shared
                for source, dest, shared in await rows(
                    source_column, target, sharing_column, where=tenant_column == t
                )
            },
        )
    c.scenes = dict(await rows(Scene.entity_id, Scene.period_entity_id, where=Scene.tenant_id == t))
    for entity_id in c.scenes:
        c.kinds[entity_id].add("scene")
    for entity_id, public in await rows(
        Item.entity_id, Item.in_public_catalog, where=Item.tenant_id == t
    ):
        c.kinds[entity_id].add("item")
        c.in_public_catalog[entity_id] = public
    for kind, model in (
        ("item_instance", ItemInstance),
        ("being", Being),
        ("character", Character),
        ("fact", Fact),
        ("calendar", Calendar),
        ("clock", Clock),
        ("location", Location),
        ("calendar_period", CalendarPeriod),
        ("event", StoryEvent),
        ("observance", CalendarObservance),
    ):
        for (entity_id,) in await rows(model.entity_id, where=model.tenant_id == t):
            c.kinds[entity_id].add(kind)
    for entity_id, slug in await rows(
        EntitySlug.entity_id, EntitySlug.slug, where=EntitySlug.tenant_id == t
    ):
        c.slugs[entity_id] = slug
    # In each entry's own order (ADR 0266): a copy gives the parents the same places.
    c.prototypes = [
        (e, p)
        for e, p in (
            await session.execute(
                select(EntityPrototype.entity_id, EntityPrototype.prototype_id)
                .where(EntityPrototype.tenant_id == t)
                .order_by(
                    EntityPrototype.entity_id,
                    EntityPrototype.position,
                    EntityPrototype.prototype_id,
                )
            )
        ).all()
    ]
    for group_id, name, priority, mandatory in await rows(
        StatGroup.id,
        StatGroup.name,
        StatGroup.priority,
        StatGroup.mandatory,
        where=StatGroup.tenant_id == t,
    ):
        c.groups[group_id] = {"name": name, "priority": priority, "mandatory": mandatory}
    for (
        def_id,
        name,
        value_type,
        group_id,
        unit,
        adjustable,
        pin,
        signed,
        position,
        max_hint,
        min_hint,
        resolved_hint,
    ) in await rows(
        StatDefinition.id,
        StatDefinition.name,
        StatDefinition.value_type,
        StatDefinition.stat_group_id,
        StatDefinition.unit,
        StatDefinition.adjustable_in_play,
        StatDefinition.pin,
        StatDefinition.signed,
        StatDefinition.position,
        StatDefinition.max_hint_id,
        StatDefinition.min_hint_id,
        StatDefinition.resolved_hint_id,
        where=StatDefinition.tenant_id == t,
    ):
        c.definitions[def_id] = {
            "name": name,
            "value_type": value_type,
            "group": group_id,
            "unit": unit,
            "adjustable_in_play": adjustable,
            "pin": pin,
            "signed": signed,
            "position": position,
            "hints": {
                "max_hint": max_hint,
                "min_hint": min_hint,
                "resolved_hint": resolved_hint,
            },
        }
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
    sums = {
        (row.entity_id, row.stat_definition_id): row
        for row in (
            await session.scalars(select(ComputedStatSum).where(ComputedStatSum.tenant_id == t))
        )
    }
    terms: dict[tuple[uuid.UUID, uuid.UUID], list[tuple[uuid.UUID, Decimal]]] = defaultdict(list)
    for term in await session.scalars(
        select(ComputedStatSumTerm)
        .where(ComputedStatSumTerm.tenant_id == t)
        .order_by(ComputedStatSumTerm.position)
    ):
        terms[(term.entity_id, term.stat_definition_id)].append(
            (term.source_stat_definition_id, term.coefficient)
        )
    contained = {
        (row.entity_id, row.stat_definition_id): row.source_stat_definition_id
        for row in (
            await session.scalars(
                select(ComputedStatContents).where(ComputedStatContents.tenant_id == t)
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
        elif (e, d) in contained:
            c.formulas[(e, d)] = Formula(kind="contents", source=contained[(e, d)])
        elif (e, d) in sums:
            c.formulas[(e, d)] = Formula(
                kind="sum",
                offset=sums[(e, d)].offset,
                round_mode=sums[(e, d)].round_mode,
                terms=terms[(e, d)],
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
    c.calendar_periods = {
        p.entity_id: {
            "calendar": p.calendar_entity_id,
            "year": p.year,
            "segment": p.segment,
            "day": p.day,
            "parent": p.parent_entity_id,
        }
        for p in await session.scalars(select(CalendarPeriod).where(CalendarPeriod.tenant_id == t))
    }
    c.event_learning = [
        (e, b, i)
        for e, b, i in await rows(
            EventLearning.event_entity_id,
            EventLearning.being_entity_id,
            EventLearning.information_id,
            where=EventLearning.tenant_id == t,
        )
    ]
    c.event_participants = [
        (e, b)
        for e, b in await rows(
            EventParticipant.event_entity_id,
            EventParticipant.being_entity_id,
            where=EventParticipant.tenant_id == t,
        )
    ]
    c.lived_before = [
        (b, a, z, shared)
        for b, a, z, shared in await rows(
            LivedBefore.being_entity_id,
            LivedBefore.from_event_id,
            LivedBefore.to_event_id,
            LivedBefore.is_shared,
            where=LivedBefore.tenant_id == t,
        )
    ]
    c.shared_event_relationships = [
        (source, target, kind)
        for source, target, kind in await rows(
            EventRelationship.from_event_id,
            EventRelationship.to_event_id,
            EventRelationship.kind,
            where=(EventRelationship.tenant_id == t) & EventRelationship.is_shared.is_(True),
        )
    ]
    c.event_relationships = [
        (source, target, kind)
        for source, target, kind in await rows(
            EventRelationship.from_event_id,
            EventRelationship.to_event_id,
            EventRelationship.kind,
            where=EventRelationship.tenant_id == t,
        )
    ]
    c.entry_dates = [
        (entity_id, period_id)
        for entity_id, period_id in await rows(
            EntryCalendarPeriod.entity_id,
            EntryCalendarPeriod.period_entity_id,
            where=EntryCalendarPeriod.tenant_id == t,
        )
    ]
    c.observances = {
        entity_id: {"calendar": calendar_id, "rule": rule}
        for entity_id, calendar_id, rule in await rows(
            CalendarObservance.entity_id,
            CalendarObservance.calendar_entity_id,
            CalendarObservance.rule,
            where=CalendarObservance.tenant_id == t,
        )
    }
    c.calendars = dict(
        await rows(Calendar.entity_id, Calendar.definition, where=Calendar.tenant_id == t)
    )
    c.clocks = dict(await rows(Clock.entity_id, Clock.ticking, where=Clock.tenant_id == t))
    c.location_parts = {
        child: {"parent": parent, "ordinal": None if ordinal is None else str(ordinal)}
        for child, parent, ordinal in await rows(
            LocationPart.child_entity_id,
            LocationPart.parent_entity_id,
            LocationPart.level_ordinal,
            where=LocationPart.tenant_id == t,
        )
    }
    clock_sources: list[tuple[type[EventClockReading] | type[CalendarReckoning], str, Any]] = [
        (EventClockReading, "clock_readings", EventClockReading.event_entity_id),
        (CalendarReckoning, "calendar_reckonings", CalendarReckoning.calendar_entity_id),
    ]
    for clock_model, field_name, source in clock_sources:
        setattr(
            c,
            field_name,
            {
                (e, k): {"data": data, "is_shared": shared}
                for e, k, data, shared in await rows(
                    source,
                    clock_model.clock_entity_id,
                    clock_model.data,
                    clock_model.is_shared,
                    where=clock_model.tenant_id == t,
                )
            },
        )
    c.clock_relationships = {
        (first, second): {"data": data, "is_shared": shared}
        for first, second, data, shared in await rows(
            ClockRelationship.clock_entity_id,
            ClockRelationship.reference_clock_entity_id,
            ClockRelationship.data,
            ClockRelationship.is_shared,
            where=ClockRelationship.tenant_id == t,
        )
    }
    c.entry_audiences = dict(
        await rows(
            EntityAudience.entity_id, EntityAudience.is_public, where=EntityAudience.tenant_id == t
        )
    )
    c.participant_entry_audiences = [
        e
        for (e,) in await rows(
            EntityAudience.entity_id,
            where=(EntityAudience.tenant_id == t)
            & EntityAudience.shared_with_participants.is_(True),
        )
    ]
    c.participant_information_audiences = [
        i
        for (i,) in await rows(
            Information.id,
            where=(Information.tenant_id == t) & Information.shared_with_participants.is_(True),
        )
    ]
    c.entry_knowledge = [
        (e, k)
        for e, k in await rows(
            EntityKnowledge.entity_id,
            EntityKnowledge.knower_entity_id,
            where=(EntityKnowledge.tenant_id == t) & EntityKnowledge.knower_entity_id.is_not(None),
        )
    ]
    c.fact_about = [
        (f, subject)
        for f, subject in await rows(
            FactAbout.fact_entity_id, FactAbout.subject_entity_id, where=FactAbout.tenant_id == t
        )
    ]
    c.knowledge = [
        (info_id, knower)
        for info_id, knower in await rows(
            Knowledge.information_id,
            Knowledge.knower_entity_id,
            where=(Knowledge.tenant_id == t) & Knowledge.knower_entity_id.is_not(None),
        )
    ]
    c.links = await load_links(session, t)
    excluded_information = {i for i, info in c.information.items() if info.entity_id in excluded}
    for i in excluded_information:
        del c.information[i]
    c.payloads = {
        i: p for i, p in c.payloads.items() if p.information_id not in excluded_information
    }
    c.knowledge = [
        (i, k) for i, k in c.knowledge if i not in excluded_information and k not in excluded
    ]
    c.slugs = {e: slug for e, slug in c.slugs.items() if e not in excluded}
    c.entry_audiences = {e: public for e, public in c.entry_audiences.items() if e not in excluded}
    c.entry_knowledge = [
        (e, k) for e, k in c.entry_knowledge if e not in excluded and k not in excluded
    ]
    c.entry_dates = [(e, p) for e, p in c.entry_dates if e not in excluded]
    c.prototypes = [(e, p) for e, p in c.prototypes if e not in excluded and p not in excluded]
    c.entity_groups = [(e, g) for e, g in c.entity_groups if e not in excluded]
    c.stats = {(e, d): value for (e, d), value in c.stats.items() if e not in excluded}
    c.formulas = {(e, d): value for (e, d), value in c.formulas.items() if e not in excluded}
    c.fact_about = [(f, e) for f, e in c.fact_about if e not in excluded]
    c.event_learning = [(e, b, i) for e, b, i in c.event_learning if i not in excluded_information]
    c.participant_information_audiences = [
        i for i in c.participant_information_audiences if i not in excluded_information
    ]
    c.participant_entry_audiences = [e for e in c.participant_entry_audiences if e not in excluded]
    return c


# --- Attachments (ADR 0172) --------------------------------------------------


@dataclass(frozen=True)
class Attachment:
    """A parent a repository added to an entity it holds a copy of. `child` and
    `parent` are the repository's own ids for the two entities; the `_source_id`s
    are their origins, which is how any tenant that copies the repository finds its
    own rows for them (ADR 0120)."""

    child: uuid.UUID
    parent: uuid.UUID
    child_source_id: uuid.UUID
    parent_source_id: uuid.UUID

    @property
    def pair(self) -> tuple[uuid.UUID, uuid.UUID]:
        return (self.child_source_id, self.parent_source_id)


def attachments_of(content: Content) -> list[Attachment]:
    """The attachments of a tenant that holds copies: every parent one of its
    copied entities has now that the copy link's snapshot, taken when it was
    copied or last synced, does not list. The snapshot names parents by origin, so
    whose edge it is needs no guessing: what arrived with the copy is in it, and
    what is beyond it was added here. A parent removed from a copy is no
    attachment, and an entity of the tenant's own has parents, not attachments."""
    found: list[Attachment] = []
    for child, parent in content.prototypes:
        if content.own("entity", child):
            continue
        child_source = content.origin("entity", child)
        parent_source = content.origin("entity", parent)
        listed = content.links.snapshots.get(child_source, {}).get("prototypes", [])
        if str(parent_source) not in listed:
            found.append(Attachment(child, parent, child_source, parent_source))
    return sorted(found, key=lambda a: (str(a.child_source_id), str(a.parent_source_id)))


async def load_attachment_content(session: AsyncSession, tenant_id: uuid.UUID) -> Content:
    """The part of a tenant's content `attachments_of` reads - entity names, prototype
    edges and copy links - without the stats and payloads `load_content` would bring."""
    c = Content(tenant_id=tenant_id)
    for entity_id, name in await session.execute(
        select(Entity.id, Entity.name).where(Entity.tenant_id == tenant_id)
    ):
        c.entities[entity_id] = name
    for entity_id, prototype_id in await session.execute(
        select(EntityPrototype.entity_id, EntityPrototype.prototype_id).where(
            EntityPrototype.tenant_id == tenant_id
        )
    ):
        c.prototypes.append((entity_id, prototype_id))
    c.links = await load_links(session, tenant_id)
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
    if formula.kind == "contents":
        assert formula.source is not None
        return {"kind": "contents", "source": name("stat_definition", formula.source)}
    if formula.kind == "sum":
        assert formula.terms is not None
        return {
            "kind": "sum",
            "terms": [
                {"source": name("stat_definition", source), "coefficient": str(coefficient)}
                for source, coefficient in formula.terms
            ],
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
    clock_records: dict[uuid.UUID, list[tuple[str, uuid.UUID, dict[str, Any]]]]


def index_entities(content: Content) -> EntityIndex:
    index = EntityIndex(
        defaultdict(list),
        defaultdict(list),
        defaultdict(dict),
        defaultdict(dict),
        defaultdict(list),
    )
    for e, p in content.prototypes:
        index.prototypes[e].append(p)
    for e, g in content.entity_groups:
        index.groups[e].append(g)
    for (e, d), value in content.stats.items():
        index.stats[e][d] = value
    for (e, d), formula in content.formulas.items():
        index.formulas[e][d] = formula
    for field_name in ("clock_readings", "calendar_reckonings"):
        for (source, clock), clock_value in getattr(content, field_name).items():
            index.clock_records[source].append((field_name, clock, clock_value))
    from lorenzo_api.clock_conversion import RelationDefinition

    for (first, second), clock_value in content.clock_relationships.items():
        definition = RelationDefinition.model_validate(clock_value["data"])
        index.clock_records[first].append(("clock_relationships", second, clock_value))
        index.clock_records[second].append(
            (
                "clock_relationships",
                first,
                {"data": definition.inverse().model_dump(), "is_shared": clock_value["is_shared"]},
            )
        )
    return index


def entity_snapshot(
    content: Content, index: EntityIndex, entity_id: uuid.UUID, name: Namer
) -> dict[str, Any]:
    """What a copy link records for an entity (ADR 0119/0121)."""
    clock_fields: dict[str, Any] = {}
    for field_name, clock_id, value in index.clock_records.get(entity_id, []):
        clock_fields.setdefault(field_name, []).append({"clock": name("entity", clock_id), **value})
    for records in clock_fields.values():
        records.sort(key=lambda record: record["clock"])
    return {
        **clock_fields,
        **({"clock_ticking": content.clocks[entity_id]} if entity_id in content.clocks else {}),
        **(
            {
                "part_of": {
                    "parent": name("entity", content.location_parts[entity_id]["parent"]),
                    "ordinal": content.location_parts[entity_id]["ordinal"],
                }
            }
            if entity_id in content.location_parts
            else {}
        ),
        **(
            {"calendar_definition": content.calendars[entity_id]}
            if entity_id in content.calendars
            else {}
        ),
        **(
            {"observance_rule": content.observances[entity_id]["rule"]}
            if entity_id in content.observances
            else {}
        ),
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


def assert_acyclic(parts: dict[uuid.UUID, dict[str, Any]]) -> None:
    """The part-of tree holds no cycle. The route guards it on write; a tree that arrives
    another way is refused where it would be copied or published (ADR 0330)."""
    from lorenzo_api.exceptions import LocationTreeError

    for start in parts:
        seen = {start}
        node = parts[start]["parent"]
        while node in parts:
            if node in seen:
                raise LocationTreeError()
            seen.add(node)
            node = parts[node]["parent"]


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
        "unit": definition["unit"],
        "adjustable_in_play": definition["adjustable_in_play"],
        "pin": definition["pin"],
        "signed": definition["signed"],
        **{
            key: name("stat_definition", hinted) if hinted is not None else None
            for key, hinted in definition["hints"].items()
        },
    }


def public_entry(content: Content, entity_id: uuid.UUID) -> bool:
    if not content.entry_audiences.get(entity_id, True):
        return False
    period = content.calendar_periods.get(entity_id) or content.observances.get(entity_id)
    return period is None or content.entry_audiences.get(period["calendar"], True)
