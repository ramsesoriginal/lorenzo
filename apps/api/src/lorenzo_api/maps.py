"""What the Map routes and the kind routes share: the limits of a library and touching a Map
(ADR 0336, ADR 0338)."""

from __future__ import annotations

import uuid

from lorenzo_map import MAX_MAPS_PER_LIBRARY, MAX_PLACEMENTS_PER_MAP
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import InvalidMapError
from lorenzo_api.models import Entity, Map, MapPlacement


async def require_map_room(session: AsyncSession, *, tenant_id: uuid.UUID) -> None:
    """Refuses a Map beyond the library's limit."""
    count = await session.scalar(
        select(func.count()).select_from(Map).where(Map.tenant_id == tenant_id)
    )
    if (count or 0) >= MAX_MAPS_PER_LIBRARY:
        raise InvalidMapError(detail=f"A library holds at most {MAX_MAPS_PER_LIBRARY} Maps")


async def require_placement_room(
    session: AsyncSession, *, tenant_id: uuid.UUID, map_id: uuid.UUID
) -> None:
    """Refuses a placement beyond the Map's limit."""
    count = await session.scalar(
        select(func.count())
        .select_from(MapPlacement)
        .where(MapPlacement.tenant_id == tenant_id, MapPlacement.map_entity_id == map_id)
    )
    if (count or 0) >= MAX_PLACEMENTS_PER_MAP:
        raise InvalidMapError(detail=f"A Map holds at most {MAX_PLACEMENTS_PER_MAP} placements")


async def touch_map(
    session: AsyncSession, *, tenant_id: uuid.UUID, map_id: uuid.UUID, user_id: uuid.UUID
) -> Entity:
    """Moves the Map entry's `updated_at`, and so its `ETag`, for whoever reads it next."""
    await session.execute(
        update(Entity)
        .where(Entity.id == map_id, Entity.tenant_id == tenant_id)
        .values(updated_at=func.now(), updated_by=user_id)
    )
    entity = await session.scalar(
        select(Entity)
        .where(Entity.id == map_id, Entity.tenant_id == tenant_id)
        .execution_options(populate_existing=True)
    )
    assert entity is not None
    return entity
