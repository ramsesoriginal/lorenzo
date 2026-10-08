import uuid

import structlog
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import CurrentUser, SessionDep, set_tenant_rls_context
from lorenzo_api.exceptions import (
    InvalidInviteLibraryError,
    InviteLibraryRequiredError,
    InviteNotFoundError,
)
from lorenzo_api.invites import consume_invite, find_live_invite
from lorenzo_api.models import (
    Campaign,
    CampaignGm,
    CampaignProfilePicture,
    Invite,
    InviteKind,
    InviteRole,
    Membership,
    MembershipRole,
    Player,
    RepositorySubscription,
    Tenant,
    TenantKind,
    TenantProfilePicture,
)
from lorenzo_api.notifications import create_tenant_owners_notification, notify_campaign_gms
from lorenzo_api.rate_limit import enforce_invite_rate_limit, request_source
from lorenzo_api.repository_grants import grant_repository_access
from lorenzo_api.role_names import role_phrase, tenant_word
from lorenzo_api.schemas.invites import InvitePreviewOut, InviteRedeemIn, InviteRedeemOut

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
    """Unauthenticated - what the visitor is about to be asked, so a landing page can say so
    before they log in (ADR 0092, 0211): for a campaign link the campaign's name and picture
    URL, as a player or as a GM (ADR 0177); for a role link the library's or repository's name
    and picture and the role, Author or Organizer; for a library link the repository's name and
    picture. Nothing else: no ids but those in a picture's address, no roster, no members. Does
    an indexed read and never writes, and a dead link is the same 404 whatever the kind.
    """
    invite = await find_live_invite(session, token)
    if invite is None:
        raise _reject(request, endpoint="preview")
    tenant_id, campaign_id, role, kind = (
        invite.tenant_id,
        invite.campaign_id,
        invite.role,
        invite.kind,
    )
    await set_tenant_rls_context(session, tenant_id)

    if kind is InviteKind.CAMPAIGN and campaign_id is not None:
        campaign_name = (
            await session.execute(
                select(Campaign.name).where(
                    Campaign.id == campaign_id, Campaign.tenant_id == tenant_id
                )
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
            str(
                request.url_for(
                    "get_campaign_picture", tenant_id=tenant_id, campaign_id=campaign_id
                )
            )
            if has_picture
            else None
        )
        return InvitePreviewOut(
            kind=kind,
            name=campaign_name,
            campaign_name=campaign_name,
            tenant_kind=None,
            picture_url=picture_url,
            role=role,
        )

    tenant = await session.get_one(Tenant, tenant_id)
    has_picture = (
        await session.execute(
            select(TenantProfilePicture.tenant_id).where(
                TenantProfilePicture.tenant_id == tenant_id
            )
        )
    ).first() is not None
    return InvitePreviewOut(
        kind=kind,
        name=tenant.name,
        campaign_name=None,
        tenant_kind=tenant.kind,
        picture_url=(
            str(request.url_for("get_tenant_picture", tenant_id=tenant_id)) if has_picture else None
        ),
        role=role,
    )


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
            kind=InviteKind.CAMPAIGN,
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
        kind=InviteKind.CAMPAIGN,
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        role=InviteRole.GM,
        player_id=None,
        already_joined=False,
    )


async def _redeem_role_link(
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    *,
    invite: Invite,
) -> InviteRedeemOut:
    """A role link's redemption (ADR 0211): a membership of the invite's tenant with the
    link's role, Author or Organizer, attributed to whoever made the link. **It never changes
    an existing membership**: someone who already holds any role there gets `200`,
    `already_joined`, no use is spent and nothing changes, so a link can raise or lower no
    one's role (that is People's job, by an Owner). The tenant's Owners are told.
    """
    tenant_id, invite_id, link_role = invite.tenant_id, invite.id, invite.role
    if link_role not in (InviteRole.AUTHOR, InviteRole.ORGA):
        raise _reject(request, endpoint="redeem")
    if await session.get(Membership, (tenant_id, user.id)) is not None:
        response.status_code = 200
        return InviteRedeemOut(
            kind=InviteKind.TENANT_ROLE,
            tenant_id=tenant_id,
            campaign_id=None,
            role=link_role,
            player_id=None,
            already_joined=True,
        )

    # The atomic spend, which is what bounds a capped link to its people.
    if not await consume_invite(session, invite_id):
        raise _reject(request, endpoint="redeem")

    role = MembershipRole(link_role.value)
    tenant = await session.get_one(Tenant, tenant_id)
    session.add(
        Membership(
            tenant_id=tenant_id,
            user_id=user.id,
            role=role,
            created_by=invite.created_by,
            updated_by=invite.created_by,
        )
    )
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="invite.redeemed",
        target_type="invite",
        target_id=invite_id,
        detail=f"kind=tenant_role, role={role.value}, member={user.id}",
    )
    who = user.display_name or user.nickname or "Someone"
    await create_tenant_owners_notification(
        session,
        tenant_id=tenant_id,
        type="invite_role_redeemed",
        title=f"{who} joined {tenant.name} as {role_phrase(role)}",
        body=f"{who} used an invite link to join the {tenant_word(tenant.kind)} {tenant.name}.",
        created_by=user.id,
    )
    await session.commit()
    return InviteRedeemOut(
        kind=InviteKind.TENANT_ROLE,
        tenant_id=tenant_id,
        campaign_id=None,
        role=link_role,
        player_id=None,
        already_joined=False,
    )


