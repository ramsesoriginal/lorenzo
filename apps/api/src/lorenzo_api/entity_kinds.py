"""What an entry is: making one with kinds, adding and removing a kind, deleting one, and which
combinations of kinds a repository may publish (ADR 0217, RFC 0041 section 2).

An entry's kinds are the marker rows it has (`item`, `item_instance`, `being`, `character`): the
entity table says nothing about kind (ADR 0012). These functions are the one write path to the
two markers a route may add, `item` and `being`; `item_instance` and `character` have their own
routes (an inventory item is made from a catalog item, a being becomes a character by promotion).
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable, Sequence
from typing import Any, Literal

from lorenzo_map import MapDocumentError, validate_system
from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.client_ids import insert_with_client_id
from lorenzo_api.exceptions import (
    EntityKindInUseError,
    EntitySlugConflictError,
    InvalidKindRequestError,
    InvalidPrototypeError,
    InventoryItemKindError,
    ItemPrototypeInUseError,
)
from lorenzo_api.learning import require_no_learning
from lorenzo_api.maps import require_map_room
from lorenzo_api.models import (
    Being,
    Calendar,
    CalendarObservance,
    CalendarPeriod,
    Campaign,
    Character,
    Clock,
    Entity,
    EntityAudience,
    EntityPrototype,
    EntitySlug,
    EntryCalendarPeriod,
    EventParticipant,
    Fact,
    Item,
    ItemInstance,
    Location,
    Map,
    StoryEvent,
)
from lorenzo_api.models.story_session import Scene, SceneAppearance, StorySession

# The kinds a route may add or remove.
Kind = Literal["item", "being", "fact", "event", "location", "map"]

# The combinations of kinds a repository may be published with, each as its kinds in the order
# `entity_snapshot` writes them (alphabetical). A draft repository may hold any combination the
# routes allow; publishing is gated by this list (RFC 0041 section 2), and the round-trip matrix
# (tests/test_kind_matrix.py) holds it complete: a combination is added here together with its
# row in the matrix, and a row in the matrix is not a combination until it is added here.
# `item_instance` and `being` + `character` are what repositories held before kinds could be
# combined, and the matrix covers them.
PUBLISHABLE_KIND_COMBINATIONS: frozenset[tuple[str, ...]] = frozenset(
    {
        (),
        ("item",),
        ("fact",),
        ("calendar",),
        ("clock",),
        ("calendar_period",),
        ("event",),
        ("observance",),
        ("scene",),
        ("being",),
        ("being", "item"),
        ("item_instance",),
        ("being", "character"),
        # ADR 0331: a Location beside every other kind. Pairs only; a triple is not published
        # until it is proven.
        ("location",),
        ("being", "location"),
        ("calendar", "location"),
        ("calendar_period", "location"),
        ("clock", "location"),
        ("event", "location"),
        ("fact", "location"),
        ("item", "location"),
        ("item_instance", "location"),
        ("location", "observance"),
        ("location", "scene"),
        # ADR 0336: a Map beside every other kind, pairs only.
        ("map",),
        ("being", "map"),
        ("calendar", "map"),
        ("calendar_period", "map"),
        ("clock", "map"),
        ("event", "map"),
        ("fact", "map"),
        ("item", "map"),
        ("item_instance", "map"),
        ("location", "map"),
        ("map", "observance"),
        ("map", "scene"),
    }
)


# The kinds whose outer audience belongs to them: removing a Location leaves that row alone.
_AUDIENCE_KINDS = frozenset(
    {
        "fact",
        "calendar",
        "clock",
        "calendar_period",
        "event",
        "observance",
        "scene",
        "session",
        "scene_appearance",
    }
)


async def create_entry(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    slug: str | None,
    kinds: Collection[Kind],
    parents: Sequence[uuid.UUID],
    in_public_catalog: bool,
    entity_id: uuid.UUID | None = None,
    system: dict[str, Any] | None = None,
) -> Entity:
    """The entry, its link name, its marker rows and its parent edges, flushed in the caller's
    transaction. A taken link name is a 409 and a parent that is not an entry of the tenant a
    422, before anything is written."""
    if slug is not None:
        taken = await session.scalar(
            select(EntitySlug.entity_id).where(
                EntitySlug.tenant_id == tenant_id, EntitySlug.slug == slug
            )
        )
        if taken is not None:
            raise EntitySlugConflictError(
                detail=f"Slug {slug!r} is already in use in tenant {tenant_id}"
            )
    if "event" in kinds and set(kinds) - {"location", "map"} != {"event"}:
        raise InvalidKindRequestError(
            detail="An Event does not combine with other kinds in this slice."
        )
    if "fact" in kinds and set(kinds) - {"location", "map"} != {"fact"}:
        raise InvalidKindRequestError(
            detail="A fact is an information anchor; other kinds are a later slice."
        )
    stored_system: dict[str, Any] | None = None
    if "map" in kinds:
        if system is None:
            raise InvalidKindRequestError(
                detail="A Map needs its system: use POST /maps or add the kind to an entry."
            )
        try:
            stored_system = validate_system(system)
        except MapDocumentError as error:
            raise InvalidKindRequestError(detail=error.reason) from None
        await require_map_room(session, tenant_id=tenant_id)
    wanted = set(parents)
    if wanted:
        found = set(
            await session.scalars(
                select(Entity.id).where(Entity.id.in_(wanted), Entity.tenant_id == tenant_id)
            )
        )
        if missing := wanted - found:
            raise InvalidPrototypeError(
                detail=(
                    f"Parent id(s) {sorted(str(i) for i in missing)} do not exist "
                    f"in tenant {tenant_id}"
                )
            )
    entity = Entity(tenant_id=tenant_id, name=name, created_by=user_id, updated_by=user_id)
    if entity_id is None:
        session.add(entity)
        await session.flush()
    else:
        # The client made the id (ADR 0222): a clash on it is the generic 409.
        entity.id = entity_id
        await insert_with_client_id(session, entity)
    if slug is not None:
        session.add(EntitySlug(entity_id=entity.id, tenant_id=tenant_id, slug=slug))
    if "item" in kinds:
        session.add(
            Item(entity_id=entity.id, tenant_id=tenant_id, in_public_catalog=in_public_catalog)
        )
    if "being" in kinds:
        session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
    if "fact" in kinds:
        session.add(Fact(entity_id=entity.id, tenant_id=tenant_id))
        session.add(EntityAudience(entity_id=entity.id, tenant_id=tenant_id, is_public=False))
    if "event" in kinds:
        session.add(StoryEvent(entity_id=entity.id, tenant_id=tenant_id))
        session.add(EntityAudience(entity_id=entity.id, tenant_id=tenant_id, is_public=False))
    if "location" in kinds:
        session.add(Location(entity_id=entity.id, tenant_id=tenant_id))
        if set(kinds) == {"location"}:
            # A new Location is restricted until its audience is opened (ADR 0330). A Location
            # beside another kind leaves that kind's own audience rules alone.
            session.add(EntityAudience(entity_id=entity.id, tenant_id=tenant_id, is_public=False))
    if stored_system is not None:
        session.add(Map(entity_id=entity.id, tenant_id=tenant_id, system=stored_system))
        if set(kinds) == {"map"}:
            # A new Map is restricted until its audience is opened, like a Location.
            session.add(EntityAudience(entity_id=entity.id, tenant_id=tenant_id, is_public=False))
    for position, parent_id in enumerate(dict.fromkeys(parents)):
        session.add(
            EntityPrototype(
                entity_id=entity.id, prototype_id=parent_id, tenant_id=tenant_id, position=position
            )
        )
    await session.flush()
    return entity


async def add_kind(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity: Entity,
    kind: Kind,
    user_id: uuid.UUID,
    in_public_catalog: bool | None = None,
    system: dict[str, Any] | None = None,
) -> Literal["created", "changed", "unchanged"]:
    """Gives the entry the kind, and says what happened: `created` the marker row, `changed` an
    `item`'s `in_public_catalog` set to another value, or `unchanged`. Touches the entry
    (`updated_by`, and `updated_at`, so its ETag moves) only then. An inventory item never takes
    `item`; it may take `being`."""
    entity_id = entity.id
    existing_kinds = await kinds_of_entry(session, entity_id)
    if kind not in ("location", "map") and existing_kinds & {
        "scene",
        "scene_appearance",
        "session",
        "clock",
    }:
        raise InvalidKindRequestError(
            detail="Session and Scene kinds do not combine with other kinds"
        )
    if kind not in ("location", "map") and (
        "calendar_period" in existing_kinds
        or "observance" in existing_kinds
        or "event" in existing_kinds
        or kind == "event"
    ):
        raise InvalidKindRequestError(
            detail="Use the Event creation route; "
            "temporal entries do not combine kinds in this slice."
        )
    if kind not in ("location", "map") and "calendar" in existing_kinds:
        raise InvalidKindRequestError(
            detail="A calendar does not combine with physical kinds in this slice."
        )
    if (kind == "fact" and existing_kinds - {"fact", "location", "map"}) or (
        kind not in ("fact", "location", "map") and "fact" in existing_kinds
    ):
        raise InvalidKindRequestError(
            detail="A fact is an information anchor; other kinds are a later slice."
        )
    result: Literal["created", "changed", "unchanged"] = "unchanged"
    if kind == "item":
        if await session.get(ItemInstance, entity_id) is not None:
            raise InventoryItemKindError(
                detail=f"Entry {entity_id} is an inventory item, which is made from a catalog "
                "item and is never one itself"
            )
        item = await session.get(Item, entity_id)
        if item is None:
            session.add(
                Item(
                    entity_id=entity_id,
                    tenant_id=tenant_id,
                    in_public_catalog=bool(in_public_catalog),
                )
            )
            result = "created"
        elif in_public_catalog is not None and item.in_public_catalog != in_public_catalog:
            item.in_public_catalog = in_public_catalog
            result = "changed"
    elif kind == "fact":
        if await session.get(Fact, entity_id) is None:
            session.add(Fact(entity_id=entity_id, tenant_id=tenant_id))
            if await session.get(EntityAudience, entity_id) is None:
                session.add(
                    EntityAudience(entity_id=entity_id, tenant_id=tenant_id, is_public=False)
                )
            result = "created"
    elif kind == "location":
        if await session.get(Location, entity_id) is None:
            session.add(Location(entity_id=entity_id, tenant_id=tenant_id))
            result = "created"
    elif kind == "map":
        if await session.get(Map, entity_id) is None:
            if system is None:
                raise InvalidKindRequestError(detail="A Map needs its system.")
            try:
                stored = validate_system(system)
            except MapDocumentError as error:
                raise InvalidKindRequestError(detail=error.reason) from None
            await require_map_room(session, tenant_id=tenant_id)
            session.add(Map(entity_id=entity_id, tenant_id=tenant_id, system=stored))
            result = "created"
    elif await session.get(Being, entity_id) is None:
        session.add(Being(entity_id=entity_id, tenant_id=tenant_id))
        result = "created"
    if result != "unchanged":
        session.info.pop("visible_entry_checks", None)
        _touch(entity, user_id)
        await session.flush()
    return result


async def require_no_participations(
    session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    await session.execute(
        select(Entity.id)
        .where(Entity.tenant_id == tenant_id, Entity.id == entity_id)
        .with_for_update()
    )
    if await session.scalar(
        select(
            exists().where(
                EventParticipant.tenant_id == tenant_id,
                (EventParticipant.event_entity_id == entity_id)
                | (EventParticipant.being_entity_id == entity_id),
            )
        )
    ):
        raise EntityKindInUseError(
            detail="This entry has references that prevent deletion or kind removal."
        )


async def remove_kind(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity: Entity,
    kind: Kind,
    user_id: uuid.UUID,
) -> bool:
    """Takes the kind away, and says whether the entry had it. `item` is refused while an
    inventory item inherits from the entry directly, which is the guard `DELETE /items/{id}` has
    (ADR 0032), and `being` while the entry is a character, whose key would cascade away with it:
    demote it first (ADR 0036)."""
    entity_id = entity.id
    from lorenzo_api.story_context import require_no_context_references

    if kind in ("being", "fact", "event"):
        await require_no_context_references(session, tenant_id, entity_id)
    if kind == "being":
        await require_no_participations(session, tenant_id, entity_id)
    if kind == "event":
        raise EntityKindInUseError(detail="Delete the Event entry instead of removing its kind.")
    if kind == "item":
        if await inventory_items_inherit(session, tenant_id=tenant_id, entity_id=entity_id):
            raise ItemPrototypeInUseError(
                detail=f"Entry {entity_id} is still a direct prototype of at least one "
                "inventory item"
            )
        marker: type[Item | Being | Fact | Location | Map] = Item
    elif kind == "location":
        marker = Location
    elif kind == "map":
        marker = Map
    else:
        if await session.get(Character, entity_id) is not None:
            raise EntityKindInUseError(
                detail=f"Entry {entity_id} is a character: demote it with "
                f"DELETE /tenants/{tenant_id}/characters/{entity_id} before it stops being a being"
            )
        marker = Being
    if kind in ("location", "map"):
        audience = await session.get(EntityAudience, entity_id)
        if audience is not None:
            if not audience.is_public:
                raise InvalidKindRequestError(
                    detail=f"Make the entry audience public before removing its {kind} kind."
                )
            if not (await kinds_of_entry(session, entity_id)) & _AUDIENCE_KINDS:
                await session.delete(audience)
    if kind == "fact":
        marker = Fact
        audience = await session.get(EntityAudience, entity_id)
        if audience is not None:
            if not audience.is_public:
                raise InvalidKindRequestError(
                    detail="Make the entry audience public before removing its fact kind."
                )
            await session.delete(audience)
    removed = await session.scalar(
        delete(marker)
        .where(marker.entity_id == entity_id, marker.tenant_id == tenant_id)
        .returning(marker.entity_id)
    )
    if removed is not None:
        session.info.pop("visible_entry_checks", None)
        _touch(entity, user_id)
        await session.flush()
    return removed is not None


async def inventory_items_inherit(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> bool:
    """Whether an inventory item has this entry as a direct prototype."""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    EntityPrototype.prototype_id == entity_id,
                    EntityPrototype.tenant_id == tenant_id,
                    EntityPrototype.entity_id == ItemInstance.entity_id,
                )
            )
        )
    )


async def kinds_of_entry(session: AsyncSession, entity_id: uuid.UUID) -> set[str]:
    """The entry's kinds."""
    return {
        kind
        for kind, model in (
            ("item", Item),
            ("scene", Scene),
            ("scene_appearance", SceneAppearance),
            ("session", StorySession),
            ("fact", Fact),
            ("calendar", Calendar),
            ("clock", Clock),
            ("location", Location),
            ("map", Map),
            ("calendar_period", CalendarPeriod),
            ("observance", CalendarObservance),
            ("event", StoryEvent),
            ("item_instance", ItemInstance),
            ("being", Being),
            ("character", Character),
        )
        if await session.get(model, entity_id) is not None
    }


