"""What the connection routes and the entry routes share: the limits of a library and touching a
connection (ADR 0363)."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import InvalidConnectionError
from lorenzo_api.models import Connection, Entity

#: A library holds at most this many connections.
MAX_CONNECTIONS_PER_LIBRARY = 10_000
#: One hub write makes at most this many.
MAX_HUB_SPOKES = 50
#: A Map's links answer at most this many rows.
MAX_LINK_ROWS = 500


async def require_connection_room(
    session: AsyncSession, *, tenant_id: uuid.UUID, adding: int = 1
) -> None:
    """Refuses connections beyond the library's limit: `adding` more than there are now."""
    count = await session.scalar(
        select(func.count()).select_from(Connection).where(Connection.tenant_id == tenant_id)
    )
    if (count or 0) + adding > MAX_CONNECTIONS_PER_LIBRARY:
        raise InvalidConnectionError(
            detail=f"A library holds at most {MAX_CONNECTIONS_PER_LIBRARY:,} connections"
        )


async def touch_connection(
    session: AsyncSession, *, tenant_id: uuid.UUID, connection_id: uuid.UUID, user_id: uuid.UUID
) -> Entity:
    """Moves the connection entry's `updated_at`, and so its `ETag`."""
    await session.execute(
        update(Entity)
        .where(Entity.id == connection_id, Entity.tenant_id == tenant_id)
        .values(updated_at=func.now(), updated_by=user_id)
    )
    entity = await session.scalar(
        select(Entity)
        .where(Entity.id == connection_id, Entity.tenant_id == tenant_id)
        .execution_options(populate_existing=True)
    )
    assert entity is not None
    return entity
