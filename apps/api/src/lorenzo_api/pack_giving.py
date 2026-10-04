"""Handing a pack out - RFC 0032, ADR 0149.

`hand_out` is what `POST .../item-instances/from-pack` does once the caller
is authorized: it reads the pack item's public description (the list `packs.py`
parses), checks the list can be handed out, and creates what it names in the
caller's own transaction. Nothing here commits, so a refusal at any point,
capacity's included, leaves nothing behind.

It writes the same rows `create_item_instance` does - an `Entity`, its
`ItemInstance` and `EntityPrototype`, an `Ownership` row, and a `Containment`
row where something is inside something - and checks capacity the way that
route does for an instance created inside something (ADR 0128).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.capacity import CapacityCheck
from lorenzo_api.dependencies import get_entity_or_404
from lorenzo_api.exceptions import InvalidPackOwnerError, NotAPackError, PackListError
from lorenzo_api.models import (
    Being,
    Containment,
    Entity,
    EntityPrototype,
    EntitySlug,
    GroupMember,
    Information,
    Item,
    ItemInstance,
    Ownership,
    Payload,
    PayloadDescription,
)
from lorenzo_api.packs import PackNode, list_problems, nest, parse_pack_list

__all__ = ["Created", "hand_out"]

OwnerKind = Literal["being", "group"]


@dataclass(slots=True)
class Created:
    """An instance made for a line of the list, and what's inside it."""

    entity_id: uuid.UUID
    prototype_id: uuid.UUID
    children: list[Created] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Item:
    entity_id: uuid.UUID
    name: str


async def _owner_kind(
    session: AsyncSession, *, tenant_id: uuid.UUID, owner_id: uuid.UUID
) -> OwnerKind:
    """A being, or a group: an entity named by `group_member` rows, which is
    all a group is (ADR 0028, 0045) - so one with no member yet is not
    recognised. `404` for an entity that isn't the tenant's at all."""
    await get_entity_or_404(session, owner_id, tenant_id)
    if await session.scalar(
        select(Being.entity_id).where(Being.entity_id == owner_id, Being.tenant_id == tenant_id)
    ):
        return "being"
    if await session.scalar(
        select(GroupMember.group_entity_id)
        .where(GroupMember.group_entity_id == owner_id, GroupMember.tenant_id == tenant_id)
        .limit(1)
    ):
        return "group"
    raise InvalidPackOwnerError(
        detail=f"{owner_id} is neither a being nor a group with members in tenant {tenant_id}"
    )


async def _public_description(
    session: AsyncSession, *, tenant_id: uuid.UUID, pack_id: uuid.UUID
) -> str:
    """The pack item's own public description, its payloads joined with a
    newline in order (as the CLI reads it, ADR 0145). Not what the caller
    can see: the answer mustn't depend on who asks, and GM-only text is never
    read as a list."""
    is_item = await session.scalar(
        select(Item.entity_id).where(Item.entity_id == pack_id, Item.tenant_id == tenant_id)
    )
    if is_item is None:
        raise NotAPackError(detail=f"{pack_id} is not an item of tenant {tenant_id}")
    contents = await session.scalars(
        select(PayloadDescription.content)
        .join(Payload, Payload.id == PayloadDescription.payload_id)
        .join(Information, Information.id == Payload.information_id)
        .where(
            Information.entity_id == pack_id,
            Information.tenant_id == tenant_id,
            Information.type == "description",
            Information.is_public.is_(True),
        )
        .order_by(Information.order, Payload.order)
    )
    return "\n".join(contents)


async def _items_by_slug(
    session: AsyncSession, *, tenant_id: uuid.UUID, slugs: set[str]
) -> dict[str, _Item]:
    rows = await session.execute(
        select(EntitySlug.slug, Entity.id, Entity.name)
        .join(Entity, Entity.id == EntitySlug.entity_id)
        .join(Item, Item.entity_id == Entity.id)
        .where(EntitySlug.tenant_id == tenant_id, EntitySlug.slug.in_(slugs))
    )
    return {slug: _Item(entity_id, name) for slug, entity_id, name in rows}


def _slugs(nodes: list[PackNode]) -> set[str]:
    found: set[str] = set()
    for node in nodes:
        if node.line.slug is not None:
            found.add(node.line.slug)
        found |= _slugs(node.children)
    return found