async def require_deletable(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    allow_character: bool = False,
) -> set[str]:
    """The guards of every kind the entry has, composed (RFC 0041 section 2), and the kinds it
    has, so a delete can say what went with it. An inventory item is deleted through its own
    route (it moves what it holds back out, ADR 0128), a character is demoted before its entry
    goes, a catalog item is not deleted while an inventory item inherits from it, and a
    campaign's own entry stays with the campaign. A being that is no character, an item and a
    bare entry go. The permanent being-deletion route explicitly allows a character here."""
    kinds = await kinds_of_entry(session, entity_id)
    from lorenzo_api.story_context import require_no_context_references

    await require_no_context_references(session, tenant_id, entity_id)
    if kinds & {"session", "scene_appearance"}:
        raise EntityKindInUseError(
            detail="Remove this Session or Scene appearance through its preparation page"
        )
    if (
        "scene" in kinds
        and await session.scalar(
            select(SceneAppearance.entity_id)
            .where(SceneAppearance.scene_entity_id == entity_id)
            .limit(1)
        )
        is not None
    ):
        raise EntityKindInUseError(detail="This Scene is used in a Session")
    if "event" in kinds:
        from lorenzo_api.event_order_lock import lock_event_order
        from lorenzo_api.models import EventRelationship

        await lock_event_order(session, tenant_id)
        if await session.scalar(
            select(
                exists().where(
                    EventRelationship.tenant_id == tenant_id,
                    (EventRelationship.from_event_id == entity_id)
                    | (EventRelationship.to_event_id == entity_id),
                )
            )
        ):
            raise EntityKindInUseError(detail="This entry has references that prevent deletion.")
    if "event" in kinds or "being" in kinds:
        await require_no_participations(session, tenant_id, entity_id)
    if "calendar" in kinds or "calendar_period" in kinds or "observance" in kinds:
        await session.execute(
            select(Entity.id)
            .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
            .with_for_update()
        )
    if "calendar" in kinds and (
        await session.scalar(select(exists().where(CalendarPeriod.calendar_entity_id == entity_id)))
        or await session.scalar(
            select(exists().where(CalendarObservance.calendar_entity_id == entity_id))
        )
    ):
        raise EntityKindInUseError(
            detail="This calendar has recorded periods. Resolve them before deleting it."
        )
    if "calendar_period" in kinds and (
        await session.scalar(select(exists().where(CalendarPeriod.parent_entity_id == entity_id)))
        or await session.scalar(
            select(exists().where(EntryCalendarPeriod.period_entity_id == entity_id))
        )
        or await session.scalar(select(exists().where(Scene.period_entity_id == entity_id)))
        or await session.scalar(select(exists().where(StorySession.start_period_id == entity_id)))
    ):
        raise EntityKindInUseError(
            detail="This period has references. Resolve them before deleting it."
        )
    if "item_instance" in kinds:
        raise InventoryItemKindError(
            detail=f"Entry {entity_id} is an inventory item: delete it with "
            f"DELETE /tenants/{tenant_id}/item-instances/{entity_id}"
        )
    if "character" in kinds and not allow_character:
        raise EntityKindInUseError(
            detail=f"Entry {entity_id} is a character: demote it with "
            f"DELETE /tenants/{tenant_id}/characters/{entity_id} before deleting the entry"
        )
    if await session.scalar(select(func.count()).where(Campaign.entity_id == entity_id)):
        raise EntityKindInUseError(
            detail=f"Entry {entity_id} belongs to a campaign, which is deleted with its campaign"
        )
    if "item" in kinds and await inventory_items_inherit(
        session, tenant_id=tenant_id, entity_id=entity_id
    ):
        raise ItemPrototypeInUseError(
            detail=f"Entry {entity_id} is still a direct prototype of at least one inventory item"
        )
    from lorenzo_api.models import CalendarReckoning, ClockRelationship, EventClockReading

    if await session.scalar(
        select(EventClockReading.clock_entity_id)
        .where(
            (EventClockReading.clock_entity_id == entity_id)
            | (EventClockReading.event_entity_id == entity_id)
        )
        .limit(1)
    ) or await session.scalar(
        select(CalendarReckoning.clock_entity_id)
        .where(
            (CalendarReckoning.clock_entity_id == entity_id)
            | (CalendarReckoning.calendar_entity_id == entity_id)
        )
        .limit(1)
    ):
        raise EntityKindInUseError(
            detail="Resolve dependent clock records before deleting this entry"
        )
    if await session.scalar(
        select(ClockRelationship.clock_entity_id)
        .where(
            (ClockRelationship.clock_entity_id == entity_id)
            | (ClockRelationship.reference_clock_entity_id == entity_id)
        )
        .limit(1)
    ):
        raise EntityKindInUseError(
            detail="Resolve dependent clock records before deleting this entry"
        )
    await require_no_learning(session, tenant_id, entity_id=entity_id)
    return kinds


