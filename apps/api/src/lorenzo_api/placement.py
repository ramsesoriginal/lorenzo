"""Placement: where an entry is (ADR 0333) and where it is for one character (ADR 0334).

A place belongs to the top of an entry's containment chain, and nothing inherits it: not down
the part-of tree, not along containment, not through prototypes. Nothing here is read by GM reach
(ADR 0046); a test scans for it.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import delete, event, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy.orm.unitofwork import UOWTransaction

from lorenzo_api.entity_access import surroundings
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.locations import visible_ancestor_ids
from lorenzo_api.models import Containment, Entity, EntityLocation, EntitySlug, Location

_MAX_CHAIN = 50


def _top_and_place(session: Session, entity_id: uuid.UUID) -> uuid.UUID | None:
    """The place of the top of an entry's containment chain, as the flush hook reads it: the
    top's own `entity_location`, or the top itself when it is a Location with none. Synchronous
    and cycle-safe: it runs inside a flush."""
    top = entity_id
    seen = {entity_id}
    for _ in range(_MAX_CHAIN):
        parent = session.execute(
            text("SELECT parent_entity_id FROM containment WHERE child_entity_id = :id"),
            {"id": top},
        ).scalar()
        if parent is None or parent in seen:
            break
        seen.add(parent)
        top = parent
    placed = session.execute(
        text("SELECT location_entity_id FROM entity_location WHERE entity_id = :id"), {"id": top}
    ).scalar()
    if placed is not None:
        return uuid.UUID(str(placed))
    if session.execute(text("SELECT 1 FROM location WHERE entity_id = :id"), {"id": top}).scalar():
        return top
    return None


def _before_flush(session: Session, flush_context: UOWTransaction, instances: Any) -> None:
    """The row follows the container (ADR 0333): put into one, an entry has no place of its own;
    taken out of one, it is where that container was."""
    put_in = {obj.child_entity_id for obj in session.new if isinstance(obj, Containment)}
    taken_out = [
        (obj.child_entity_id, obj.parent_entity_id, obj.tenant_id)
        for obj in session.deleted
        if isinstance(obj, Containment)
    ]
    if not put_in and not taken_out:
        return
    going = {obj.id for obj in session.deleted if isinstance(obj, Entity)}
    for child in put_in:
        session.execute(delete(EntityLocation).where(EntityLocation.entity_id == child))
    for child, parent, tenant in taken_out:
        if child in put_in or child in going:
            continue
        place = _top_and_place(session, parent)
        if place is None or place == child:
            continue
        session.execute(
            pg_insert(EntityLocation)
            .values(entity_id=child, location_entity_id=place, tenant_id=tenant)
            .on_conflict_do_update(
                index_elements=[EntityLocation.entity_id],
                set_={"location_entity_id": place},
            )
        )


def install() -> None:
    """Makes the flush hook live for every ORM session, once however often it is called."""
    if not event.contains(Session, "before_flush", _before_flush):
        event.listen(Session, "before_flush", _before_flush)


State = Literal["with_you", "stashed", "elsewhere", "unknown"]


@dataclass(frozen=True)
class Place:
    id: uuid.UUID
    name: str
    slug: str | None


@dataclass(frozen=True)
class Whereabouts:
    state: State
    place: Place | None = None


async def whereabouts_of(
    session: AsyncSession,
    vis: InformationVisibility,
    *,
    tenant_id: uuid.UUID,
    entity_ids: Sequence[uuid.UUID],
    character_id: uuid.UUID,
) -> dict[uuid.UUID, Whereabouts]:
    """Where each entry is, as `character_id` would say it (ADR 0334): from rows the reader can
    see, so a hidden place is `unknown` and a hidden level between two places is not there."""
    wanted = frozenset(entity_ids) | {character_id}
    chains = await surroundings(session, entity_ids=wanted, tenant_id=tenant_id)
    top = {entity: (chain[-1] if chain else entity) for entity, chain in chains.items()}
    tops = set(top.values())
    placed = dict(
        (
            await session.execute(
                select(EntityLocation.entity_id, EntityLocation.location_entity_id).where(
                    EntityLocation.entity_id.in_(tops), EntityLocation.tenant_id == tenant_id
                )
            )
        )
        .tuples()
        .all()
    )
    markers = set(
        (
            await session.scalars(
                select(Location.entity_id).where(
                    Location.entity_id.in_(tops), Location.tenant_id == tenant_id
                )
            )
        ).all()
    )

    def place_of(entity: uuid.UUID) -> uuid.UUID | None:
        at = top[entity]
        return placed.get(at) or (at if at in markers else None)

    candidates = {p for p in (place_of(e) for e in wanted) if p is not None}
    seen: set[uuid.UUID] = set()
    if candidates:
        seen = set(
            (
                await session.scalars(
                    select(Entity.id).where(
                        Entity.id.in_(candidates),
                        Entity.tenant_id == tenant_id,
                        visible_entry_clause(vis, Entity.id),
                    )
                )
            ).all()
        )
    names: dict[uuid.UUID, Place] = {}
    if seen:
        for identity, name, slug in (
            await session.execute(
                select(Entity.id, Entity.name, EntitySlug.slug)
                .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
                .where(Entity.id.in_(seen))
            )
        ).tuples():
            names[identity] = Place(identity, name, slug)
    above: dict[uuid.UUID, set[uuid.UUID]] = {}

    async def ancestors(location: uuid.UUID) -> set[uuid.UUID]:
        if location not in above:
            above[location] = set(
                await visible_ancestor_ids(session, vis, tenant_id=tenant_id, location_id=location)
            )
        return above[location]

    mine = place_of(character_id)
    mine = mine if mine in seen else None
    out: dict[uuid.UUID, Whereabouts] = {}
    for entity in entity_ids:
        if entity == character_id or character_id in chains.get(entity, []):
            out[entity] = Whereabouts("with_you")
            continue
        there = place_of(entity)
        if there is None or there not in seen:
            out[entity] = Whereabouts("unknown")
        elif mine is None:
            out[entity] = Whereabouts("stashed", names[there])
        elif there == mine:
            out[entity] = Whereabouts("stashed")
        elif mine in await ancestors(there) or there in await ancestors(mine):
            out[entity] = Whereabouts("stashed", names[there])
        else:
            out[entity] = Whereabouts("elsewhere", names[there])
    return out
