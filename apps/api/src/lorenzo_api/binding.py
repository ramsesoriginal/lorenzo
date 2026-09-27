"""Binding: things that won't leave their owner - see ADR 0129.

The API reads one enum stat by name, `binding`, tenant data like the
capacity stats (ADR 0128), resolved with its prototypes and formulas. It
binds only to the item's owner, and only when the owner is a being:

- `on_own`: bound while a being owns it; once the owner carries it, it
  can't leave what the owner carries.
- `on_pickup`: bound while its owner carries it, and can't leave what the
  owner carries.
- `on_equip`: bound while its owner has it equipped - contained directly -
  and can't leave the owner.

A bound item's owner can't change. Nothing is stored: whether something is
bound follows from where it is and who owns it, so a GM moving it or giving
it away (`override`) is the curse lifted, until it binds again - unless the
GM lifts it for good, setting the item's own `binding` to `none`.
"""

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.entity_access import containment_paths, recursive_descendants_cte
from lorenzo_api.exceptions import BindingNotLiftableError, ItemBoundError
from lorenzo_api.models import (
    Being,
    ComputedStat,
    Entity,
    EntityStat,
    Ownership,
    StatDefinition,
    StatValueType,
    VEffectiveStat,
    VItemInstance,
    formula_load_options,
)
from lorenzo_api.stat_contents import load_contents
from lorenzo_api.stat_evaluation import Contents, Value, evaluate

__all__ = [
    "BindingCheck",
    "attach_bound",
    "copy_binding",
    "is_bound",
    "lift_binding",
    "refuse_owner_change",
]

BINDING = "binding"
# What each binding reads as, in a refusal.
_LABELS = {
    "on_own": "binds when owned",
    "on_pickup": "binds on pickup",
    "on_equip": "binds on equip",
}


def _binds(value: Value | None) -> str | None:
    """The binding `value` stands for, or None: unset, `none`, or anything
    outside the vocabulary binds nothing."""
    return value if isinstance(value, str) and value in _LABELS else None


def _in_place(binding: str, owner_id: uuid.UUID, path: Sequence[uuid.UUID]) -> bool:
    """Whether it's where its binding holds it: equipped by its owner for
    `on_equip`, else anywhere its owner carries it. `path` is its
    containers, nearest first."""
    if binding == "on_equip":
        return path[:1] == [owner_id]
    return owner_id in path


def is_bound(
    binding: str | None,
    *,
    owner_id: uuid.UUID | None,
    owner_is_being: bool,
    path: Sequence[uuid.UUID],
) -> bool:
    """RFC 0030 §8's table: whether an item's owner can't change right now."""
    if binding is None or owner_id is None or not owner_is_being:
        return False
    return binding == "on_own" or _in_place(binding, owner_id, path)


def _view_binding(view: VItemInstance) -> str | None:
    """The binding `view` resolves to, from the stats it already loaded."""
    for stat in view.entity.effective_stats:
        definition = stat.stat_definition
        if definition.name == BINDING and definition.value_type is StatValueType.ENUM:
            return _binds(view.resolved_stat_values().get(definition.id))
    return None


async def _beings(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_ids: Iterable[uuid.UUID]
) -> set[uuid.UUID]:
    ids = set(entity_ids)
    if not ids:
        return set()
    return set(
        await session.scalars(
            select(Being.entity_id).where(Being.entity_id.in_(ids), Being.tenant_id == tenant_id)
        )
    )


async def attach_bound(
    session: AsyncSession, views: Sequence[VItemInstance], *, tenant_id: uuid.UUID
) -> None:
    """Sets each view's `bound`. Call after stat_contents.attach_contents: a
    binding a formula decides reads resolved stats. Costs nothing more
    unless something on the page binds."""
    bindings = {
        view.entity_id: binding
        for view in views
        if view.owner_entity_id is not None and (binding := _view_binding(view)) is not None
    }
    beings = await _beings(
        session,
        tenant_id=tenant_id,
        entity_ids={
            view.owner_entity_id
            for view in views
            if view.entity_id in bindings and view.owner_entity_id is not None
        },
    )
    # Only on_pickup looks further up than the item's own container.
    paths = await containment_paths(
        session,
        entity_ids=frozenset(
            entity_id for entity_id, binding in bindings.items() if binding == "on_pickup"
        ),
        tenant_id=tenant_id,
    )
    for view in views:
        path = paths.get(view.entity_id)
        if path is None:
            path = [view.container_entity_id] if view.container_entity_id is not None else []
        view.bound = is_bound(
            bindings.get(view.entity_id),
            owner_id=view.owner_entity_id,
            owner_is_being=view.owner_entity_id in beings,
            path=path,
        )


