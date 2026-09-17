import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from lorenzo_api.dependencies import ParamsDep, SessionDep, get_tenant_context
from lorenzo_api.models import AuditLog
from lorenzo_api.schemas.activity_log import AuditLogEntryOut

router = APIRouter(prefix="/tenants/{tenant_id}/activity-log", tags=["activity-log"])


@router.get("")
async def list_activity_log(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    params: ParamsDep,
) -> Page[AuditLogEntryOut]:
    """See ADR 0059 - a first, deliberately narrow slice: only membership
    and campaign/GM lifecycle events are logged (`lorenzo_api.
    activity_log.record_activity`'s own call sites), not an exhaustive
    record of every mutation in the API. Gated by `get_tenant_context`,
    the same bar `list_tenant_roster` already uses - any tenant-wide
    member, not OWNER-only.
    """
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
    )
    page: Page[AuditLogEntryOut] = await apaginate(session, stmt, params)
    return page
