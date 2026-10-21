import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from lorenzo_api.dependencies import CurrentUser, ParamsDep, SessionDep, get_tenant_admin_context
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import AuditLog
from lorenzo_api.schemas.activity_log import AuditLogEntryOut

router = APIRouter(prefix="/tenants/{tenant_id}/activity-log", tags=["activity-log"])


@router.get("")
async def list_activity_log(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_admin_context)],
    session: SessionDep,
    params: ParamsDep,
    user: CurrentUser,
) -> Page[AuditLogEntryOut]:
    """An accountability timeline for tenant administrators: who changed
    what shape this tenant has, who can see or do what in it, and who
    holds what - by any actor, GMs included (ADR 0063/0084). What is
    recorded, and what is deliberately not, is ADR 0084's coverage rule;
    a mutation route either calls `activity_log.record_activity` or says
    in its own docstring why it doesn't.

    Gated by `get_tenant_admin_context`: an OWNER or an ORGA. An AUTHOR (RFC 0040,
    ADR 0219) is a member and gets a 403; GMs and players without a Membership row
    get a 404.
    """
    stmt = (
        select(AuditLog)
        .where(AuditLog.tenant_id == tenant_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id)
    )
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    if not visibility.is_admin:
        # Filter before pagination: even the presence/count of an assertion is restricted.
        stmt = stmt.where(
            AuditLog.action.not_in(
                [
                    "event.relationship_added",
                    "event.relationship_removed",
                    "event.relationship_sharing_changed",
                    "event.participant_added",
                    "event.participant_removed",
                    "event.learning_recorded",
                    "event.learning_removed",
                ]
            )
        )
    page: Page[AuditLogEntryOut] = await apaginate(session, stmt, params)
    return page
