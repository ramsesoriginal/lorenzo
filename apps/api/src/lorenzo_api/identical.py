"""Whether item instances are the same thing (ADR 0133): what a move with
`merge_identical` stacks together. Two are identical when they have the same
name, prototype(s), owner, and stat values of their own, and neither has
information of its own (a description, a note), a slug, or a formula of its
own - anything that makes one of them a thing of its own, which a merge
would lose.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    ComputedStat,
    Entity,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    Information,
    Ownership,
)

type StatValue = tuple[uuid.UUID, int | None, str | None, float | None, bool | None]


@dataclass(frozen=True)
class Signature:
    """What two identical instances share."""

    name: str
    prototype_ids: frozenset[uuid.UUID]
    owner_id: uuid.UUID | None
    stats: frozenset[StatValue]


async def signatures(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_ids: frozenset[uuid.UUID]
) -> dict[uuid.UUID, Signature | None]:
    """Each of entity_ids' signature, or None for one with something of its
    own a merge would lose - so it's never identical to anything."""
    if not entity_ids:
        return {}

    # Information (notes included), a slug, a formula: a thing of its own.
    own: set[uuid.UUID] = set()
    for column, tenant_column in (
        (Information.entity_id, Information.tenant_id),
        (EntitySlug.entity_id, EntitySlug.tenant_id),
        (ComputedStat.entity_id, ComputedStat.tenant_id),
    ):
        own |= set(
            await session.scalars(
                select(column).where(column.in_(entity_ids), tenant_column == tenant_id)
            )
        )
    names = dict(
        (
            await session.execute(
                select(Entity.id, Entity.name).where(
                    Entity.id.in_(entity_ids), Entity.tenant_id == tenant_id
                )
            )
        )
        .tuples()
        .all()
    )
    prototypes: defaultdict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for entity_id, prototype_id in await session.execute(
        select(EntityPrototype.entity_id, EntityPrototype.prototype_id).where(
            EntityPrototype.entity_id.in_(entity_ids), EntityPrototype.tenant_id == tenant_id
        )
    ):
        prototypes[entity_id].add(prototype_id)
    owners = dict(
        (
            await session.execute(
                select(Ownership.owned_entity_id, Ownership.owner_character_id).where(
                    Ownership.owned_entity_id.in_(entity_ids), Ownership.tenant_id == tenant_id
                )
            )
        )
        .tuples()
        .all()
    )
    stats: defaultdict[uuid.UUID, set[StatValue]] = defaultdict(set)
    for stat in await session.scalars(
        select(EntityStat).where(
            EntityStat.entity_id.in_(entity_ids), EntityStat.tenant_id == tenant_id
        )
    ):
        stats[stat.entity_id].add(
            (
                stat.stat_definition_id,
                stat.value_int,
                stat.value_text,
                stat.value_float,
                stat.value_bool,
            )
        )
    return {
        entity_id: None
        if entity_id in own or entity_id not in names
        else Signature(
            name=names[entity_id],
            prototype_ids=frozenset(prototypes[entity_id]),
            owner_id=owners.get(entity_id),
            stats=frozenset(stats[entity_id]),
        )
        for entity_id in entity_ids
    }
