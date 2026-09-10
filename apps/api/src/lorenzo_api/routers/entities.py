import uuid

from fastapi import APIRouter, Depends, Request
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import CurrentUser, ParamsDep, SessionDep, get_tenant_context
from lorenzo_api.exceptions import EntityNotFoundError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Entity, EntityStat, Information, Payload
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import EntityDetailOut

# get_tenant_context here, not per-route (ADR 0020's revised guidance) -
# every route on this router needs it and none read its return value, the
# textbook case FastAPI's own docs give for a router-level dependency.
router = APIRouter(
    prefix="/tenants/{tenant_id}/entities",
    tags=["entities"],
    dependencies=[Depends(get_tenant_context)],
)


@router.get("")
async def list_entities(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
) -> Page[EntitySummary]:
    """A lightweight listing - EntitySummary rather than EntityDetailOut, to
    avoid an N+1-heavy response when listing many entities.
    """
    stmt = select(Entity).where(Entity.tenant_id == tenant_id).order_by(Entity.name, Entity.id)
    page: Page[EntitySummary] = await apaginate(session, stmt, params)
    return page


@router.get("/{entity_id}")
async def get_entity(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> EntityDetailOut:
    """The full detail shape, with every relationship eager-loaded up front.

    Queried directly with the full .options() chain rather than delegating
    to dependencies.get_entity_or_404 first - that helper's plain
    session.get() wouldn't have any of these relationships loaded, so
    reusing it here would just mean a second, redundant round trip for
    this same row. The 404 check below covers exactly what that helper
    covers (missing id, or an id that belongs to a different tenant).
    """
    stmt = (
        select(Entity)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .options(
            selectinload(Entity.stats).selectinload(EntityStat.stat_definition),
            selectinload(Entity.stat_groups),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.description),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.number),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.picture),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .selectinload(Payload.document),
            selectinload(Entity.information).selectinload(Information.knowledge_links),
            selectinload(Entity.prototypes),
            selectinload(Entity.instances),
            selectinload(Entity.parent),
            selectinload(Entity.children),
        )
    )
    entity = await session.scalar(stmt)
    if entity is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")

    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return EntityDetailOut.from_entity(entity, request, visibility=visibility)
