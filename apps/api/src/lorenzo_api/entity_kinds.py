"""What an entry is: making one with kinds, adding and removing a kind, deleting one, and which
combinations of kinds a repository may publish (ADR 0217, RFC 0041 section 2).

An entry's kinds are the marker rows it has (`item`, `item_instance`, `being`, `character`): the
entity table says nothing about kind (ADR 0012). These functions are the one write path to the
two markers a route may add, `item` and `being`; `item_instance` and `character` have their own
routes (an inventory item is made from a catalog item, a being becomes a character by promotion).
"""

from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable, Sequence
from typing import Any, Literal

from sqlalchemy import delete, exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import (
    EntityKindInUseError,
    EntitySlugConflictError,
    InvalidPrototypeError,
    InventoryItemKindError,
    ItemPrototypeInUseError,
)
from lorenzo_api.models import (
    Being,
    Campaign,
    Character,
    Entity,
    EntityPrototype,
    EntitySlug,
    Item,
    ItemInstance,
)

# The kinds a route may add or remove.
Kind = Literal["item", "being"]

# The combinations of kinds a repository may be published with, each as its kinds in the order
# `entity_snapshot` writes them (alphabetical). A draft repository may hold any combination the
# routes allow; publishing is gated by this list (RFC 0041 section 2), and the round-trip matrix
# (tests/test_kind_matrix.py) holds it complete: a combination is added here together with its
# row in the matrix, and a row in the matrix is not a combination until it is added here.
# `item_instance` and `being` + `character` are what repositories held before kinds could be
# combined, and the matrix covers them.
PUBLISHABLE_KIND_COMBINATIONS: frozenset[tuple[str, ...]] = frozenset(
    {
        (),
        ("item",),
        ("being",),
        ("being", "item"),
        ("item_instance",),
        ("being", "character"),
    }
)


async def create_entry(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
    slug: str | None,
    kinds: Collection[Kind],
    parents: Collection[uuid.UUID],
    in_public_catalog: bool,
) -> Entity:
    """The entry, its link name, its marker rows and its parent edges, flushed in the caller's
    transaction. A taken link name is a 409 and a parent that is not an entry of the tenant a
    422, before anything is written."""
    if slug is not None:
        taken = await session.scalar(
            select(EntitySlug.entity_id).where(
                EntitySlug.tenant_id == tenant_id, EntitySlug.slug == slug
            )
        )
        if taken is not None:
            raise EntitySlugConflictError(
                detail=f"Slug {slug!r} is already in use in tenant {tenant_id}"
            )
    wanted = set(parents)
    if wanted:
        found = set(
            await session.scalars(
                select(Entity.id).where(Entity.id.in_(wanted), Entity.tenant_id == tenant_id)
            )
        )
        if missing := wanted - found:
            raise InvalidPrototypeError(
                detail=(
                    f"Parent id(s) {sorted(str(i) for i in missing)} do not exist "
                    f"in tenant {tenant_id}"
                )
            )
    entity = Entity(tenant_id=tenant_id, name=name, created_by=user_id, updated_by=user_id)
    session.add(entity)
    await session.flush()
    if slug is not None:
        session.add(EntitySlug(entity_id=entity.id, tenant_id=tenant_id, slug=slug))
    if "item" in kinds:
        session.add(
            Item(entity_id=entity.id, tenant_id=tenant_id, in_public_catalog=in_public_catalog)
        )
    if "being" in kinds:
        session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
    for parent_id in wanted:
        session.add(
            EntityPrototype(entity_id=entity.id, prototype_id=parent_id, tenant_id=tenant_id)
        )
    await session.flush()
    return entity


async def add_kind(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity: Entity,
    kind: Kind,
    user_id: uuid.UUID,
    in_public_catalog: bool | None = None,
) -> Literal["created", "changed", "unchanged"]:
    """Gives the entry the kind, and says what happened: `created` the marker row, `changed` an
    `item`'s `in_public_catalog` set to another value, or `unchanged`. Touches the entry
    (`updated_by`, and `updated_at`, so its ETag moves) only then. An inventory item never takes
    `item`; it may take `being`."""
    entity_id = entity.id
    result: Literal["created", "changed", "unchanged"] = "unchanged"
    if kind == "item":
        if await session.get(ItemInstance, entity_id) is not None:
            raise InventoryItemKindError(
                detail=f"Entry {entity_id} is an inventory item, which is made from a catalog "
                "item and is never one itself"
            )
        item = await session.get(Item, entity_id)
        if item is None:
            session.add(
                Item(
                    entity_id=entity_id,
                    tenant_id=tenant_id,
                    in_public_catalog=bool(in_public_catalog),
                )
            )
            result = "created"
        elif in_public_catalog is not None and item.in_public_catalog != in_public_catalog:
            item.in_public_catalog = in_public_catalog
            result = "changed"
    elif await session.get(Being, entity_id) is None:
        session.add(Being(entity_id=entity_id, tenant_id=tenant_id))
        result = "created"
    if result != "unchanged":
        _touch(entity, user_id)
        await session.flush()
    return result


