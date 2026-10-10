"""`my/` links (ADR 0240): `[[my/Longsword]]` is the longsword that belongs to
whoever the text belongs to. Nothing here is stored: a reference keeps its
hint `my` and its slug (ADR 0110), and this module says what they mean when
they are read, for resolving and for backlinks alike, so the two agree.
"""

import uuid
from collections.abc import Iterable

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.entity_access import (
    prototype_descendants_cte,
    reachable_entity_ids,
    surroundings,
)
from lorenzo_api.inherited_information import MAX_PROTOTYPE_HOPS
from lorenzo_api.models import (
    Being,
    Entity,
    EntityPrototype,
    EntitySlug,
    Item,
    Ownership,
    VItemInstance,
)

MY_HINT = "my"
MY_PREFIX = f"{MY_HINT}/"


async def anchors_of(
    session: AsyncSession, *, tenant_id: uuid.UUID, home_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID | None]:
    """The being each text home belongs to: the home itself if it is a being,
    else the nearest being among what it is in or with (surroundings:
    containers, then the owner and the owner's containers), else None.
    """
    homes = frozenset(home_ids)
    if not homes:
        return {}
    paths = await surroundings(session, entity_ids=homes, tenant_id=tenant_id)
    candidates = {home: [home, *paths.get(home, [])] for home in homes}
    every = {entity_id for chain in candidates.values() for entity_id in chain}
    beings = set(
        (
            await session.execute(
                select(Being.entity_id).where(
                    Being.tenant_id == tenant_id, Being.entity_id.in_(every)
                )
            )
        ).scalars()
    )
    return {
        home: next((entity_id for entity_id in chain if entity_id in beings), None)
        for home, chain in candidates.items()
    }


async def pick_for_anchor(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    anchor_id: uuid.UUID,
    targets: Iterable[uuid.UUID],
    reach: frozenset[uuid.UUID] | None,
) -> dict[uuid.UUID, uuid.UUID]:
    """For each target entity (what the slug after `my/` names) the entity it
    means for this anchor, if any. `reach` is the caller's reach (ADR 0040,
    None for ORGA): an instance the caller may not see is not a candidate.

    A catalog item means one of its instances (itself or through a derived
    item) that the anchor holds; any other entity means itself, if held.
    The pick is deterministic: a direct instance before a derived one, owned
    before merely contained, then by name, then by id.
    """
    held = await reachable_entity_ids(
        session, root_entity_ids=frozenset({anchor_id}), tenant_id=tenant_id
    )
    picks: dict[uuid.UUID, uuid.UUID] = {}
    for target in dict.fromkeys(targets):
        if await session.scalar(select(exists().where(Item.entity_id == target))):
            descendants = prototype_descendants_cte(target, tenant_id)
            rows = (
                await session.execute(
                    select(VItemInstance.entity_id, VItemInstance.owner_entity_id)
                    .join(Entity, Entity.id == VItemInstance.entity_id)
                    .where(
                        VItemInstance.tenant_id == tenant_id,
                        VItemInstance.entity_id.in_(select(descendants.c.descendant_id)),
                        VItemInstance.entity_id.in_(held),
                    )
                    .order_by(
                        ~exists().where(
                            EntityPrototype.entity_id == VItemInstance.entity_id,
                            EntityPrototype.prototype_id == target,
                        ),
                        ~exists().where(
                            Ownership.owned_entity_id == VItemInstance.entity_id,
                            Ownership.owner_character_id == anchor_id,
                        ),
                        Entity.name,
                        Entity.id,
                    )
                )
            ).tuples()
            for entity_id, owner_id in rows:
                if reach is None or owner_id is None or entity_id in reach:
                    picks[target] = entity_id
                    break
        elif target in held:
            instance = (
                await session.execute(
                    select(VItemInstance.owner_entity_id).where(
                        VItemInstance.entity_id == target, VItemInstance.tenant_id == tenant_id
                    )
                )
            ).first()
            # Not an instance: nothing narrows it. An instance: ADR 0040's rule.
            if instance is None or reach is None or instance[0] is None or target in reach:
                picks[target] = target
    return picks


async def item_ancestor_slugs(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> dict[uuid.UUID, str]:
    """The slugs of the catalog items this instance derives from, by entity
    id: what a `my/` link names when it means this instance.
    """
    seen: set[uuid.UUID] = set()
    frontier = {entity_id}
    for _ in range(MAX_PROTOTYPE_HOPS):
        parents = set(
            (
                await session.execute(
                    select(EntityPrototype.prototype_id).where(
                        EntityPrototype.tenant_id == tenant_id,
                        EntityPrototype.entity_id.in_(frontier),
                    )
                )
            ).scalars()
        )
        frontier = parents - seen
        if not frontier:
            break
        seen |= frontier
    if not seen:
        return {}
    rows = (
        await session.execute(
            select(EntitySlug.entity_id, EntitySlug.slug).where(
                EntitySlug.tenant_id == tenant_id,
                EntitySlug.entity_id.in_(seen),
                EntitySlug.entity_id.in_(select(Item.entity_id)),
            )
        )
    ).tuples()
    return {item_id: name for item_id, name in rows}


__all__ = ["MY_HINT", "MY_PREFIX", "anchors_of", "item_ancestor_slugs", "pick_for_anchor"]