async def _redeem_library_link(
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    *,
    invite: Invite,
    library_id: uuid.UUID | None,
) -> InviteRedeemOut:
    """A library-access link's redemption (ADR 0211): the repository the link was made for is
    granted to a library the caller owns, named in the request body (`library_id`), with the
    same writes, log and notice as an Owner granting it by id. The library is any tenant the
    caller is an Owner of other than the repository itself, a repository too, for a bridge;
    one that does not exist and one that is not theirs get the same `422`. A library that
    already holds the grant gets `200` and spends no use. The repository's Owners are told.
    """
    repository_id, invite_id = invite.tenant_id, invite.id
    repository = await session.get_one(Tenant, repository_id)
    if repository.kind is not TenantKind.REPOSITORY:
        raise _reject(request, endpoint="redeem")
    if library_id is None:
        raise InviteLibraryRequiredError(
            detail="Say which library to share it with: send library_id in the body."
        )
    # The caller's own memberships are readable whatever tenant the request runs under.
    membership = await session.get(Membership, (library_id, user.id))
    library = await session.get(Tenant, library_id)
    if (
        library is None
        or library_id == repository_id
        or membership is None
        or membership.role is not MembershipRole.OWNER
    ):
        raise InvalidInviteLibraryError(
            detail="Choose a library or repository you own to share it with."
        )

    if await session.get(RepositorySubscription, (repository_id, library_id)) is not None:
        response.status_code = 200
        return InviteRedeemOut(
            kind=InviteKind.LIBRARY_ACCESS,
            tenant_id=repository_id,
            campaign_id=None,
            role=None,
            player_id=None,
            library_id=library_id,
            already_joined=True,
        )

    if not await consume_invite(session, invite_id):
        raise _reject(request, endpoint="redeem")

    await grant_repository_access(
        session,
        repository=repository,
        subscriber=library,
        granted_by=user.id,
        detail=f"invite={invite_id}",
    )
    await record_activity(
        session,
        tenant_id=repository_id,
        actor_id=user.id,
        action="invite.redeemed",
        target_type="invite",
        target_id=invite_id,
        detail=f"kind=library_access, library={library_id}",
    )
    who = user.display_name or user.nickname or "Someone"
    await create_tenant_owners_notification(
        session,
        tenant_id=repository_id,
        type="invite_library_redeemed",
        title=f"{who} shared {repository.name} with {library.name}",
        body=(
            f"{who} used an invite link to share the repository {repository.name}"
            f" with the {tenant_word(library.kind)} {library.name}."
        ),
        created_by=user.id,
    )
    await session.commit()
    return InviteRedeemOut(
        kind=InviteKind.LIBRARY_ACCESS,
        tenant_id=repository_id,
        campaign_id=None,
        role=None,
        player_id=None,
        library_id=library_id,
        already_joined=False,
    )


@router.post("/invites/{token}/redeem", status_code=201)
async def redeem_invite(
    token: str,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    body: InviteRedeemIn | None = None,
) -> InviteRedeemOut:
    """Authenticated but not tenant-scoped: any verified Authgear user
    (ADR 0092) - joining creates a `player` row, which needs a user. Gives
    the player role in this one campaign and nothing more; never tenant
    membership. A GM link (ADR 0177) gives a GM row instead, and no player
    row. Idempotent: someone who already holds the role gets `200` and no
    second seat, no use consumed. `201` the first time.

    The other kinds (ADR 0211): a role link makes the caller an Author or an Organizer of its
    library or repository, and never changes a role they already hold; a library-access link
    grants its repository to the library named in the body.
    """
    invite = await find_live_invite(session, token)
    if invite is None:
        raise _reject(request, endpoint="redeem")
    tenant_id, campaign_id, invite_id = invite.tenant_id, invite.campaign_id, invite.id
    role, granted_by = invite.role, invite.created_by
    await set_tenant_rls_context(session, tenant_id)

    if invite.kind is InviteKind.TENANT_ROLE:
        return await _redeem_role_link(request, response, session, user, invite=invite)
    if invite.kind is InviteKind.LIBRARY_ACCESS:
        return await _redeem_library_link(
            request,
            response,
            session,
            user,
            invite=invite,
            library_id=body.library_id if body else None,
        )
    if campaign_id is None:
        raise _reject(request, endpoint="redeem")

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
            kind=InviteKind.CAMPAIGN,
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
        kind=InviteKind.CAMPAIGN,
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        role=InviteRole.PLAYER,
        player_id=player_id,
        already_joined=False,
    )
