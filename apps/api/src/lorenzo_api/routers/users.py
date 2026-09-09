from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import CurrentUser, SessionDep
from lorenzo_api.models import User
from lorenzo_api.schemas.users import MeOut

router = APIRouter(tags=["users"])


@router.get("/me")
async def get_me(user: CurrentUser, session: SessionDep) -> MeOut:
    """Proves the whole token-verification pipeline end to end over real
    HTTP - see ADR 0023. Not nested under /tenants/{tenant_id}/... - this
    is about the caller's own identity across every tenant they belong to,
    not scoped to one.

    Re-fetched with memberships eager-loaded rather than reusing the
    `user` CurrentUser resolved - that one only ever needs `.id` itself
    (get_tenant_context's Membership lookup), so eager-loading memberships
    on every authenticated request regardless of whether a route needs
    them would be wasted work.
    """
    stmt = select(User).where(User.id == user.id).options(selectinload(User.memberships))
    full_user = (await session.execute(stmt)).scalar_one()
    return MeOut.from_user(full_user)
