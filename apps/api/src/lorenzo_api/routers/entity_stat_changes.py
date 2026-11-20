"""The History of a being's sheet: its latest stat changes and who made them (ADR 0525)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_or_404
from lorenzo_api.models import EntityStatChange, StatDefinition, User
from lorenzo_api.routers.entities import entity_detail_out
from lorenzo_api.schemas.entity_stat_changes import EntityStatChangeOut

router = APIRouter(
    prefix="/tenants/{tenant_id}/entities/{entity_id}",
    tags=["entity-stats"],
    dependencies=[Depends(get_tenant_or_404)],
)


@router.get("/stat-changes")
async def list_stat_changes(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=EntityStatChange.KEEP)] = 30,
) -> list[EntityStatChangeOut]:
    """The entry's latest own-stat changes, newest first (ADR 0525, BN9).

    The gate is `GET /{entity_id}`'s own (404 for an entry the caller cannot see): whoever may read
    the entry's stats may read how they changed. Bounded: the latest `EntityStatChange.KEEP` are
    kept, 30 are returned by default.
    """
    await entity_detail_out(session, request, tenant_id=tenant_id, entity_id=entity_id, user=user)
    rows = await session.execute(
        select(EntityStatChange, StatDefinition.name, User.nickname, User.display_name)
        .join(StatDefinition, StatDefinition.id == EntityStatChange.stat_definition_id)
        .outerjoin(User, User.id == EntityStatChange.actor_id)
        .where(EntityStatChange.entity_id == entity_id)
        .order_by(EntityStatChange.created_at.desc(), EntityStatChange.id.desc())
        .limit(limit)
    )
    return [
        EntityStatChangeOut(
            id=change.id,
            stat_definition_id=change.stat_definition_id,
            stat_name=name,
            old=change.old_value,
            new=change.new_value,
            actor_id=change.actor_id,
            actor_name=nickname or display_name,
            created_at=change.created_at,
        )
        for change, name, nickname, display_name in rows.all()
    ]
