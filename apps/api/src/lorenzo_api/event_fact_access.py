"""Event/Fact collaboration standing, distinct from general tenant administration (ADR 0316)."""

from __future__ import annotations

import uuid

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.campaign_access import is_tenant_author, is_tenant_gm, is_tenant_participant
from lorenzo_api.models import Entity, Fact, StoryEvent, TenantAdminCampaignOptOut


async def manages_events(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    if (
        await session.scalar(
            select(TenantAdminCampaignOptOut.campaign_id)
            .where(
                TenantAdminCampaignOptOut.tenant_id == tenant_id,
                TenantAdminCampaignOptOut.user_id == user_id,
            )
            .limit(1)
        )
        is not None
    ):
        return False
    return await is_tenant_author(
        session, tenant_id=tenant_id, user_id=user_id
    ) or await is_tenant_gm(session, tenant_id=tenant_id, user_id=user_id)


async def is_event_fact(
    session: AsyncSession, *, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> bool:
    return bool(
        await session.scalar(
            select(Entity.id).where(
                Entity.id == entity_id,
                Entity.tenant_id == tenant_id,
                or_(
                    exists().where(Fact.entity_id == Entity.id),
                    exists().where(StoryEvent.entity_id == Entity.id),
                ),
            )
        )
    )


async def edits_event_fact(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID, entity_id: uuid.UUID
) -> bool:
    if not await is_tenant_participant(
        session, tenant_id=tenant_id, user_id=user_id
    ) or not await is_event_fact(session, tenant_id=tenant_id, entity_id=entity_id):
        return False
    return (
        await manages_events(session, tenant_id=tenant_id, user_id=user_id)
        or await session.scalar(
            select(Entity.id).where(
                Entity.id == entity_id, Entity.tenant_id == tenant_id, Entity.created_by == user_id
            )
        )
        is not None
    )
