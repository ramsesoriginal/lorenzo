"""Locations: the part-of tree, its write guard and its reads as one reader sees them (ADR 0330).

The tree is single-parent and skip-level. A reader sees each visible Location under its nearest
visible ancestor: a hidden level is skipped, never marked, and the depth cap counts hops whatever
their visibility. Nothing here is containment, ownership, a prototype edge or a travel edge, and
nothing here widens GM reach (ADR 0046).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import CTE, Numeric, Select, any_, cast, func, literal, null, select, text
from sqlalchemy.dialects.postgresql import array as pg_array
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.exceptions import EntityNotFoundError, LocationTreeError
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import Entity, EntitySlug, Location, LocationPart

MAX_DEPTH = 50


async def lock_tree(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """One writer at a time per library, so two writes cannot each pass the cycle check and
    together make a cycle."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('lorenzo:locations:' || :tenant, 0))"),
        {"tenant": str(tenant_id)},
    )


def _upward(start: uuid.UUID, tenant_id: uuid.UUID) -> CTE:
    """Every ancestor of a Location with its distance, cycle-safe and capped."""
    base = select(
        LocationPart.parent_entity_id.label("id"),
        literal(1).label("depth"),
        pg_array([LocationPart.child_entity_id, LocationPart.parent_entity_id]).label("path"),
    ).where(LocationPart.child_entity_id == start, LocationPart.tenant_id == tenant_id)
    cte = base.cte("location_ancestors", recursive=True)
    step = (
        select(
            LocationPart.parent_entity_id.label("id"),
            (cte.c.depth + 1).label("depth"),
            cte.c.path.op("||")(LocationPart.parent_entity_id).label("path"),
        )
        .select_from(cte.join(LocationPart, LocationPart.child_entity_id == cte.c.id))
        .where(
            LocationPart.tenant_id == tenant_id,
            ~(LocationPart.parent_entity_id == any_(cte.c.path)),
            cte.c.depth < MAX_DEPTH,
        )
    )
    return cte.union_all(step)


async def ancestor_ids(
    session: AsyncSession, *, tenant_id: uuid.UUID, location_id: uuid.UUID
) -> list[uuid.UUID]:
    """Every ancestor, nearest first, whatever a reader may see. For the write guard only."""
    cte = _upward(location_id, tenant_id)
    rows = await session.execute(select(cte.c.id).order_by(cte.c.depth))
    return list(rows.scalars().all())


async def subtree_height(
    session: AsyncSession, *, tenant_id: uuid.UUID, location_id: uuid.UUID
) -> int:
    """How many levels lie below a Location (0 for a leaf), capped."""
    base = select(
        LocationPart.child_entity_id.label("id"),
        literal(1).label("depth"),
        pg_array([LocationPart.parent_entity_id, LocationPart.child_entity_id]).label("path"),
    ).where(LocationPart.parent_entity_id == location_id, LocationPart.tenant_id == tenant_id)
    cte = base.cte("location_descendants", recursive=True)
    step = (
        select(
            LocationPart.child_entity_id.label("id"),
            (cte.c.depth + 1).label("depth"),
            cte.c.path.op("||")(LocationPart.child_entity_id).label("path"),
        )
        .select_from(cte.join(LocationPart, LocationPart.parent_entity_id == cte.c.id))
        .where(
            LocationPart.tenant_id == tenant_id,
            ~(LocationPart.child_entity_id == any_(cte.c.path)),
            cte.c.depth < MAX_DEPTH,
        )
    )
    cte = cte.union_all(step)
    deepest = await session.scalar(select(func.max(cte.c.depth)))
    return int(deepest or 0)


async def set_part_of(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    child: uuid.UUID,
    parent: uuid.UUID,
    ordinal: Decimal | None,
) -> None:
    """Makes `child` a part of `parent`, or moves it. Both must be Locations of the library.
    A self reference, a cycle and a chain beyond the depth cap are one generic 422."""
    await lock_tree(session, tenant_id)
    if child == parent:
        raise LocationTreeError()
    for identity in (child, parent):
        if await session.get(Location, identity) is None:
            raise EntityNotFoundError(detail="No such Location in this library")
    above = await ancestor_ids(session, tenant_id=tenant_id, location_id=parent)
    if child in above:
        raise LocationTreeError()
    below = await subtree_height(session, tenant_id=tenant_id, location_id=child)
    if len(above) + 1 + 1 + below > MAX_DEPTH:
        raise LocationTreeError()
    row = await session.get(LocationPart, child)
    if row is None:
        session.add(
            LocationPart(
                child_entity_id=child,
                parent_entity_id=parent,
                tenant_id=tenant_id,
                level_ordinal=ordinal,
            )
        )
    else:
        row.parent_entity_id = parent
        row.level_ordinal = ordinal
    await session.flush()