async def _definition(session: AsyncSession, *, tenant_id: uuid.UUID) -> StatDefinition | None:
    """The tenant's `binding`, if it has one that can bind: an enum."""
    definition: StatDefinition | None = await session.scalar(
        select(StatDefinition)
        .where(
            StatDefinition.tenant_id == tenant_id,
            StatDefinition.name == BINDING,
            StatDefinition.value_type == StatValueType.ENUM,
        )
        .options(selectinload(StatDefinition.enum_values))
    )
    return definition


async def _bindings(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    definition_id: uuid.UUID,
    entity_ids: Iterable[uuid.UUID],
) -> dict[uuid.UUID, str]:
    """Each of `entity_ids` that binds, and how - resolved with its formulas,
    as a read would."""
    ids = set(entity_ids)
    if not ids:
        return {}
    candidates = set(
        await session.scalars(
            select(VEffectiveStat.entity_id).where(
                VEffectiveStat.entity_id.in_(ids),
                VEffectiveStat.stat_definition_id == definition_id,
                VEffectiveStat.tenant_id == tenant_id,
            )
        )
    )
    if not candidates:
        return {}
    stats: dict[uuid.UUID, list[VEffectiveStat]] = {entity_id: [] for entity_id in candidates}
    for stat in await session.scalars(
        select(VEffectiveStat)
        .where(VEffectiveStat.entity_id.in_(candidates), VEffectiveStat.tenant_id == tenant_id)
        .options(
            selectinload(VEffectiveStat.stat_definition),
            *formula_load_options(selectinload(VEffectiveStat.computed_stat)),
        )
        # Read again within the write's transaction: a lift just changed it.
        .execution_options(populate_existing=True)
    ):
        stats[stat.entity_id].append(stat)
    needing = [
        entity_id
        for entity_id, rows in stats.items()
        if any(
            row.computed_entity_id is not None
            and row.computed_stat is not None
            and row.computed_stat.contents is not None
            for row in rows
        )
    ]
    loaded = (
        await load_contents(session, tenant_id=tenant_id, root_ids=needing)
        if needing
        else Contents(stats={}, children={})
    )
    contents = Contents(stats={**loaded.stats, **stats}, children=loaded.children)
    result: dict[uuid.UUID, str] = {}
    for entity_id in candidates:
        binding = _binds(
            evaluate(stats[entity_id], entity_id=entity_id, contents=contents).get(definition_id)
        )
        if binding is not None:
            result[entity_id] = binding
    return result


