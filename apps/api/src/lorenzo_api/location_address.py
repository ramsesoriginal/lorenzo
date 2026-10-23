"""The GM's address of an entry (ADR 0335): what holds it, where it is, and what that is within.

Read with the caller's own visibility, by the same walks the player's reads use. It adds nothing to
any other read and no reach code names it.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.entity_access import containment_paths, surroundings
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.locations import visible_ancestor_ids
from lorenzo_api.models import Entity, EntityLocation, EntitySlug, Location

Via = Literal["contained_in", "with", "at", "part_of"]


@dataclass(frozen=True)
class Step:
    via: Via
    entity_id: uuid.UUID
    name: str
    slug: str | None


@dataclass(frozen=True)
class Address:
    segments: list[Step]
    interior: list[Step] | None


async def address_of(
    session: AsyncSession,
    vis: InformationVisibility,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
) -> Address:
    held = frozenset({entity_id})
    containers = (await containment_paths(session, entity_ids=held, tenant_id=tenant_id))[entity_id]
    around = (await surroundings(session, entity_ids=held, tenant_id=tenant_id))[entity_id]
    top = around[-1] if around else entity_id
    hops: list[tuple[Via, uuid.UUID]] = []
    for position, node in enumerate(around):
        # What follows the containers is the owner of a thing in no container, then its containers.
        hops.append(("with" if position == len(containers) else "contained_in", node))
    placed = await session.scalar(
        select(EntityLocation.location_entity_id).where(
            EntityLocation.entity_id == top, EntityLocation.tenant_id == tenant_id
        )
    )
    is_location = (
        await session.scalar(
            select(Location.entity_id).where(
                Location.entity_id == entity_id, Location.tenant_id == tenant_id
            )
        )
        is not None
    )
    place: uuid.UUID | None = placed
    if place is None and top != entity_id:
        top_is_location = await session.scalar(
            select(Location.entity_id).where(
                Location.entity_id == top, Location.tenant_id == tenant_id
            )
        )
        place = top if top_is_location is not None else None
    if placed is not None:
        hops.append(("at", placed))
    if place is not None:
        hops.extend(
            ("part_of", ancestor)
            for ancestor in await visible_ancestor_ids(
                session, vis, tenant_id=tenant_id, location_id=place
            )
        )
    interior: list[tuple[Via, uuid.UUID]] | None = None
    if is_location:
        interior = [
            ("part_of", ancestor)
            for ancestor in await visible_ancestor_ids(
                session, vis, tenant_id=tenant_id, location_id=entity_id
            )
        ]
    wanted = {node for _, node in hops} | {node for _, node in interior or []}
    named: dict[uuid.UUID, tuple[str, str | None]] = {}
    if wanted:
        for identity, name, slug in (
            await session.execute(
                select(Entity.id, Entity.name, EntitySlug.slug)
                .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
                .where(
                    Entity.id.in_(wanted),
                    Entity.tenant_id == tenant_id,
                    visible_entry_clause(vis, Entity.id),
                )
            )
        ).tuples():
            named[identity] = (name, slug)

    def steps(found: list[tuple[Via, uuid.UUID]]) -> list[Step]:
        return [
            Step(via, node, named[node][0], named[node][1]) for via, node in found if node in named
        ]

    return Address(steps(hops), None if interior is None else steps(interior))
