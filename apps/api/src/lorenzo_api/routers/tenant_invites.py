"""An Owner's invite links for their library or repository (ADR 0211): a role link, which makes
an Author or an Organizer, and a library-access link, which shares a repository with a library.

The campaign links are `routers/campaign_invites.py`; redeeming any of them is
`routers/invites.py`. Behind `get_tenant_context` and an Owner check: minting one hands over
a role or a grant, which adding a person or a grant already is only an Owner's to do.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import is_tenant_owner
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    InvalidInviteExpiryError,
    InviteManagementForbiddenError,
    InviteNotFoundError,
    NotARepositoryError,
)
from lorenzo_api.invites import (
    DEFAULT_LIBRARY_INVITE_LIFETIME,
    DEFAULT_ROLE_INVITE_LIFETIME,
    MAX_LIBRARY_INVITE_LIFETIME,
    MAX_ROLE_INVITE_LIFETIME,
    generate_token,
    hash_token,
)
from lorenzo_api.models import Invite, InviteKind, Tenant, TenantKind
from lorenzo_api.schemas.invites import InviteCreatedOut, InviteOut, TenantInviteCreate

router = APIRouter(
    prefix="/tenants/{tenant_id}/invites",
    tags=["tenant-invites"],
)


async def _require_owner(session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser) -> None:
    if not await is_tenant_owner(session, tenant_id=tenant_id, user_id=user.id):
        raise InviteManagementForbiddenError(
            detail=f"Only an owner of tenant {tenant_id} can make or revoke its invite links"
        )


def _lifetimes(kind: InviteKind) -> tuple[timedelta, timedelta]:
    """The default and the longest a link of this kind may live."""
    if kind is InviteKind.LIBRARY_ACCESS:
        return DEFAULT_LIBRARY_INVITE_LIFETIME, MAX_LIBRARY_INVITE_LIFETIME
    return DEFAULT_ROLE_INVITE_LIFETIME, MAX_ROLE_INVITE_LIFETIME


@router.post("", status_code=201)
async def create_tenant_invite(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    body: TenantInviteCreate,
    session: SessionDep,
    user: CurrentUser,
) -> InviteCreatedOut:
    """The only response that ever contains the token, shown once. An Owner's alone. A role
    link makes an Author or an Organizer, never an Owner; a library link, for a repository
    (`409` for a library), grants it to a library its redeemer owns. Always ends and is always
    capped: single use unless an Author or library link says more, up to a ceiling; the
    expiry defaults to 3 days for a role link and 7 for a library link, and may not be longer
    than 7 and 30 (ADR 0211).
    """
    await _require_owner(session, tenant_id=tenant_id, user=user)
    tenant = await session.get_one(Tenant, tenant_id)
    if body.kind is InviteKind.LIBRARY_ACCESS and tenant.kind is not TenantKind.REPOSITORY:
        raise NotARepositoryError(
            detail="A link that shares a repository is made for a repository, not a library."
        )

    now = datetime.now(tz=UTC)
    default_lifetime, longest = _lifetimes(body.kind)
    expires_at = body.expires_at or now + default_lifetime
    if expires_at <= now:
        raise InvalidInviteExpiryError(detail="expires_at must be in the future")
    if expires_at > now + longest:
        raise InvalidInviteExpiryError(
            detail=f"expires_at must be within {longest.days} days from now"
        )
    max_uses = body.max_uses or 1

    token = generate_token()
    invite = Invite(
        tenant_id=tenant_id,
        kind=body.kind,
        campaign_id=None,
        token_hash=hash_token(token),
        role=body.role,
        created_by=user.id,
        expires_at=expires_at,
        max_uses=max_uses,
    )
    session.add(invite)
    await session.flush()
    invite_id = invite.id
    # Never the token - the log is read by administrators, not by link holders.
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="invite.created",
        target_type="invite",
        target_id=invite_id,
        detail=(
            f"kind={body.kind.value}, "
            f"{f'role={body.role.value}, ' if body.role else ''}"
            f"expires_at={expires_at.isoformat()}, max_uses={max_uses}"
        ),
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    created = (
        await session.execute(
            select(Invite).where(Invite.id == invite_id, Invite.tenant_id == tenant_id)
        )
    ).scalar_one()
    return InviteCreatedOut(**InviteOut.from_invite(created, now=now).model_dump(), token=token)


@router.get("")
async def list_tenant_invites(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
) -> Page[InviteOut]:
    """This library's or repository's role and library links, newest first, with their use
    counts and never a token. An Owner's, like making them. A campaign's links are listed
    with the campaign."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    now = datetime.now(tz=UTC)
    stmt = (
        select(Invite)
        .where(Invite.tenant_id == tenant_id, Invite.kind != InviteKind.CAMPAIGN)
        .order_by(Invite.created_at.desc(), Invite.id)
    )
    page: Page[InviteOut] = await apaginate(
        session,
        stmt,
        params,
        transformer=lambda rows: [InviteOut.from_invite(row, now=now) for row in rows],
    )
    return page


@router.delete("/{invite_id}", status_code=204)
async def revoke_tenant_invite(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    invite_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """Instant, and idempotent: revoking an already-revoked link is a no-op (and writes no
    second activity entry). People who already used it keep what it gave them."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    invite = (
        await session.execute(
            select(Invite).where(
                Invite.id == invite_id,
                Invite.tenant_id == tenant_id,
                Invite.kind != InviteKind.CAMPAIGN,
            )
        )
    ).scalar_one_or_none()
    if invite is None:
        raise InviteNotFoundError(detail=f"No invite {invite_id} on tenant {tenant_id}")
    if invite.revoked_at is not None:
        return
    invite.revoked_at = datetime.now(tz=UTC)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="invite.revoked",
        target_type="invite",
        target_id=invite_id,
        detail=f"kind={invite.kind.value}",
    )
    await session.commit()
