import uuid

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import CurrentUser, SessionDep, set_tenant_rls_context
from lorenzo_api.exceptions import InviteNotFoundError
from lorenzo_api.invites import consume_invite, find_live_invite
from lorenzo_api.models import Campaign, CampaignGm, CampaignProfilePicture, InviteRole, Player
from lorenzo_api.notifications import notify_campaign_gms
from lorenzo_api.rate_limit import enforce_invite_rate_limit, request_source
from lorenzo_api.schemas.invites import InvitePreviewOut, InviteRedeemOut

# Both routes are reachable by anyone on the internet, so both sit behind
# the in-process rate-limit backstop (ADR 0092) - the edge rule is the real
# control, see docs/operations/invite-link-rate-limiting.md.
router = APIRouter(tags=["invites"], dependencies=[Depends(enforce_invite_rate_limit)])

log = structlog.get_logger()

# One fixed message for every reason a link can fail. Never the token.
_NOT_VALID = "This invite link is not valid."


def _reject(request: Request, *, endpoint: str) -> InviteNotFoundError:
    """The single 404 for an unknown, expired, revoked or exhausted token
    (ADR 0092) - identical whatever the reason, so a response can't tell an
    attacker a token was once real. The reason *class* is deliberately not
    logged either: the token is not in the request path a log ever sees
    (see the redaction test), and a probe shows up as a rate of these
    events from one source, which is all an operator needs.
    """
    log.warning("invite_link_rejected", endpoint=endpoint, source=request_source(request))
    return InviteNotFoundError(detail=_NOT_VALID)


@router.get("/invites/{token}")
async def preview_invite(token: str, request: Request, session: SessionDep) -> InvitePreviewOut:
    """Unauthenticated - the campaign's name and picture URL, so a landing
    page can say what the visitor is being invited to (ADR 0092) - as a
    player, or as a GM (ADR 0177). Does an indexed read and never writes.
    """
    invite = await find_live_invite(session, token)
    if invite is None:
        raise _reject(request, endpoint="preview")
    tenant_id, campaign_id, role = invite.tenant_id, invite.campaign_id, invite.role
    await set_tenant_rls_context(session, tenant_id)

    campaign_name = (
        await session.execute(
            select(Campaign.name).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
        )
    ).scalar_one()
    has_picture = (
        await session.execute(
            select(CampaignProfilePicture.campaign_id).where(
                CampaignProfilePicture.campaign_id == campaign_id
            )
        )
    ).first() is not None
    picture_url = (
        str(request.url_for("get_campaign_picture", tenant_id=tenant_id, campaign_id=campaign_id))
        if has_picture
        else None
    )
    return InvitePreviewOut(campaign_name=campaign_name, picture_url=picture_url, role=role)


async def _redeem_gm_link(
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    invite_id: uuid.UUID,
    granted_by: uuid.UUID | None,
) -> InviteRedeemOut:
    """A GM link's redemption (ADR 0177): a `CampaignGm` row, never a
    player row and never a tenant membership, attributed to whoever made the
    link as `PUT .../gms/{user}` attributes to its granter. Someone already a
    GM of the campaign gets `200` and no use is spent.
    """
    if await session.get(CampaignGm, (tenant_id, user.id, campaign_id)) is not None:
        response.status_code = 200
        return InviteRedeemOut(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            role=InviteRole.GM,
            player_id=None,
            already_joined=True,
        )

    # The atomic spend, which is what makes a single-use link one person.
    if not await consume_invite(session, invite_id):
        raise _reject(request, endpoint="redeem")

    # The GMs to tell are the ones there before this one joins.
    gm_user_ids = set(
        (
            await session.execute(
                select(CampaignGm.user_id).where(
                    CampaignGm.campaign_id == campaign_id, CampaignGm.tenant_id == tenant_id
                )
            )
        ).scalars()
    )
    session.add(
        CampaignGm(
            tenant_id=tenant_id, user_id=user.id, campaign_id=campaign_id, created_by=granted_by
        )
    )
    campaign_name = (
        await session.execute(
            select(Campaign.name).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
        )
    ).scalar_one()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="campaign_invite.redeemed",
        target_type="campaign_invite",
        target_id=invite_id,
        detail=f"campaign={campaign_id}, role=gm, gm={user.id}",
    )
    who = user.display_name or user.nickname or "Someone"
    notify_campaign_gms(
        session,
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        gm_user_ids=gm_user_ids,
        type="campaign_invite_gm_redeemed",
        title=f"A new GM joined {campaign_name}",
        body=f"{who} joined as a GM through an invite link.",
        created_by=user.id,
    )
    await session.commit()
    return InviteRedeemOut(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        role=InviteRole.GM,
        player_id=None,
        already_joined=False,
    )


@router.post("/invites/{token}/redeem", status_code=201)
async def redeem_invite(
    token: str,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> InviteRedeemOut:
    """Authenticated but not tenant-scoped: any verified Authgear user
    (ADR 0092) - joining creates a `player` row, which needs a user. Gives
    the player role in this one campaign and nothing more; never tenant
    membership. A GM link (ADR 0177) gives a GM row instead, and no player
    row. Idempotent: someone who already holds the role gets `200` and no
    second seat, no use consumed. `201` the first time.
    """
    invite = await find_live_invite(session, token)
    if invite is None:
        raise _reject(request, endpoint="redeem")
    tenant_id, campaign_id, invite_id = invite.tenant_id, invite.campaign_id, invite.id
    role, granted_by = invite.role, invite.created_by
    await set_tenant_rls_context(session, tenant_id)

    if role is InviteRole.GM:
        return await _redeem_gm_link(
            request,
            response,
            session,
            user,
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            invite_id=invite_id,
            granted_by=granted_by,
        )

    existing_player_id = (
        await session.execute(
            select(Player.id).where(Player.campaign_id == campaign_id, Player.user_id == user.id)
        )
    ).scalar_one_or_none()
    if existing_player_id is not None:
        response.status_code = 200
        return InviteRedeemOut(
            tenant_id=tenant_id,
            campaign_id=campaign_id,
            role=InviteRole.PLAYER,
            player_id=existing_player_id,
            already_joined=True,
        )

    # The atomic spend: if the link ran out or was revoked between the
    # lookup above and now, this loses the race and the caller sees the same
    # 404 as any other dead link.
    if not await consume_invite(session, invite_id):
        raise _reject(request, endpoint="redeem")

    player = Player(
        user_id=user.id,
        campaign_id=campaign_id,
        tenant_id=tenant_id,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(player)
    await session.flush()
    player_id = player.id

    campaign_name = (
        await session.execute(
            select(Campaign.name).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
        )
    ).scalar_one()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="campaign_invite.redeemed",
        target_type="campaign_invite",
        target_id=invite_id,
        detail=f"campaign={campaign_id}, player={player_id}",
    )
    gm_user_ids = set(
        (
            await session.execute(
                select(CampaignGm.user_id).where(
                    CampaignGm.campaign_id == campaign_id, CampaignGm.tenant_id == tenant_id
                )
            )
        ).scalars()
    )
    who = user.display_name or user.nickname or "Someone"
    notify_campaign_gms(
        session,
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        gm_user_ids=gm_user_ids,
        type="campaign_invite_redeemed",
        title=f"A new player joined {campaign_name}",
        body=f"{who} joined through an invite link.",
        created_by=user.id,
    )
    await session.commit()
    return InviteRedeemOut(
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        role=InviteRole.PLAYER,
        player_id=player_id,
        already_joined=False,
    )