@dataclass
class _Builder:
    session: AsyncSession
    tenant_id: uuid.UUID
    actor_id: uuid.UUID
    owner_id: uuid.UUID
    kind: OwnerKind
    items: dict[str, _Item]
    override: bool

    async def make(self, node: PackNode, *, parent: Created | None) -> list[Created]:
        """What `node` makes, inside `parent`, or at the top of the list when
        there is none. A line with lines inside is a container, made once for
        each unit; any other line is one stack - except at the top of a
        group's, which has no container to hold a count (ADR 0149)."""
        line = node.line
        assert line.slug is not None  # checked by list_problems
        item = self.items[line.slug]
        made: list[Created] = []
        if node.children:
            for _ in range(line.quantity):
                container = await self._create(item, parent=parent, quantity=1)
                made.append(container)
                await self._fill(container, node.children)
            return made
        if parent is None and self.kind == "group":
            return [await self._create(item, parent=None, quantity=1) for _ in range(line.quantity)]
        return [await self._create(item, parent=parent, quantity=line.quantity)]

    async def _fill(self, container: Created, nodes: list[PackNode]) -> None:
        # The container exists and is flushed, so its own load limits (and
        # everything above it) are measured before anything goes in.
        check = (
            None
            if self.override
            else await CapacityCheck.start(
                self.session, tenant_id=self.tenant_id, target_id=container.entity_id
            )
        )
        for node in nodes:
            container.children.extend(await self.make(node, parent=container))
        if check is not None:
            await check.finish(moved_ids=[child.entity_id for child in container.children])

    async def _create(self, item: _Item, *, parent: Created | None, quantity: int) -> Created:
        session = self.session
        entity = Entity(
            tenant_id=self.tenant_id,
            name=item.name,
            created_by=self.actor_id,
            updated_by=self.actor_id,
        )
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=self.tenant_id))
        session.add(
            EntityPrototype(
                entity_id=entity.id, prototype_id=item.entity_id, tenant_id=self.tenant_id
            )
        )
        session.add(
            Ownership(
                owned_entity_id=entity.id,
                owner_character_id=self.owner_id,
                tenant_id=self.tenant_id,
            )
        )
        # Top of a being's list: its hands (Equipped, ADR 0123). Top of a
        # group's: no container, since a group carries nothing (ADR 0124).
        holder = parent.entity_id if parent is not None else None
        if holder is None and self.kind == "being":
            holder = self.owner_id
        if holder is not None:
            session.add(
                Containment(
                    child_entity_id=entity.id,
                    parent_entity_id=holder,
                    tenant_id=self.tenant_id,
                    quantity=quantity,
                )
            )
        await session.flush()
        return Created(entity_id=entity.id, prototype_id=item.entity_id)


async def hand_out(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    actor_id: uuid.UUID,
    pack_id: uuid.UUID,
    owner_id: uuid.UUID,
    override: bool,
) -> list[Created]:
    """Creates what `pack_id`'s list names for `owner_id`, as one tree per
    top-level instance, in the order of the list. Raises a problem, and has
    made nothing the caller keeps, if the owner or the pack is wrong, the
    list can't be handed out, or capacity refuses it (ADR 0149)."""
    kind = await _owner_kind(session, tenant_id=tenant_id, owner_id=owner_id)
    text = await _public_description(session, tenant_id=tenant_id, pack_id=pack_id)
    nodes = nest(parse_pack_list(text))
    if not nodes:
        raise NotAPackError(
            detail=f"The public description of {pack_id} holds no contents list to hand out"
        )

    problems = list_problems(nodes, group=kind == "group")
    slugs = _slugs(nodes)
    items = await _items_by_slug(session, tenant_id=tenant_id, slugs=slugs)
    problems += [f"“{slug}” is not an item of this tenant" for slug in sorted(slugs - set(items))]
    if problems:
        raise PackListError(
            detail="The pack's list can't be handed out as it is: " + "; ".join(problems),
            lines=problems,
        )

    builder = _Builder(session, tenant_id, actor_id, owner_id, kind, items, override)
    # A being's hands are the target of everything at the top of the list:
    # its own limits, and every container it is inside, are measured around
    # the whole of it (ADR 0128). The check locks that chain, which also keeps
    # two packs into one being in order.
    check = (
        await CapacityCheck.start(session, tenant_id=tenant_id, target_id=owner_id)
        if kind == "being" and not override
        else None
    )
    created: list[Created] = []
    for node in nodes:
        created.extend(await builder.make(node, parent=None))
    if check is not None:
        await check.finish(moved_ids=[top.entity_id for top in created])
    return created