KIND_WORDS = {
    "scene": "scene",
    "session": "session",
    "scene_appearance": "scene appearance",
    "fact": "fact",
    "calendar": "calendar",
    "clock": "clock",
    "location": "location",
    "map": "map",
    "calendar_period": "calendar period",
    "event": "event",
    "observance": "observance",
    "item": "item",
    "item_instance": "inventory item",
    "being": "being",
    "character": "character",
}


def unpublishable_entries(
    rows: Iterable[tuple[uuid.UUID, str, Sequence[str]]],
) -> list[dict[str, Any]]:
    """The entries (id, name, kinds) whose combination of kinds is not in
    PUBLISHABLE_KIND_COMBINATIONS, ordered by name."""
    return [
        {"id": entity_id, "name": name, "kinds": list(kinds)}
        for entity_id, name, kinds in sorted(rows, key=lambda r: (r[1], str(r[0])))
        if tuple(kinds) not in PUBLISHABLE_KIND_COMBINATIONS
    ]


def unpublishable_sentence(entries: Sequence[dict[str, Any]]) -> str:
    """The refusal in words (ADR 0194): who they are, the first ten by name."""
    shown = [
        f"“{e['name']}” ({' and '.join(KIND_WORDS[k] for k in e['kinds'])})" for e in entries[:10]
    ]
    more = f", and {len(entries) - 10} more" if len(entries) > 10 else ""
    return (
        f"{len(entries)} of the entries here have a combination of kinds that copying and "
        f"updating have not been proven to carry yet: {', '.join(shown)}{more}. "
        "Take a kind away from each, or keep this repository a draft."
    )


def _touch(entity: Entity, user_id: uuid.UUID) -> None:
    entity.updated_by = user_id
    # Also when updated_by is already this user, so the ETag moves whoever writes.
    entity.updated_at = func.now()
