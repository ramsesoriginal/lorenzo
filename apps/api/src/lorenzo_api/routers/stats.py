from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from lorenzo_api.dependencies import SessionDep, get_tenant_context
from lorenzo_api.exceptions import (
    InvalidStatGroupError,
    StatDefinitionNotFoundError,
    StatGroupNotFoundError,
)
from lorenzo_api.models import StatDefinition, StatGroup
from lorenzo_api.schemas.stats import (
    StatDefinitionCreate,
    StatDefinitionOut,
    StatGroupCreate,
    StatGroupOut,
)

# get_tenant_context here, not per-route (ADR 0020's revised guidance,
# matching routers/items.py's identical precedent) - every route on this
# router needs it and none read its return value. stat_group/stat_definition
# are the shared stat vocabulary ("physical," "weight," ...), the same kind
# of tenant-admin-authored catalog concern as item's own prototypes
# (ADR 0032/ADR 0037, RFC 0008).
router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["stats"],
    dependencies=[Depends(get_tenant_context)],
)


async def _get_stat_group_or_404(
    tenant_id: uuid.UUID, stat_group_id: uuid.UUID, session: SessionDep
) -> StatGroup:
    stmt = select(StatGroup).where(StatGroup.id == stat_group_id, StatGroup.tenant_id == tenant_id)
    stat_group = (await session.execute(stmt)).scalar_one_or_none()
    if stat_group is None:
        raise StatGroupNotFoundError(
            detail=f"No stat group with id {stat_group_id} in tenant {tenant_id}"
        )
    return stat_group


async def _get_stat_definition_or_404(
    tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, session: SessionDep
) -> StatDefinition:
    stmt = select(StatDefinition).where(
        StatDefinition.id == stat_definition_id, StatDefinition.tenant_id == tenant_id
    )
    stat_definition = (await session.execute(stmt)).scalar_one_or_none()
    if stat_definition is None:
        raise StatDefinitionNotFoundError(
            detail=f"No stat definition with id {stat_definition_id} in tenant {tenant_id}"
        )
    return stat_definition


@router.post("/stat-groups", status_code=201)
async def create_stat_group(
    tenant_id: uuid.UUID,
    body: StatGroupCreate,
    request: Request,
    response: Response,
    session: SessionDep,
) -> StatGroupOut:
    """No post-commit re-read (unlike routers/items.py's create_item) - the
    response is built straight from the in-memory row create/committed just
    above, and async_session_factory's expire_on_commit=False (db.py) keeps
    its attributes readable without a fresh SELECT. Nothing here goes back
    through a security_invoker view after the commit, so
    dependencies.set_tenant_rls_context's "call it again after a mid-request
    commit" rule (ADR 0032) doesn't apply - it's only needed once a route
    actually re-queries.
    """
    stat_group = StatGroup(tenant_id=tenant_id, name=body.name, priority=body.priority)
    session.add(stat_group)
    await session.commit()
    response.headers["Location"] = str(
        request.url_for("get_stat_group", tenant_id=tenant_id, stat_group_id=stat_group.id)
    )
    return StatGroupOut.from_stat_group(stat_group)


@router.get("/stat-groups/{stat_group_id}")
async def get_stat_group(
    tenant_id: uuid.UUID, stat_group_id: uuid.UUID, session: SessionDep
) -> StatGroupOut:
    stat_group = await _get_stat_group_or_404(tenant_id, stat_group_id, session)
    return StatGroupOut.from_stat_group(stat_group)


@router.post("/stat-definitions", status_code=201)
async def create_stat_definition(
    tenant_id: uuid.UUID,
    body: StatDefinitionCreate,
    request: Request,
    response: Response,
    session: SessionDep,
) -> StatDefinitionOut:
    """stat_group_id must resolve to a stat group in this tenant (422
    InvalidStatGroupError otherwise) - mirrors create_item_instance's own
    prototype_id validation (ADR 0032).
    """
    stat_group_stmt = select(StatGroup.id).where(
        StatGroup.id == body.stat_group_id, StatGroup.tenant_id == tenant_id
    )
    if (await session.execute(stat_group_stmt)).first() is None:
        raise InvalidStatGroupError(
            detail=f"{body.stat_group_id} is not a stat group in tenant {tenant_id}"
        )

    stat_definition = StatDefinition(
        tenant_id=tenant_id,
        stat_group_id=body.stat_group_id,
        name=body.name,
        value_type=body.value_type,
    )
    session.add(stat_definition)
    await session.commit()
    response.headers["Location"] = str(
        request.url_for(
            "get_stat_definition", tenant_id=tenant_id, stat_definition_id=stat_definition.id
        )
    )
    return StatDefinitionOut.from_stat_definition(stat_definition)


@router.get("/stat-definitions/{stat_definition_id}")
async def get_stat_definition(
    tenant_id: uuid.UUID, stat_definition_id: uuid.UUID, session: SessionDep
) -> StatDefinitionOut:
    stat_definition = await _get_stat_definition_or_404(tenant_id, stat_definition_id, session)
    return StatDefinitionOut.from_stat_definition(stat_definition)
