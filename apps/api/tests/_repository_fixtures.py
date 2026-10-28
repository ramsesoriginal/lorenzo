"""One row in every repository content table (ADR 0118) - for the RLS
tests, which need each table to have something to hide or show.
"""

import hashlib
import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api import release_document
from lorenzo_api.models import (
    Being,
    Book,
    Calendar,
    CalendarObservance,
    CalendarPeriod,
    CalendarReckoning,
    Chapter,
    Character,
    Clock,
    ClockRelationship,
    ComputedStat,
    ComputedStatComparison,
    ComputedStatContents,
    ComputedStatLinear,
    ComputedStatSum,
    ComputedStatSumTerm,
    Connection,
    Containment,
    ContentReference,
    Edition,
    Entity,
    EntityAudience,
    EntityKnowledge,
    EntityLocation,
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
    ManuscriptPlacement,
    Map,
    MapLayer,
    MapPlacement,
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
    RepositoryRelease,
    RepositoryReleaseBlob,
    RepositoryReleaseDocument,
    RepositoryReleasedRow,
    RepositoryShowcase,
    Scene,
    SceneTelling,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
    StoryEvent,
    WritingBiography,
)
from lorenzo_api.models.story_context import SceneBeing, SceneEvent, SceneFact
from lorenzo_api.repository_content import Content