async def clear_part_of(session: AsyncSession, *, tenant_id: uuid.UUID, child: uuid.UUID) -> None:
    await lock_tree(session, tenant_id)
    row = await session.get(LocationPart, child)
    if row is not None:
        await session.delete(row)
        await session.flush()


async def nearest_visible_ancestor(
    session: AsyncSession,
    vis: InformationVisibility,
    *,
    tenant_id: uuid.UUID,
    location_id: uuid.UUID,
) -> uuid.UUID | None:
    """The first ancestor the reader may see, skipping hidden levels without a trace."""
    base = select(
        LocationPart.parent_entity_id.label("id"),
        visible_entry_clause(vis, LocationPart.parent_entity_id).label("vis"),
        literal(1).label("depth"),
        pg_array([LocationPart.child_entity_id, LocationPart.parent_entity_id]).label("path"),
    ).where(LocationPart.child_entity_id == location_id, LocationPart.tenant_id == tenant_id)
    cte = base.cte("location_visible_ancestors", recursive=True)
    step = (
        select(
            LocationPart.parent_entity_id.label("id"),
            visible_entry_clause(vis, LocationPart.parent_entity_id).label("vis"),
            (cte.c.depth + 1).label("depth"),
            cte.c.path.op("||")(LocationPart.parent_entity_id).label("path"),
        )
        .select_from(cte.join(LocationPart, LocationPart.child_entity_id == cte.c.id))
        .where(
            LocationPart.tenant_id == tenant_id,
            ~cte.c.vis,
            ~(LocationPart.parent_entity_id == any_(cte.c.path)),
            cte.c.depth < MAX_DEPTH,
        )
    )
    cte = cte.union_all(step)
    return await session.scalar(select(cte.c.id).where(cte.c.vis).limit(1))


def visible_parts(
    vis: InformationVisibility, *, tenant_id: uuid.UUID, parent_id: uuid.UUID | None
) -> Select[tuple[uuid.UUID, str, str | None, Decimal | None]]:
    """The Locations a reader sees directly under `parent_id` (the visible roots when None):
    the visible children, and, through every hidden child, the visible ones below it. The walk
    stops at a visible Location and never reports a hidden one. Ordered by ordinal (none last),
    name and id."""
    if parent_id is None:
        base = select(
            Location.entity_id.label("id"),
            cast(null(), Numeric).label("ordinal"),
            visible_entry_clause(vis, Location.entity_id).label("vis"),
            literal(1).label("depth"),
            pg_array([Location.entity_id]).label("path"),
        ).where(
            Location.tenant_id == tenant_id,
            ~select(LocationPart.child_entity_id)
            .where(LocationPart.child_entity_id == Location.entity_id)
            .exists(),
        )
    else:
        base = select(
            LocationPart.child_entity_id.label("id"),
            LocationPart.level_ordinal.label("ordinal"),
            visible_entry_clause(vis, LocationPart.child_entity_id).label("vis"),
            literal(1).label("depth"),
            pg_array([LocationPart.parent_entity_id, LocationPart.child_entity_id]).label("path"),
        ).where(LocationPart.parent_entity_id == parent_id, LocationPart.tenant_id == tenant_id)
    cte = base.cte("location_visible_parts", recursive=True)
    step = (
        select(
            LocationPart.child_entity_id.label("id"),
            LocationPart.level_ordinal.label("ordinal"),
            visible_entry_clause(vis, LocationPart.child_entity_id).label("vis"),
            (cte.c.depth + 1).label("depth"),
            cte.c.path.op("||")(LocationPart.child_entity_id).label("path"),
        )
        .select_from(cte.join(LocationPart, LocationPart.parent_entity_id == cte.c.id))
        .where(
            LocationPart.tenant_id == tenant_id,
            ~cte.c.vis,
            ~(LocationPart.child_entity_id == any_(cte.c.path)),
            cte.c.depth < MAX_DEPTH,
        )
    )
    cte = cte.union_all(step)
    return (
        select(Entity.id, Entity.name, EntitySlug.slug, cte.c.ordinal)
        .select_from(cte.join(Entity, Entity.id == cte.c.id))
        .outerjoin(EntitySlug, EntitySlug.entity_id == Entity.id)
        .where(cte.c.vis)
        .order_by(cte.c.ordinal.is_(None), cte.c.ordinal, Entity.name, Entity.id)
    )