async def _owners(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """Each of `entity_ids`' owner, where the owner is a being: only a being
    binds."""
    ids = set(entity_ids)
    if not ids:
        return {}
    owners = dict(
        (
            await session.execute(
                select(Ownership.owned_entity_id, Ownership.owner_character_id).where(
                    Ownership.owned_entity_id.in_(ids), Ownership.tenant_id == tenant_id
                )
            )
        )
        .tuples()
        .all()
    )
    beings = await _beings(session, tenant_id=tenant_id, entity_ids=owners.values())
    return {item: owner for item, owner in owners.items() if owner in beings}


async def _refusal(
    session: AsyncSession, *, item_id: uuid.UUID, owner_id: uuid.UUID, binding: str, what: str
) -> ItemBoundError:
    """The 409 for `item_id`; `what` it can't do may name the `{owner}`."""
    names = dict(
        (
            await session.execute(
                select(Entity.id, Entity.name).where(Entity.id.in_({item_id, owner_id}))
            )
        )
        .tuples()
        .all()
    )
    item, owner = names.get(item_id, str(item_id)), names.get(owner_id, str(owner_id))
    return ItemBoundError(
        detail=(
            f"{item} is bound to {owner} ({_LABELS[binding]}), so it can't "
            f"{what.format(owner=owner)}."
        ),
        item={"id": str(item_id), "name": item},
        binding=binding,
        owner={"id": str(owner_id), "name": owner},
    )


async def refuse_owner_change(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    """Raises 409 if `entity_id` is bound: its owner can't change."""
    definition = await _definition(session, tenant_id=tenant_id)
    if definition is None:
        return
    bindings = await _bindings(
        session, tenant_id=tenant_id, definition_id=definition.id, entity_ids=[entity_id]
    )
    binding = bindings.get(entity_id)
    owner_id = (await _owners(session, tenant_id=tenant_id, entity_ids=[entity_id])).get(entity_id)
    if binding is None or owner_id is None:
        return
    paths = await containment_paths(session, entity_ids=frozenset({entity_id}), tenant_id=tenant_id)
    if is_bound(binding, owner_id=owner_id, owner_is_being=True, path=paths[entity_id]):
        raise await _refusal(
            session, item_id=entity_id, owner_id=owner_id, binding=binding, what="change hands"
        )


@dataclass
class BindingCheck:
    """One move's check: `start` before the move, `finish` after it. What's
    held is every bound thing, the moved one or anything inside it, that's
    where its binding holds it; it has to still be there afterwards."""

    session: AsyncSession
    tenant_id: uuid.UUID
    # Each held thing, outermost first: its binding and its owner.
    held: list[tuple[uuid.UUID, str, uuid.UUID]]

    @classmethod
    async def start(
        cls, session: AsyncSession, *, tenant_id: uuid.UUID, moved_id: uuid.UUID
    ) -> BindingCheck | None:
        """None when there's nothing to hold: the tenant has no `binding`,
        or nothing moving is where a binding holds it."""
        definition = await _definition(session, tenant_id=tenant_id)
        if definition is None:
            return None
        descendants = recursive_descendants_cte(frozenset({moved_id}), tenant_id)
        moving = {moved_id} | set(await session.scalars(select(descendants.c.child_entity_id)))
        bindings = await _bindings(
            session, tenant_id=tenant_id, definition_id=definition.id, entity_ids=moving
        )
        owners = await _owners(session, tenant_id=tenant_id, entity_ids=bindings)
        paths = await containment_paths(session, entity_ids=frozenset(owners), tenant_id=tenant_id)
        held = [
            (entity_id, bindings[entity_id], owner_id)
            for entity_id, owner_id in owners.items()
            if _in_place(bindings[entity_id], owner_id, paths[entity_id])
        ]
        if not held:
            return None
        # The moved thing first, then outermost first, so a refusal names the
        # nearest reason.
        held.sort(key=lambda row: (row[0] != moved_id, len(paths[row[0]]), str(row[0])))
        return cls(session, tenant_id, held)

    async def finish(self) -> None:
        """Refuses the move (409) if it took a held thing out of place."""
        await self.session.flush()
        paths = await containment_paths(
            self.session,
            entity_ids=frozenset(entity_id for entity_id, _, _ in self.held),
            tenant_id=self.tenant_id,
        )
        for entity_id, binding, owner_id in self.held:
            if not _in_place(binding, owner_id, paths[entity_id]):
                raise await _refusal(
                    self.session,
                    item_id=entity_id,
                    owner_id=owner_id,
                    binding=binding,
                    what=(
                        "be taken off {owner}"
                        if binding == "on_equip"
                        else "leave what {owner} carries"
                    ),
                )


async def lift_binding(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> bool:
    """Sets `entity_id`'s own `binding` to `none`, so it won't bind again.
    Returns whether there was a `binding` to set: without one, nothing
    binds, and there's nothing to do."""
    definition = await _definition(session, tenant_id=tenant_id)
    if definition is None:
        return False
    name = await session.scalar(select(Entity.name).where(Entity.id == entity_id))
    if "none" not in {row.value for row in definition.enum_values}:
        raise BindingNotLiftableError(
            detail=f"`binding` has no `none` value to lift {name}'s binding to."
        )
    if await session.get(ComputedStat, (entity_id, definition.id)) is not None:
        raise BindingNotLiftableError(
            detail=f"{name}'s binding is its own formula. Change the formula instead."
        )
    stat = await session.get(EntityStat, (entity_id, definition.id))
    if stat is None:
        stat = EntityStat(
            entity_id=entity_id, stat_definition_id=definition.id, tenant_id=tenant_id
        )
        session.add(stat)
    stat.value_int = stat.value_float = stat.value_bool = None
    stat.value_text = "none"
    return True


async def copy_binding(
    session: AsyncSession, *, tenant_id: uuid.UUID, source_id: uuid.UUID, target_id: uuid.UUID
) -> None:
    """A stack binds as a whole, so a part split off it copies the source's
    own `binding`, if it has one - a lifted stack's halves both stay
    lifted."""
    definition = await _definition(session, tenant_id=tenant_id)
    if definition is None:
        return
    own = await session.get(EntityStat, (source_id, definition.id))
    if own is None:
        return
    session.add(
        EntityStat(
            entity_id=target_id,
            stat_definition_id=definition.id,
            tenant_id=tenant_id,
            value_text=own.value_text,
        )
    )