async def seed_every_content_table(
    session: AsyncSession, tenant_id: uuid.UUID, *, with_copy_records: bool = False
) -> None:
    """Flushes, doesn't commit. `with_copy_records` adds a copy record and
    one copy link of each kind, as if this tenant had copied something -
    for the RLS tests, which need a row in every table; a tenant copying
    this one would then see those rows as copies, not its own.
    """

    def entity(name: str) -> Entity:
        e = Entity(tenant_id=tenant_id, name=name)
        session.add(e)
        return e

    sword, blade, chest, guild, elminster = (
        entity("Sword"),
        entity("Blade"),
        entity("Chest"),
        entity("Harpers"),
        entity("Elminster"),
    )
    scene = entity("Fixture Scene")
    calendar = entity("Fixture calendar")
    clock = entity("Fixture clock")
    place = entity("Fixture place")
    room = entity("Fixture room")
    reference_clock = entity("Fixture reference clock")
    period = entity("Fixture year")
    event = entity("Fixture event")
    later_event = entity("Later fixture Event")
    observance = entity("Fixture observance")
    fact = entity("The blade belongs to Elminster")
    chart = entity("Fixture map")
    road = entity("Fixture road")
    group = StatGroup(tenant_id=tenant_id, name="Abilities")
    session.add(group)
    await session.flush()

    session.add_all(
        [
            Clock(entity_id=clock.id, tenant_id=tenant_id),
            Location(entity_id=place.id, tenant_id=tenant_id),
            Location(entity_id=room.id, tenant_id=tenant_id),
            Connection(
                entity_id=road.id, tenant_id=tenant_id, end_a=place.id, end_b=room.id, one_way=True
            ),
            Map(
                entity_id=chart.id,
                tenant_id=tenant_id,
                system={
                    "format": "lorenzo.map-system/1",
                    "kind": "plane",
                    "extent": [0, 0, 10, 10],
                },
                theme_hint="plain",
                view={"grid": {"kind": "square", "cell": {"size": 2}}},
            ),
            Clock(entity_id=reference_clock.id, tenant_id=tenant_id),
            EntityAudience(entity_id=reference_clock.id, tenant_id=tenant_id, is_public=False),
            EntityAudience(entity_id=clock.id, tenant_id=tenant_id, is_public=False),
            Calendar(
                entity_id=calendar.id,
                tenant_id=tenant_id,
                definition={
                    "format": "lorenzo.calendar/1",
                    "segments": [{"key": "month", "name": "Month", "days": 30}],
                },
            ),
            EntityAudience(entity_id=scene.id, tenant_id=tenant_id, is_public=False),
            Fact(entity_id=fact.id, tenant_id=tenant_id),
            EntityAudience(entity_id=fact.id, tenant_id=tenant_id, is_public=False),
        ]
    )
    await session.flush()
    session.add_all(
        [
            FactAbout(fact_entity_id=fact.id, subject_entity_id=blade.id, tenant_id=tenant_id),
            EntityKnowledge(entity_id=fact.id, knower_entity_id=guild.id, tenant_id=tenant_id),
        ]
    )

    session.add_all(
        [
            CalendarObservance(
                entity_id=observance.id,
                tenant_id=tenant_id,
                calendar_entity_id=calendar.id,
                rule={"segment": "month", "day": 1, "when": {"every": 1, "offset": 0}},
            ),
            EntityAudience(entity_id=observance.id, tenant_id=tenant_id, is_public=False),
            StoryEvent(entity_id=event.id, tenant_id=tenant_id),
            StoryEvent(entity_id=later_event.id, tenant_id=tenant_id),
            CalendarPeriod(
                entity_id=period.id,
                tenant_id=tenant_id,
                calendar_entity_id=calendar.id,
                year=0,
                segment=None,
                day=None,
                parent_entity_id=None,
            ),
            EntityAudience(entity_id=event.id, tenant_id=tenant_id, is_public=False),
            EntityAudience(entity_id=later_event.id, tenant_id=tenant_id, is_public=False),
            EntityAudience(entity_id=period.id, tenant_id=tenant_id, is_public=False),
        ]
    )
    await session.flush()
    session.add_all(
        [
            EntityLocation(entity_id=calendar.id, location_entity_id=place.id, tenant_id=tenant_id),
            MapPlacement(
                map_entity_id=chart.id,
                entry_entity_id=place.id,
                tenant_id=tenant_id,
                geometry={
                    "format": "lorenzo.geometry/1",
                    "parts": [{"shape": "point", "at": [1, 2]}],
                },
                role="site",
                style=None,
                z=0,
                bytes=70,
                minx=1,
                miny=2,
                maxx=1,
                maxy=2,
            ),
            LocationPart(
                child_entity_id=room.id,
                parent_entity_id=place.id,
                tenant_id=tenant_id,
                level_ordinal=Decimal("1.5"),
            ),
            EventClockReading(
                event_entity_id=event.id,
                clock_entity_id=clock.id,
                tenant_id=tenant_id,
                data={"lo": "1/3", "hi": "2/3", "lo_inclusive": True, "hi_inclusive": False},
                is_shared=True,
            ),
            CalendarReckoning(
                calendar_entity_id=calendar.id,
                clock_entity_id=clock.id,
                tenant_id=tenant_id,
                data={"date": {"year": 0, "segment": "month", "day": 1}, "reading": "0"},
                is_shared=True,
            ),
        ]
    )
    from lorenzo_api.clock_conversion import RelationDefinition, canonical

    first, second, definition = canonical(
        clock.id,
        reference_clock.id,
        RelationDefinition(ratio="2", clock_anchor="34", reference_anchor="17"),
    )
    session.add(
        ClockRelationship(
            tenant_id=tenant_id,
            clock_entity_id=first,
            reference_clock_entity_id=second,
            data=definition.model_dump(),
            is_shared=True,
        )
    )
    session.add(Scene(entity_id=scene.id, tenant_id=tenant_id, period_entity_id=period.id))
    await session.flush()
    context_rows = [
        SceneFact(tenant_id=tenant_id, scene_entity_id=scene.id, fact_entity_id=fact.id),
        SceneEvent(tenant_id=tenant_id, scene_entity_id=scene.id, event_entity_id=event.id),
        SceneBeing(tenant_id=tenant_id, scene_entity_id=scene.id, being_entity_id=elminster.id),
    ]
    session.add(
        EntryCalendarPeriod(entity_id=event.id, period_entity_id=period.id, tenant_id=tenant_id)
    )

    session.add(
        EventRelationship(
            tenant_id=tenant_id, from_event_id=event.id, to_event_id=later_event.id, kind="causes"
        )
    )
    strength = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Strength", value_type=StatValueType.INT
    )
    modifier = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Modifier", value_type=StatValueType.INT
    )
    strong = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Strong", value_type=StatValueType.BOOL
    )
    alignment = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Alignment", value_type=StatValueType.ENUM
    )
    might = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Might", value_type=StatValueType.INT
    )
    load = StatDefinition(
        tenant_id=tenant_id, stat_group_id=group.id, name="Load", value_type=StatValueType.INT
    )
    session.add_all([strength, modifier, strong, alignment, might, load])
    session.add_all(
        [
            Item(entity_id=sword.id, tenant_id=tenant_id),
            ItemInstance(entity_id=blade.id, tenant_id=tenant_id),
            Item(entity_id=chest.id, tenant_id=tenant_id),
            Being(entity_id=elminster.id, tenant_id=tenant_id),
        ]
    )
    await session.flush()
    session.add_all(
        [
            Character(entity_id=elminster.id, tenant_id=tenant_id),
            StatDefinitionEnumValue(
                tenant_id=tenant_id, stat_definition_id=alignment.id, value="neutral"
            ),
            EntityPrototype(entity_id=blade.id, prototype_id=sword.id, tenant_id=tenant_id),
            EntitySlug(entity_id=sword.id, tenant_id=tenant_id, slug=f"sword-{uuid.uuid4().hex}"),
            EntityStatGroup(entity_id=sword.id, stat_group_id=group.id, tenant_id=tenant_id),
            EntityStat(
                entity_id=sword.id,
                stat_definition_id=strength.id,
                tenant_id=tenant_id,
                value_int=16,
            ),
            ComputedStat(entity_id=sword.id, stat_definition_id=modifier.id, tenant_id=tenant_id),
            ComputedStat(entity_id=sword.id, stat_definition_id=strong.id, tenant_id=tenant_id),
            ComputedStat(entity_id=sword.id, stat_definition_id=might.id, tenant_id=tenant_id),
            ComputedStat(entity_id=chest.id, stat_definition_id=load.id, tenant_id=tenant_id),
            Containment(child_entity_id=blade.id, parent_entity_id=chest.id, tenant_id=tenant_id),
            Ownership(owned_entity_id=blade.id, owner_character_id=guild.id, tenant_id=tenant_id),
        ]
    )
    await session.flush()
    session.add_all(
        [
            ComputedStatLinear(
                entity_id=sword.id,
                stat_definition_id=modifier.id,
                tenant_id=tenant_id,
                source_stat_definition_id=strength.id,
                multiplier=Decimal("0.5"),
                offset=Decimal("-5"),
                round_mode="floor",
            ),
            ComputedStatComparison(
                entity_id=sword.id,
                stat_definition_id=strong.id,
                tenant_id=tenant_id,
                left_stat_definition_id=strength.id,
                comparator="ge",
                right_constant=Decimal("15"),
            ),
            # The Chest's Load: the Strength of what's in it (ADR 0127).
            ComputedStatContents(
                entity_id=chest.id,
                stat_definition_id=load.id,
                tenant_id=tenant_id,
                source_stat_definition_id=strength.id,
            ),
            # Might = Strength + 2 × Modifier + 1 (ADR 0126).
            ComputedStatSum(
                entity_id=sword.id,
                stat_definition_id=might.id,
                tenant_id=tenant_id,
                offset=Decimal("1"),
                round_mode="none",
            ),
            GroupMember(
                group_entity_id=guild.id, character_entity_id=elminster.id, tenant_id=tenant_id
            ),
        ]
    )
    await session.flush()
    session.add_all(
        [
            ComputedStatSumTerm(
                entity_id=sword.id,
                stat_definition_id=might.id,
                tenant_id=tenant_id,
                source_stat_definition_id=strength.id,
                coefficient=Decimal("1"),
                position=0,
            ),
            ComputedStatSumTerm(
                entity_id=sword.id,
                stat_definition_id=might.id,
                tenant_id=tenant_id,
                source_stat_definition_id=modifier.id,
                coefficient=Decimal("2"),
                position=1,
            ),
        ]
    )
    info = Information(
        tenant_id=tenant_id, entity_id=sword.id, title="Lore", type="description", is_public=True
    )
    session.add(info)
    await session.flush()
    payloads = [Payload(tenant_id=tenant_id, information_id=info.id, order=i) for i in range(4)]
    session.add_all(payloads)
    await session.flush()
    session.add_all(
        [
            PayloadDescription(
                payload_id=payloads[0].id,
                tenant_id=tenant_id,
                locale="en",
                content="Forged for [[elminster]].",
            ),
            PayloadNumber(payload_id=payloads[1].id, tenant_id=tenant_id, value=Decimal("3")),
            PayloadPicture(
                payload_id=payloads[2].id, tenant_id=tenant_id, data=b"\x89PNG", file_type="png"
            ),
            PayloadDocument(
                payload_id=payloads[3].id,
                tenant_id=tenant_id,
                data=b"%PDF",
                filename="lore.pdf",
                file_type="pdf",
            ),
            ContentReference(
                payload_id=payloads[0].id,
                position=0,
                tenant_id=tenant_id,
                kind="entity",
                target="elminster",
            ),
            Knowledge(tenant_id=tenant_id, knower_entity_id=elminster.id, information_id=info.id),
        ]
    )
    # A picture under the Map (ADR 0361): its own Information, a picture payload and a layer.
    backdrop = Information(
        tenant_id=tenant_id, entity_id=chart.id, title="Backdrop", type="picture", is_public=True
    )
    session.add(backdrop)
    await session.flush()
    backdrop_payload = Payload(tenant_id=tenant_id, information_id=backdrop.id, order=0)
    session.add(backdrop_payload)
    await session.flush()
    session.add_all(
        [
            PayloadPicture(
                payload_id=backdrop_payload.id,
                tenant_id=tenant_id,
                data=b"\x89PNG",
                file_type="image/png",
            ),
            MapLayer(
                map_entity_id=chart.id,
                position=0,
                information_id=backdrop.id,
                tenant_id=tenant_id,
                calibration={
                    "anchors": [
                        {"image": [0, 0], "at": [0, 0]},
                        {"image": [1, 1], "at": [10, 10]},
                    ]
                },
                opacity=0.5,
                reviewed_sha256=hashlib.sha256(b"\x89PNG").digest(),
            ),
        ]
    )
    session.add(
        EventParticipant(
            tenant_id=tenant_id, event_entity_id=event.id, being_entity_id=elminster.id
        )
    )
    await session.flush()
    session.add(
        EventParticipant(
            tenant_id=tenant_id, event_entity_id=later_event.id, being_entity_id=elminster.id
        )
    )
    await session.flush()
    session.add(
        LivedBefore(
            tenant_id=tenant_id,
            being_entity_id=elminster.id,
            from_event_id=event.id,
            to_event_id=later_event.id,
            is_shared=True,
        )
    )
    session.add(
        EventLearning(
            tenant_id=tenant_id,
            event_entity_id=event.id,
            being_entity_id=elminster.id,
            information_id=info.id,
        )
    )
    release = RepositoryRelease(
        id=uuid.uuid4(), tenant_id=tenant_id, number=1, label="Seed", notes="Seeded."
    )
    session.add(release)
    # Its document, and the one file it refers to (ADR 0214).
    file = b"\x89PNG"
    sha256 = hashlib.sha256(file).hexdigest()
    session.add(RepositoryReleaseBlob(tenant_id=tenant_id, sha256=sha256, data=file))
    session.add(
        RepositoryReleaseDocument(
            release_id=release.id,
            tenant_id=tenant_id,
            format=release_document.FORMAT,
            content=release_document.dumps(
                release_document.encode(Content(tenant_id=tenant_id))[0]
            ),
            blobs=[sha256],
        )
    )
    session.add(RepositoryShowcase(tenant_id=tenant_id, entity_id=sword.id, position=0))
    session.add(
        RepositoryReleasedRow(
            tenant_id=tenant_id, kind="entity", row_id=sword.id, hash="0" * 64, name="Sword"
        )
    )
    session.add_all(context_rows)
    await session.flush()
    telling = entity("Telling")
    await session.flush()
    session.add_all(
        [
            SceneTelling(
                entity_id=telling.id,
                tenant_id=tenant_id,
                scene_entity_id=scene.id,
                viewpoint_entity_id=elminster.id,
            ),
            WritingBiography(entity_id=elminster.id, tenant_id=tenant_id),
        ]
    )
    book, edition, chapter = entity("Book"), entity("Edition"), entity("Chapter")
    await session.flush()
    session.add_all(
        [
            Book(entity_id=book.id, tenant_id=tenant_id),
            Chapter(entity_id=chapter.id, tenant_id=tenant_id),
        ]
    )
    await session.flush()
    session.add(Edition(entity_id=edition.id, book_entity_id=book.id, tenant_id=tenant_id))
    await session.flush()
    session.add(
        ManuscriptPlacement(
            child_entity_id=chapter.id,
            parent_entity_id=edition.id,
            before_payload_id=None,
            position=0,
            tenant_id=tenant_id,
        )
    )
    await session.flush()
    if not with_copy_records:
        await session.flush()
        return
    # As if this tenant had copied something itself (ADR 0119): a bridge's
    # copy records are content its subscribers read (ADR 0120).
    upstream = uuid.uuid4()
    link = {"tenant_id": tenant_id, "source_tenant_id": upstream, "snapshot": {}}
    session.add_all(
        [
            RepositoryCopy(tenant_id=tenant_id, repository_tenant_id=upstream),
            RepositoryCopyLinkEntity(**link, entity_id=chest.id, source_id=uuid.uuid4()),
            RepositoryCopyLinkStatGroup(
                **link, stat_group_id=group.id, source_id=uuid.uuid4(), mode="copied"
            ),
            RepositoryCopyLinkStatDefinition(
                **link, stat_definition_id=strength.id, source_id=uuid.uuid4(), mode="copied"
            ),
        ]
    )
    await session.flush()
