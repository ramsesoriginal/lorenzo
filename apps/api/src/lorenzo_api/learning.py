"""Deletion guards shared by Information, entries and participation."""

import uuid

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import EntityKindInUseError
from lorenzo_api.models import Entity, EventLearning, Information


async def require_no_learning(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    information_id: uuid.UUID | None = None,
    entity_id: uuid.UUID | None = None,
    event_id: uuid.UUID | None = None,
    being_id: uuid.UUID | None = None,
) -> None:
    query = select(exists().where(EventLearning.tenant_id == tenant_id))
    if information_id is not None:
        query = select(
            exists().where(
                EventLearning.tenant_id == tenant_id, EventLearning.information_id == information_id
            )
        )
    if entity_id is not None:
        await session.execute(
            select(Entity.id)
            .where(Entity.tenant_id == tenant_id, Entity.id == entity_id)
            .with_for_update()
        )
        query = select(
            exists().where(
                EventLearning.tenant_id == tenant_id,
                EventLearning.information_id.in_(
                    select(Information.id).where(
                        Information.tenant_id == tenant_id, Information.entity_id == entity_id
                    )
                ),
            )
        )
    if event_id is not None and being_id is not None:
        query = select(
            exists().where(
                EventLearning.tenant_id == tenant_id,
                EventLearning.event_entity_id == event_id,
                EventLearning.being_entity_id == being_id,
            )
        )
    if event_id is not None and being_id is not None:
        from sqlalchemy import or_

        from lorenzo_api.models import LivedBefore

        if await session.scalar(
            select(
                exists().where(
                    LivedBefore.tenant_id == tenant_id,
                    LivedBefore.being_entity_id == being_id,
                    or_(LivedBefore.from_event_id == event_id, LivedBefore.to_event_id == event_id),
                )
            )
        ):
            raise EntityKindInUseError(
                detail="This entry has references that prevent deletion or kind removal."
            )
    if await session.scalar(query):
        raise EntityKindInUseError(
            detail="This entry has references that prevent deletion or kind removal."
        )
