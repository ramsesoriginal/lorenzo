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
    """An accountability timeline for tenant administrators: who changed
    what shape this tenant has, who can see or do what in it, and who
    holds what - by any actor, GMs included (ADR 0063/0084). What is
    recorded, and what is deliberately not, is ADR 0084's coverage rule;
    a mutation route either calls `activity_log.record_activity` or says
    in its own docstring why it doesn't.

    Gated by `get_tenant_context`. That means "OWNER or ORGA" only because
    every `MembershipRole` is administrative - GMs and players without a
    Membership row get a 404. `tests/test_activity_log_access.py` fails if
    a non-administrative role is ever added, at which point this gate must
    become an explicit `is_tenant_admin` check in the same change.
    """
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
    )
    page: Page[AuditLogEntryOut] = await apaginate(session, stmt, params)
    return page
