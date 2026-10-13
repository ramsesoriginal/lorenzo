"""What an item shows from its prototypes - see ADR 0111.

An item's descriptions and pictures are its own, then its ancestors':
every entity it reaches through entity_prototype, nearest first. This
module finds those ancestors for a whole page of items at once, in one
recursive query whatever the depth of the prototype graph (ADR 0285), and
loads their description information so schemas/items.py can render it with
the same visibility check as the item's own.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import and_, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.models import Entity, EntityPrototype, Information, Payload

# v_effective_stat's limit (ADR 0104's migration), so stats and descriptions
# reach the same ancestors.
MAX_PROTOTYPE_HOPS = 50


async def prototype_ancestors(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, list[Entity]]:
    """Each entity's ancestors, nearest first: each once, at its shortest
    distance, equally near ones by name then id. Their information,
    payloads (description and picture), and knowledge links are loaded.
    Every requested id has an entry, empty when it has no prototypes.

    The walk is one recursive query (ADR 0285): a plain UNION, so a row is
    kept once per (entity, ancestor, distance) and an ancestor reached by
    several paths is walked on from once at each distance, not once per
    path; the entities come with it, joined to their shortest distance.
    The prototype graph is acyclic (ADR 0015's trigger), and the walk stops
    at MAX_PROTOTYPE_HOPS regardless.
    """
    roots = set(entity_ids)
    result: dict[uuid.UUID, list[Entity]] = {root: [] for root in roots}
    if not roots:
        return result

    walk = (
        select(
            EntityPrototype.entity_id.label("root_id"),
            EntityPrototype.prototype_id.label("ancestor_id"),
            literal(1).label("hops"),
        )
        .where(EntityPrototype.tenant_id == tenant_id, EntityPrototype.entity_id.in_(roots))
        .cte("prototype_walk", recursive=True)
    )
    walk = walk.union(
        select(walk.c.root_id, EntityPrototype.prototype_id, walk.c.hops + 1)
        .select_from(
            walk.join(
                EntityPrototype,
                and_(
                    EntityPrototype.entity_id == walk.c.ancestor_id,
                    EntityPrototype.tenant_id == tenant_id,
                ),
            )
        )
        .where(walk.c.hops < MAX_PROTOTYPE_HOPS)
    )
    nearest = (
        select(walk.c.root_id, walk.c.ancestor_id, func.min(walk.c.hops).label("hops"))
        .group_by(walk.c.root_id, walk.c.ancestor_id)
        .subquery("nearest_ancestor")
    )
    rows = await session.execute(
        select(nearest.c.root_id, nearest.c.hops, Entity)
        .join(Entity, Entity.id == nearest.c.ancestor_id)
        .where(Entity.tenant_id == tenant_id)
        .options(
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .joinedload(Payload.description),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .joinedload(Payload.picture),
            selectinload(Entity.information).selectinload(Information.knowledge_links),
        )
    )
    found: dict[uuid.UUID, list[tuple[int, Entity]]] = {root: [] for root in roots}
    for root_id, hops, ancestor in rows:
        found[root_id].append((hops, ancestor))
    for root, ancestors in found.items():
        ancestors.sort(key=lambda found_at: (found_at[0], found_at[1].name, str(found_at[1].id)))
        result[root] = [ancestor for _, ancestor in ancestors]
    return result


async def ancestors_of(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> list[Entity]:
    """prototype_ancestors for one entity."""
    found = await prototype_ancestors(session, tenant_id=tenant_id, entity_ids=[entity_id])
    return found[entity_id]
