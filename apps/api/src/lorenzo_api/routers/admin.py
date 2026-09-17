import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import cast

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import or_, select

from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    require_platform_operator_role,
)
from lorenzo_api.exceptions import UserNotFoundError
from lorenzo_api.models import Tenant, User
from lorenzo_api.notifications import create_platform_notification
from lorenzo_api.schemas.admin import AdminUserOut, SuspendUserRequest
from lorenzo_api.schemas.notifications import AdminNotificationCreate, NotificationOut
from lorenzo_api.schemas.tenants import TenantOut

# See ADR 0057 - a platform-wide capability orthogonal to tenant
# membership entirely, gated by a role no tenant-scoped Membership row can
# grant. Every route below needs it and none read its return value, the
# same router-level-dependency shape campaigns.py's own get_tenant_or_404
# already uses.
router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require_platform_operator_role)]
)


@router.get("/tenants")
async def list_all_tenants(session: SessionDep, params: ParamsDep) -> Page[TenantOut]:
    """Every tenant on the platform, no membership filter - unlike
    GET /tenants (ADR 0030), which is scoped to the caller's own
    relationships. See ADR 0057.
    """
    stmt = select(Tenant).order_by(Tenant.name, Tenant.id)
    page: Page[TenantOut] = await apaginate(session, stmt, params)
    return page


@router.get("/users")
async def list_all_users(
    session: SessionDep, params: ParamsDep, q: str | None = None
) -> Page[AdminUserOut]:
    """A real browse/search - `q` (optional) does a case-insensitive
    substring match against nickname/email, unlike ADR 0055's deliberately
    exact-match, no-search public lookup. Safe to widen here: this sits
    behind the platform-operator role, not open to any authenticated user.
    """
    stmt = select(User).order_by(User.created_at, User.id)
    if q is not None:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(User.nickname.ilike(pattern), User.email.ilike(pattern)))

    def _users_out(users: Sequence[User]) -> list[AdminUserOut]:
        return [AdminUserOut.from_user(u) for u in users]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise exact.
    return cast(Page[AdminUserOut], await apaginate(session, stmt, params, transformer=_users_out))


@router.put("/users/{user_id}/suspend")
async def suspend_user(
    user_id: uuid.UUID, body: SuspendUserRequest, session: SessionDep, user: CurrentUser
) -> AdminUserOut:
    """Idempotent - re-suspending an already-suspended account updates the
    reason/operator but doesn't error, mirroring `grant_campaign_gm`'s own
    idempotent-PUT precedent. See ADR 0057: the target's *next* request,
    anywhere in the API, is rejected by `dependencies.get_current_user`.
    """
    target = await session.get(User, user_id)
    if target is None:
        raise UserNotFoundError(detail=f"No user with id {user_id}")

    target.suspended_at = datetime.now(tz=UTC)
    target.suspended_by = user.id
    target.suspension_reason = body.reason
    await session.commit()
    return AdminUserOut.from_user(target)


@router.delete("/users/{user_id}/suspend")
async def unsuspend_user(user_id: uuid.UUID, session: SessionDep) -> AdminUserOut:
    """No-op (still 200), not 404, if the account wasn't suspended -
    matches DELETE's own general idempotency expectation."""
    target = await session.get(User, user_id)
    if target is None:
        raise UserNotFoundError(detail=f"No user with id {user_id}")

    target.suspended_at = None
    target.suspended_by = None
    target.suspension_reason = None
    await session.commit()
    return AdminUserOut.from_user(target)


@router.post("/notifications", status_code=201)
async def create_platform_notification_route(
    body: AdminNotificationCreate, session: SessionDep, user: CurrentUser
) -> NotificationOut:
    """scope="platform" - see ADR 0058. `recipient_user_id` is required
    here (`AdminNotificationCreate`'s own narrowing) - no
    broadcast-to-every-user mechanism exists yet.
    """
    if await session.get(User, body.recipient_user_id) is None:
        raise UserNotFoundError(detail=f"No user with id {body.recipient_user_id}")

    notification = create_platform_notification(
        recipient_user_id=body.recipient_user_id,
        type=body.type,
        title=body.title,
        body=body.body,
        created_by=user.id,
    )
    session.add(notification)
    await session.commit()
    return NotificationOut.model_validate(notification)
