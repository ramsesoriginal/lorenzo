"""What the relationship routes share: the library limit and touching a relationship (ADR 0399).

The rule that a relationship is read only with both its ends lives in `entry_visibility`, in the
clause every entry read applies, so nothing here has to repeat it."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import InvalidRelationshipError
from lorenzo_api.models import Entity, Relationship

#: A library holds at most this many relationships, counted apart from connections.
MAX_RELATIONSHIPS_PER_LIBRARY = 20_000
#: A list read takes at most this many ids for either end.
MAX_END_IDS = 100


async def require_relationship_room(
    session: AsyncSession, *, tenant_id: uuid.UUID, adding: int = 1
) -> None:
    """Refuses relationships beyond the library's limit: `adding` more than there are now."""
    count = await session.scalar(
        select(func.count()).select_from(Relationship).where(Relationship.tenant_id == tenant_id)
    )
    if (count or 0) + adding > MAX_RELATIONSHIPS_PER_LIBRARY:
        raise InvalidRelationshipError(
            detail=f"A library holds at most {MAX_RELATIONSHIPS_PER_LIBRARY:,} relationships"
        )


async def touch_relationship(
    session: AsyncSession, *, tenant_id: uuid.UUID, relationship_id: uuid.UUID, user_id: uuid.UUID
) -> Entity:
    """Moves the relationship entry's `updated_at`, and so its `ETag`."""
    await session.execute(
        update(Entity)
        .where(Entity.id == relationship_id, Entity.tenant_id == tenant_id)
        .values(updated_at=func.now(), updated_by=user_id)
    )
    entity = await session.scalar(
        select(Entity)
        .where(Entity.id == relationship_id, Entity.tenant_id == tenant_id)
        .execution_options(populate_existing=True)
    )
    assert entity is not None
    return entity