async def remove_kind(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity: Entity,
    kind: Kind,
    user_id: uuid.UUID,
) -> bool:
    """Takes the kind away, and says whether the entry had it. `item` is refused while an
    inventory item inherits from the entry directly, which is the guard `DELETE /items/{id}` has
    (ADR 0032), and `being` while the entry is a character, whose key would cascade away with it:
    demote it first (ADR 0036)."""
    entity_id = entity.id
    if kind == "item":
        if await inventory_items_inherit(session, tenant_id=tenant_id, entity_id=entity_id):
            raise ItemPrototypeInUseError(
                detail=f"Entry {entity_id} is still a direct prototype of at least one "
                "inventory item"
            )
        marker: type[Item | Being] = Item
    else:
        if await session.get(Character, entity_id) is not None:
            raise EntityKindInUseError(
                detail=f"Entry {entity_id} is a character: demote it with "
                f"DELETE /tenants/{tenant_id}/characters/{entity_id} before it stops being a being"
            )
        marker = Being
    removed = await session.scalar(
        delete(marker)
        .where(marker.entity_id == entity_id, marker.tenant_id == tenant_id)
        .returning(marker.entity_id)
    )
    if removed is not None:
        _touch(entity, user_id)
        await session.flush()
    return removed is not None


async def inventory_items_inherit(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> bool:
    """Whether an inventory item has this entry as a direct prototype."""
    return bool(
        await session.scalar(
            select(
                exists().where(
                    EntityPrototype.prototype_id == entity_id,
                    EntityPrototype.tenant_id == tenant_id,
                    EntityPrototype.entity_id == ItemInstance.entity_id,
                )
            )
        )
    )


async def kinds_of_entry(session: AsyncSession, entity_id: uuid.UUID) -> set[str]:
    """The entry's kinds."""
    return {
        kind
        for kind, model in (
            ("item", Item),
            ("item_instance", ItemInstance),
            ("being", Being),
            ("character", Character),
        )
        if await session.get(model, entity_id) is not None
    }


async def require_deletable(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> set[str]:
    """The guards of every kind the entry has, composed (RFC 0041 section 2), and the kinds it
    has, so a delete can say what went with it. An inventory item is deleted through its own
    route (it moves what it holds back out, ADR 0128), a character is demoted before its entry
    goes, a catalog item is not deleted while an inventory item inherits from it, and a
    campaign's own entry stays with the campaign. A being that is no character, an item and a
    bare entry go."""
    kinds = await kinds_of_entry(session, entity_id)
    if "item_instance" in kinds:
        raise InventoryItemKindError(
            detail=f"Entry {entity_id} is an inventory item: delete it with "
            f"DELETE /tenants/{tenant_id}/item-instances/{entity_id}"
        )
    if "character" in kinds:
        raise EntityKindInUseError(
            detail=f"Entry {entity_id} is a character: demote it with "
            f"DELETE /tenants/{tenant_id}/characters/{entity_id} before deleting the entry"
        )
    if await session.scalar(select(func.count()).where(Campaign.entity_id == entity_id)):
        raise EntityKindInUseError(
            detail=f"Entry {entity_id} belongs to a campaign, which is deleted with its campaign"
        )
    if "item" in kinds and await inventory_items_inherit(
        session, tenant_id=tenant_id, entity_id=entity_id
    ):
        raise ItemPrototypeInUseError(
            detail=f"Entry {entity_id} is still a direct prototype of at least one inventory item"
        )
    return kinds


KIND_WORDS = {
    "item": "item",
    "item_instance": "inventory item",
    "being": "being",
    "character": "character",
}


def unpublishable_entries(
    rows: Iterable[tuple[uuid.UUID, str, Sequence[str]]],
) -> list[dict[str, Any]]:
    """The entries (id, name, kinds) whose combination of kinds is not in
    PUBLISHABLE_KIND_COMBINATIONS, ordered by name."""
    return [
        {"id": entity_id, "name": name, "kinds": list(kinds)}
        for entity_id, name, kinds in sorted(rows, key=lambda r: (r[1], str(r[0])))
        if tuple(kinds) not in PUBLISHABLE_KIND_COMBINATIONS
    ]


def unpublishable_sentence(entries: Sequence[dict[str, Any]]) -> str:
    """The refusal in words (ADR 0194): who they are, the first ten by name."""
    shown = [
        f"“{e['name']}” ({' and '.join(KIND_WORDS[k] for k in e['kinds'])})" for e in entries[:10]
    ]
    more = f", and {len(entries) - 10} more" if len(entries) > 10 else ""
    return (
        f"{len(entries)} of the entries here have a combination of kinds that copying and "
        f"updating have not been proven to carry yet: {', '.join(shown)}{more}. "
        "Take a kind away from each, or keep this repository a draft."
    )


def _touch(entity: Entity, user_id: uuid.UUID) -> None:
    entity.updated_by = user_id
    # Also when updated_by is already this user, so the ETag moves whoever writes.
    entity.updated_at = func.now()
