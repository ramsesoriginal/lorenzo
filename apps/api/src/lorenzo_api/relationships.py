"""What the relationship routes share: the library limit and touching a relationship (ADR 0399).

The rule that a relationship is read only with both its ends lives in `entry_visibility`, in the
clause every entry read applies, so nothing here has to repeat it."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text, update
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


#: A relationship holds through at most this many others (ADR 0402, *proposed default*).
MAX_THROUGH_STEPS = 12
#: Readers of a chain stop here, so a cycle that arrived through a repository ends it quietly.
MAX_THROUGH_DEPTH = 64


async def lock_through(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """Serialises the writes of every chain in a library, so two that would close a cycle between
    them cannot both pass the check (ADR 0402)."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('lorenzo:through:' || :tenant, 0))"),
        {"tenant": str(tenant_id)},
    )


async def through_reaches(
    session: AsyncSession, *, tenant_id: uuid.UUID, start: uuid.UUID, target: uuid.UUID
) -> bool:
    """Whether `target` is among the relationships `start` holds through, directly or by a longer
    path. A recursive walk with a path guard and a depth cap."""
    row = await session.execute(
        text(
            """
            WITH RECURSIVE walk(via, path, depth) AS (
              SELECT via_entity_id, ARRAY[relationship_entity_id, via_entity_id], 1
              FROM relationship_through
              WHERE tenant_id = :tenant AND relationship_entity_id = :start
              UNION ALL
              SELECT t.via_entity_id, walk.path || t.via_entity_id, walk.depth + 1
              FROM relationship_through t JOIN walk ON t.relationship_entity_id = walk.via
              WHERE t.tenant_id = :tenant AND NOT t.via_entity_id = ANY(walk.path)
                AND walk.depth < :depth
            )
            SELECT EXISTS (SELECT 1 FROM walk WHERE via = :target)
            """
        ),
        {
            "tenant": tenant_id,
            "start": start,
            "target": target,
            "depth": MAX_THROUGH_DEPTH,
        },
    )
    return bool(row.scalar())
