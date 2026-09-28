"""Capacity: what a container or a being can take - see ADR 0128.

The API reads a few stats by name, tenant data like `is_container` (ADR
0047), each resolved with its formulas: `carry_capacity` against
`Σ weight × quantity` of what's directly inside, on the container moved
into and every container above it; `containment_capacity` against
`Σ size × quantity`, and `max_item_size` against the moved item's own
`size`, on that container only.

A write that puts something somewhere measures the loads before it and
again after, inside its own transaction, and is refused only when a load
grows past its limit - so taking something out, moving within what a being
carries, or filling a Bag of Holding (whose own weight is fixed) never is.
Loads are what a `contents` formula over `weight` or `size` would add up
(ADR 0127), evaluated with stat_contents' loader.
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.entity_access import containment_paths
from lorenzo_api.exceptions import CapacityExceededError
from lorenzo_api.models import (
    Entity,
    StatDefinition,
    StatValueType,
    VEffectiveStat,
    formula_load_options,
)
from lorenzo_api.stat_contents import load_contents
from lorenzo_api.stat_evaluation import Contents, ContentsFormula, Value, evaluate

__all__ = ["CapacityCheck", "lock_ahead"]

_LIMITS = ("carry_capacity", "containment_capacity", "max_item_size")
_NAMES = ("weight", "size", *_LIMITS)
# What each capacity adds up, and the key its load is evaluated under - an
# unsaved contents formula (ADR 0104's override), under a key no stat has.
_LOADS = {
    "carry_capacity": ("weight", uuid.uuid4()),
    "containment_capacity": ("size", uuid.uuid4()),
}

Values = dict[uuid.UUID, Value]


def _number(value: Value | None) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _shown(number: float) -> str:
    return str(int(number)) if number.is_integer() else f"{number:g}"


async def _known(session: AsyncSession, tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    return {
        name: definition_id
        for definition_id, name in await session.execute(
            select(StatDefinition.id, StatDefinition.name).where(
                StatDefinition.tenant_id == tenant_id, StatDefinition.name.in_(_NAMES)
            )
        )
    }


async def _lock(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_ids: Iterable[uuid.UUID]
) -> None:
    # Id order, so no two lock in a cycle. FOR NO KEY UPDATE: another check's
    # lock still waits on it, but the share lock a foreign key takes on these
    # rows - an ownership row's on its owner, a containment row's on its
    # container - never does, so no write taking those can wait in a cycle
    # with a check (ADR 0128's Addendum).
    await session.execute(
        select(Entity.id)
        .where(Entity.id.in_(set(entity_ids)), Entity.tenant_id == tenant_id)
        .order_by(Entity.id)
        .with_for_update(key_share=True)
    )


async def lock_ahead(
    session: AsyncSession, *, tenant_id: uuid.UUID, target_ids: Iterable[uuid.UUID]
) -> None:
    """For several checks in one transaction, bulk-assign's entries: locks
    every target's chain they'll lock, in one id-ordered go, before any of
    them runs.

    What a check locks stays locked until the commit, so locked check by
    check, two transactions could each hold a chain the other's next check
    waits for. Nothing, when there's no target or the tenant defines no
    capacity: then no check locks anything.
    """
    targets = frozenset(target_ids)
    if not targets:
        return
    known = await _known(session, tenant_id)
    if not any(name in known for name in _LIMITS):
        return
    paths = await containment_paths(session, entity_ids=targets, tenant_id=tenant_id)
    await _lock(
        session,
        tenant_id=tenant_id,
        entity_ids={*targets, *(link for path in paths.values() for link in path)},
    )


@dataclass
class CapacityCheck:
    """One write's check: `start` before the write, `finish` after it."""

    session: AsyncSession
    tenant_id: uuid.UUID
    target_id: uuid.UUID
    chain: list[uuid.UUID]
    known: dict[str, uuid.UUID]
    before: dict[uuid.UUID, Values]

    @classmethod
    async def start(
        cls, session: AsyncSession, *, tenant_id: uuid.UUID, target_id: uuid.UUID
    ) -> CapacityCheck | None:
        """Locks `target_id`'s chain and measures it, or None when the
        tenant defines no capacity at all - then nothing is checked."""
        known = await _known(session, tenant_id)
        if not any(name in known for name in _LIMITS):
            return None
        paths = await containment_paths(
            session, entity_ids=frozenset({target_id}), tenant_id=tenant_id
        )
        chain = [target_id, *paths[target_id]]
        # Two moves into one bag queue up here, so the second measures the
        # first's result (ADR 0128).
        await _lock(session, tenant_id=tenant_id, entity_ids=chain)
        check = cls(session, tenant_id, target_id, chain, known, {})
        check.before, _ = await check._measure()
        return check

    async def finish(self, *, moved_ids: Iterable[uuid.UUID]) -> None:
        """Measures again, after the write, and refuses it (409) if it made
        a load grow past its limit."""
        await self.session.flush()
        after, contents = await self._measure()
        for container_id in self.chain:
            for limit_name, (_, load_key) in _LOADS.items():
                if limit_name != "carry_capacity" and container_id != self.target_id:
                    continue
                limit_id = self.known.get(limit_name)
                limit = _number(after[container_id].get(limit_id)) if limit_id else None
                if limit is None:
                    continue
                load = _number(after[container_id].get(load_key)) or 0.0
                was = _number(self.before[container_id].get(load_key)) or 0.0
                if load > limit and load > was:
                    name = await self._name(container_id)
                    detail = (
                        f"{name} can carry {_shown(limit)}, and this would make it {_shown(load)}."
                        if limit_name == "carry_capacity"
                        else f"{name} has room for {_shown(limit)}, and this would fill it to "
                        f"{_shown(load)}."
                    )
                    raise CapacityExceededError(
                        detail=detail,
                        container={"id": str(container_id), "name": name},
                        stat=limit_name,
                        limit=limit,
                        load=load,
                    )

        size_id, max_id = self.known.get("size"), self.known.get("max_item_size")
        largest = _number(after[self.target_id].get(max_id)) if max_id else None
        if size_id is None or largest is None:
            return
        for moved_id in moved_ids:
            size = _number(
                evaluate(
                    contents.stats.get(moved_id, ()), entity_id=moved_id, contents=contents
                ).get(size_id)
            )
            if size is not None and size > largest:
                name, item = await self._name(self.target_id), await self._name(moved_id)
                raise CapacityExceededError(
                    detail=(
                        f"{name} takes nothing larger than {_shown(largest)}, and {item} is "
                        f"{_shown(size)}."
                    ),
                    container={"id": str(self.target_id), "name": name},
                    stat="max_item_size",
                    limit=largest,
                    load=size,
                )

    async def _measure(self) -> tuple[dict[uuid.UUID, Values], Contents]:
        """Each chain container's resolved stats, plus its loads under their
        synthetic keys; and what's inside, for the moved items' sizes."""
        loaded = await load_contents(self.session, tenant_id=self.tenant_id, root_ids=self.chain)
        own: dict[uuid.UUID, list[VEffectiveStat]] = {entity_id: [] for entity_id in self.chain}
        for stat in await self.session.scalars(
            select(VEffectiveStat)
            .where(
                VEffectiveStat.entity_id.in_(self.chain),
                VEffectiveStat.tenant_id == self.tenant_id,
            )
            .options(
                selectinload(VEffectiveStat.stat_definition),
                *formula_load_options(selectinload(VEffectiveStat.computed_stat)),
            )
            # A re-measure in the same transaction reads what the write changed.
            .execution_options(populate_existing=True)
        ):
            own[stat.entity_id].append(stat)
        contents = Contents(stats={**loaded.stats, **own}, children=loaded.children)
        overrides = {
            key: (ContentsFormula(self.known[load_name]), StatValueType.FLOAT)
            for load_name, key in _LOADS.values()
            if load_name in self.known
        }
        values = {
            entity_id: evaluate(
                own[entity_id], overrides=overrides, entity_id=entity_id, contents=contents
            )
            for entity_id in self.chain
        }
        return values, contents

    async def _name(self, entity_id: uuid.UUID) -> str:
        name = await self.session.scalar(select(Entity.name).where(Entity.id == entity_id))
        return name or str(entity_id)
