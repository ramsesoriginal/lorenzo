"""What is probably a mistake in a library's places (ADR 0335). Read-only: it stores nothing,
changes nothing and offers no repair."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from lorenzo_api.models import (
    Containment,
    Entity,
    EntityAudience,
    EntityLocation,
    LocationPart,
)

# A library with more than this many findings of one kind shows the first of them.
_PER_KIND = 500
_LOOP_ROWS = 100_000


@dataclass(frozen=True)
class Finding:
    finding: str
    message: str
    entries: list[tuple[uuid.UUID, str]]


async def lint_locations(session: AsyncSession, *, tenant_id: uuid.UUID) -> list[Finding]:
    found: list[Finding] = []
    holder = aliased(Entity)
    place = aliased(Entity)
    parent = aliased(Entity)
    child = aliased(Entity)
    place_audience = aliased(EntityAudience)
    parent_audience = aliased(EntityAudience)
    own_audience = aliased(EntityAudience)

    # A place on something that is in a container: the container places it, so the row is ignored.
    for entry_id, entry, holder_id, container in (
        await session.execute(
            select(EntityLocation.entity_id, Entity.name, holder.id, holder.name)
            .join(Entity, Entity.id == EntityLocation.entity_id)
            .join(Containment, Containment.child_entity_id == EntityLocation.entity_id)
            .join(holder, holder.id == Containment.parent_entity_id)
            .where(EntityLocation.tenant_id == tenant_id)
            .order_by(Entity.name, Entity.id)
            .limit(_PER_KIND)
        )
    ).tuples():
        found.append(
            Finding(
                "dormant_place",
                f"{entry} has a place, but it is in {container}, which places it. "
                "The place is ignored.",
                [(entry_id, entry), (holder_id, container)],
            )
        )

    # Everyone can see the entry; the players cannot see where it is, so they read "unknown".
    for entry_id, entry, place_id, name in (
        await session.execute(
            select(EntityLocation.entity_id, Entity.name, place.id, place.name)
            .join(Entity, Entity.id == EntityLocation.entity_id)
            .join(place, place.id == EntityLocation.location_entity_id)
            .join(place_audience, place_audience.entity_id == place.id)
            .outerjoin(own_audience, own_audience.entity_id == EntityLocation.entity_id)
            .where(
                EntityLocation.tenant_id == tenant_id,
                place_audience.is_public.is_(False),
                (own_audience.entity_id.is_(None)) | own_audience.is_public.is_(True),
            )
            .order_by(Entity.name, Entity.id)
            .limit(_PER_KIND)
        )
    ).tuples():
        found.append(
            Finding(
                "place_hidden",
                f"{entry} can be seen by everyone, but is at {name}, which the players cannot "
                "see. They read it as unknown.",
                [(entry_id, entry), (place_id, name)],
            )
        )

    # Everyone can see the Location; it is part of one the players cannot see.
    for child_id, child_name, parent_id, parent_name in (
        await session.execute(
            select(LocationPart.child_entity_id, child.name, parent.id, parent.name)
            .join(child, child.id == LocationPart.child_entity_id)
            .join(parent, parent.id == LocationPart.parent_entity_id)
            .join(parent_audience, parent_audience.entity_id == parent.id)
            .outerjoin(own_audience, own_audience.entity_id == LocationPart.child_entity_id)
            .where(
                LocationPart.tenant_id == tenant_id,
                parent_audience.is_public.is_(False),
                (own_audience.entity_id.is_(None)) | own_audience.is_public.is_(True),
            )
            .order_by(child.name, child.id)
            .limit(_PER_KIND)
        )
    ).tuples():
        found.append(
            Finding(
                "part_hidden",
                f"{child_name} can be seen by everyone, but is part of {parent_name}, which the "
                "players cannot see. They see it under a higher Location, or as a top-level one.",
                [(child_id, child_name), (parent_id, parent_name)],
            )
        )

    # Locations that are part of one another: only a copy can make that, never a write.
    parents = dict(
        (
            await session.execute(
                select(LocationPart.child_entity_id, LocationPart.parent_entity_id)
                .where(LocationPart.tenant_id == tenant_id)
                .limit(_LOOP_ROWS)
            )
        )
        .tuples()
        .all()
    )
    on_a_loop: list[list[uuid.UUID]] = []
    settled: set[uuid.UUID] = set()
    for start in parents:
        if start in settled:
            continue
        walk: list[uuid.UUID] = []
        at: uuid.UUID | None = start
        while at is not None and at not in settled and at not in walk:
            walk.append(at)
            at = parents.get(at)
        if at is not None and at in walk:
            on_a_loop.append(walk[walk.index(at) :])
        settled.update(walk)
    if on_a_loop:
        names = dict(
            (
                await session.execute(
                    select(Entity.id, Entity.name).where(
                        Entity.id.in_({node for loop in on_a_loop for node in loop})
                    )
                )
            )
            .tuples()
            .all()
        )
        for loop in on_a_loop[:_PER_KIND]:
            pairs = sorted(((node, names[node]) for node in loop), key=lambda p: (p[1], str(p[0])))
            found.append(
                Finding(
                    "part_loop",
                    f"{', '.join(name for _, name in pairs)} are part of one another.",
                    pairs,
                )
            )
    order = {"dormant_place": 0, "place_hidden": 1, "part_hidden": 2, "part_loop": 3}
    found.sort(key=lambda f: (order[f.finding], f.entries[0][1], str(f.entries[0][0])))
    return found
