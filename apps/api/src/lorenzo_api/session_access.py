"""Explicit Session scope, independent of library-wide Event standing (ADR 0317)."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    CampaignGm,
    Player,
    SceneAppearance,
    SessionGm,
    SessionPlayer,
    StorySession,
)


@dataclass(frozen=True)
class SessionScope:
    entries: frozenset[uuid.UUID]
    readers: frozenset[uuid.UUID]
    managers: frozenset[uuid.UUID]


async def session_scope(
    session: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> SessionScope:
    sessions = list(
        await session.scalars(select(StorySession).where(StorySession.tenant_id == tenant_id))
    )
    gm_campaigns = set(
        await session.scalars(
            select(CampaignGm.campaign_id).where(
                CampaignGm.tenant_id == tenant_id, CampaignGm.user_id == user_id
            )
        )
    )
    assignments = set(
        await session.scalars(
            select(SessionGm.session_entity_id).where(
                SessionGm.tenant_id == tenant_id, SessionGm.user_id == user_id
            )
        )
    )
    managers = {
        row.entity_id
        for row in sessions
        if row.entity_id in assignments and row.campaign_id in gm_campaigns
    }
    readers = (
        set(
            await session.scalars(
                select(SessionPlayer.session_entity_id)
                .join(Player, Player.id == SessionPlayer.player_id)
                .where(SessionPlayer.tenant_id == tenant_id, Player.user_id == user_id)
            )
        )
        | managers
    )
    appearances = list(
        await session.scalars(select(SceneAppearance).where(SceneAppearance.tenant_id == tenant_id))
    )
    return SessionScope(
        frozenset({row.entity_id for row in sessions} | {row.entity_id for row in appearances}),
        frozenset(
            readers
            | {
                row.entity_id
                for row in appearances
                if row.session_entity_id in readers
                and (row.is_shared or row.session_entity_id in managers)
            }
        ),
        frozenset(
            managers | {row.entity_id for row in appearances if row.session_entity_id in managers}
        ),
    )


async def planning_entry(session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> bool:
    cache = session.info.setdefault("planning_entry_checks", {})
    key = (tenant_id, entity_id)
    if key not in cache:
        cache[key] = (
            await session.scalar(
                union_all(
                    select(StorySession.entity_id).where(
                        StorySession.tenant_id == tenant_id, StorySession.entity_id == entity_id
                    ),
                    select(SceneAppearance.entity_id).where(
                        SceneAppearance.tenant_id == tenant_id,
                        SceneAppearance.entity_id == entity_id,
                    ),
                )
            )
            is not None
        )
    return bool(cache[key])


async def manages_planning_entry(
    session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    from lorenzo_api.information_visibility import _administrative_tier

    if (await _administrative_tier(session, user_id=user_id, tenant_id=tenant_id))[1]:
        return True
    return entity_id in (await session_scope(session, tenant_id, user_id)).managers
