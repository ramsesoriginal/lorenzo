"""Loading what contents formulas read - see ADR 0127.

A contents formula adds up a stat over what's directly inside an entity, so
evaluating one needs the stats of everything below it. stat_evaluation stays
pure; this loads its input: the containment subtree of each entity being
read whose stats include a winning contents formula, what's directly inside
each entity in it (with stack counts), and every one's effective stats.

Nothing is loaded when no contents formula wins, so a read that doesn't use
one costs nothing more. Everything physically inside counts, whatever the
reader may see (ADR 0127): the queries are scoped by tenant only.
"""

import uuid
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.entity_access import recursive_descendants_cte
from lorenzo_api.models import Containment, Entity, VEffectiveStat, formula_load_options
from lorenzo_api.stat_evaluation import Contents


def _has_contents_formula(entity: Entity) -> bool:
    """Requires effective_stats and their formulas loaded."""
    return any(
        stat.computed_entity_id is not None
        and stat.computed_stat is not None
        and stat.computed_stat.contents is not None
        for stat in entity.effective_stats
    )


async def load_contents(
    session: AsyncSession, *, tenant_id: uuid.UUID, root_ids: Iterable[uuid.UUID]
) -> Contents:
    """What's inside `root_ids`, to the containment walk's depth cap (ADR
    0016), and the effective stats of all of it. What's directly inside
    comes from every containment row under the loaded entities, so a row
    leading back into the subtree - a cycle - is seen, not cut short."""
    roots = frozenset(root_ids)
    descendants = recursive_descendants_cte(roots, tenant_id)
    loaded = roots | set(await session.scalars(select(descendants.c.child_entity_id)))

    children: dict[uuid.UUID, list[tuple[uuid.UUID, int]]] = defaultdict(list)
    for parent, child, quantity in await session.execute(
        select(Containment.parent_entity_id, Containment.child_entity_id, Containment.quantity)
        .where(Containment.parent_entity_id.in_(loaded), Containment.tenant_id == tenant_id)
        .order_by(Containment.child_entity_id)
    ):
        children[parent].append((child, quantity))

    stats: dict[uuid.UUID, list[VEffectiveStat]] = defaultdict(list)
    for stat in await session.scalars(
        select(VEffectiveStat)
        .where(VEffectiveStat.entity_id.in_(loaded - roots), VEffectiveStat.tenant_id == tenant_id)
        .options(
            selectinload(VEffectiveStat.stat_definition),
            *formula_load_options(selectinload(VEffectiveStat.computed_stat)),
        )
    ):
        stats[stat.entity_id].append(stat)
    return Contents(stats=stats, children=children)


async def attach_contents(
    session: AsyncSession, entities: Iterable[Entity], *, tenant_id: uuid.UUID
) -> None:
    """Attaches, to each of `entities` whose stats include a winning
    contents formula, what that formula reads - one load for all of them.
    Call before serializing their stats. Requires each entity's
    effective_stats and their formulas loaded."""
    needing = [entity for entity in entities if _has_contents_formula(entity)]
    if not needing:
        return
    contents = await load_contents(
        session, tenant_id=tenant_id, root_ids=[entity.id for entity in needing]
    )
    # A root inside another root's subtree is read with its own rows, which
    # evaluation already has; the others are what's below.
    root_stats = {entity.id: list(entity.effective_stats) for entity in needing}
    merged = Contents(stats={**root_stats, **contents.stats}, children=contents.children)
    for entity in needing:
        entity.stat_contents = merged
