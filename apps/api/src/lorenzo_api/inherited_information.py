"""What an item shows from its prototypes - see ADR 0111.

An item's descriptions and pictures are its own, then its ancestors':
every entity it reaches through entity_prototype, nearest first. This
module finds those ancestors for a whole page of items at once, one query
per level of the prototype graph, and loads their description information
so schemas/items.py can render it with the same visibility check as the
item's own.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from sqlalchemy import select
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
    """
    roots = set(entity_ids)
    parents: dict[uuid.UUID, list[uuid.UUID]] = {}
    frontier = set(roots)
    # The prototype graph is acyclic (ADR 0015's trigger), so each level only
    # asks about entities not asked about yet.
    for _ in range(MAX_PROTOTYPE_HOPS):
        frontier -= parents.keys()
        if not frontier:
            break
        edges = await session.execute(
            select(EntityPrototype.entity_id, EntityPrototype.prototype_id).where(
                EntityPrototype.tenant_id == tenant_id, EntityPrototype.entity_id.in_(frontier)
            )
        )
        for child in frontier:
            parents[child] = []
        for child, parent in edges:
            parents[child].append(parent)
        frontier = {parent for child in frontier for parent in parents[child]}

    distances = {root: _distances(root, parents) for root in roots}
    ancestor_ids = {ancestor for found in distances.values() for ancestor in found}
    entities: dict[uuid.UUID, Entity] = {}
    if ancestor_ids:
        loaded = await session.scalars(
            select(Entity)
            .where(Entity.tenant_id == tenant_id, Entity.id.in_(ancestor_ids))
            .options(
                selectinload(Entity.information)
                .selectinload(Information.payloads)
                .selectinload(Payload.description),
                selectinload(Entity.information)
                .selectinload(Information.payloads)
                .selectinload(Payload.picture),
                selectinload(Entity.information).selectinload(Information.knowledge_links),
            )
        )
        entities = {entity.id: entity for entity in loaded}
    return {
        root: sorted(
            (entities[ancestor] for ancestor in found if ancestor in entities),
            key=lambda entity: (found[entity.id], entity.name, str(entity.id)),
        )
        for root, found in distances.items()
    }


def _distances(root: uuid.UUID, parents: dict[uuid.UUID, list[uuid.UUID]]) -> dict[uuid.UUID, int]:
    """Breadth-first from `root`: each ancestor's fewest hops, up to the limit."""
    found: dict[uuid.UUID, int] = {}
    level = [root]
    for hops in range(1, MAX_PROTOTYPE_HOPS + 1):
        # dict.fromkeys: an ancestor reached twice at one level is walked once.
        level = list(
            dict.fromkeys(p for child in level for p in parents.get(child, []) if p not in found)
        )
        if not level:
            break
        for ancestor in level:
            found[ancestor] = hops
    return found


async def ancestors_of(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> list[Entity]:
    """prototype_ancestors for one entity."""
    found = await prototype_ancestors(session, tenant_id=tenant_id, entity_ids=[entity_id])
    return found[entity_id]
