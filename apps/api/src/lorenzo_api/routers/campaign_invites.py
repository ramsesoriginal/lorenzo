import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import can_access_campaign, can_manage_campaign
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    CampaignManagementForbiddenError,
    CampaignNotFoundError,
    InvalidInviteExpiryError,
    InviteNotFoundError,
)
from lorenzo_api.invites import MAX_INVITE_LIFETIME, generate_token, hash_token
from lorenzo_api.models import Campaign, CampaignInvite
from lorenzo_api.schemas.invites import InviteCreate, InviteCreatedOut, InviteOut

# get_tenant_or_404, not get_tenant_context: a campaign's GM may hold no
# tenant-wide Membership at all (ADR 0022), and managing a campaign's invite
# links is a campaign-management concern - each route runs its own explicit
# can_manage_campaign check, the pair routers/campaigns.py already uses.
router = APIRouter(
    prefix="/tenants/{tenant_id}/campaigns/{campaign_id}/invites",
    tags=["campaign-invites"],
    dependencies=[Depends(get_tenant_or_404)],
)


async def _require_manageable_campaign(
    session: SessionDep, *, tenant_id: uuid.UUID, campaign_id: uuid.UUID, user: CurrentUser
) -> None:
    """404 for "no relationship to this campaign at all" (existence hidden),
    403 for "can see it, may not manage it" - ADR 0032's split.
    """
    exists = select(Campaign.id).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
    not_found = CampaignNotFoundError(
        detail=f"No campaign with id {campaign_id} in tenant {tenant_id}"
    )
    if (await session.execute(exists)).first() is None:
        raise not_found
    if not await can_access_campaign(
        session, user_id=user.id, campaign_id=campaign_id, tenant_id=tenant_id
    ):
        raise not_found
    if not await can_manage_campaign(
        session, user_id=user.id, campaign_id=campaign_id, tenant_id=tenant_id
    ):
        raise CampaignManagementForbiddenError(
            detail=f"Not authorized to manage campaign {campaign_id}"
        )


def _invite_out(invite: CampaignInvite, *, now: datetime) -> InviteOut:
    is_active = (
        invite.revoked_at is None
        and invite.expires_at > now
        and (invite.max_uses is None or invite.use_count < invite.max_uses)
    )
    return InviteOut(
        id=invite.id,
        campaign_id=invite.campaign_id,
        created_by=invite.created_by,
        created_at=invite.created_at,
        expires_at=invite.expires_at,
        max_uses=invite.max_uses,
        use_count=invite.use_count,
        revoked_at=invite.revoked_at,
        is_active=is_active,
    )


@router.post("", status_code=201)
async def create_invite(
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    body: InviteCreate,
    session: SessionDep,
    user: CurrentUser,
) -> InviteCreatedOut:
    """The only response that ever contains the token - shown once, and
    unrecoverable afterwards, since only its hash is stored (ADR 0092).
    `expires_at` must be in the future and at most 30 days out.
    """
    await _require_manageable_campaign(
        session, tenant_id=tenant_id, campaign_id=campaign_id, user=user
    )
    now = datetime.now(tz=UTC)
    if body.expires_at <= now:
        raise InvalidInviteExpiryError(detail="expires_at must be in the future")
    if body.expires_at > now + MAX_INVITE_LIFETIME:
        raise InvalidInviteExpiryError(
            detail=f"expires_at must be within {MAX_INVITE_LIFETIME.days} days from now"
        )

    token = generate_token()
    invite = CampaignInvite(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        token_hash=hash_token(token),
        created_by=user.id,
        expires_at=body.expires_at,
        max_uses=body.max_uses,
    )
    session.add(invite)
    await session.flush()
    invite_id = invite.id
    # Never the token - the log is read by administrators, not by link holders.
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="campaign_invite.created",
        target_type="campaign_invite",
        target_id=invite_id,
        detail=(
            f"campaign={campaign_id}, expires_at={body.expires_at.isoformat()}, "
            f"max_uses={body.max_uses if body.max_uses is not None else 'unlimited'}"
        ),
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    created = (
        await session.execute(
            select(CampaignInvite).where(
                CampaignInvite.id == invite_id, CampaignInvite.tenant_id == tenant_id
            )
        )
    ).scalar_one()
    return InviteCreatedOut(**_invite_out(created, now=now).model_dump(), token=token)


@router.get("")
async def list_invites(
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
) -> Page[InviteOut]:
    """Metadata and use counts, newest first - never a token."""
    await _require_manageable_campaign(
        session, tenant_id=tenant_id, campaign_id=campaign_id, user=user
    )
    now = datetime.now(tz=UTC)
    stmt = (
        select(CampaignInvite)
        .where(CampaignInvite.campaign_id == campaign_id, CampaignInvite.tenant_id == tenant_id)
        .order_by(CampaignInvite.created_at.desc(), CampaignInvite.id)
    )
    page: Page[InviteOut] = await apaginate(
        session,
        stmt,
        params,
        transformer=lambda rows: [_invite_out(row, now=now) for row in rows],
    )
    return page


@router.delete("/{invite_id}", status_code=204)
async def revoke_invite(
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    invite_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """Instant, and idempotent: revoking an already-revoked link is a no-op
    (and writes no second activity entry).
    """
    await _require_manageable_campaign(
        session, tenant_id=tenant_id, campaign_id=campaign_id, user=user
    )
    invite = (
        await session.execute(
            select(CampaignInvite).where(
                CampaignInvite.id == invite_id,
                CampaignInvite.campaign_id == campaign_id,
                CampaignInvite.tenant_id == tenant_id,
            )
        )
    ).scalar_one_or_none()
    if invite is None:
        raise InviteNotFoundError(detail=f"No invite {invite_id} on campaign {campaign_id}")
    if invite.revoked_at is not None:
        return
    invite.revoked_at = datetime.now(tz=UTC)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="campaign_invite.revoked",
        target_type="campaign_invite",
        target_id=invite_id,
        detail=f"campaign={campaign_id}",
    )
    await session.commit()
