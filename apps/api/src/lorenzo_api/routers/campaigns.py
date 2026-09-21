import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, UploadFile
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import exists, select

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import can_manage_campaign, is_tenant_admin
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_campaign_context,
    get_tenant_context,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import (
    CampaignAdminOptOutRequiresAdminError,
    CampaignManagementForbiddenError,
    CampaignNotEmptyError,
    CampaignNotFoundError,
    InvalidUserError,
)
from lorenzo_api.models import Campaign, CampaignGm, Entity, Player, TenantAdminCampaignOptOut, User
from lorenzo_api.notifications import create_campaign_notification
from lorenzo_api.profile_pictures import (
    delete_campaign_profile_picture,
    read_and_validate_upload,
    upsert_campaign_profile_picture,
)
from lorenzo_api.schemas.campaigns import (
    CampaignCreate,
    CampaignOut,
    CampaignSummaryOut,
    CampaignUpdate,
)
from lorenzo_api.schemas.notifications import NotificationCreate, NotificationOut

# get_tenant_or_404 here, not get_tenant_context (ADR 0030/RFC 0003): an
# ordinary participant with zero tenant-wide Membership rows must still be
# able to browse this tenant's campaigns - get_campaign_context (the detail
# route below) depends on get_tenant_or_404 directly too, so FastAPI's
# per-request dependency caching means it isn't run twice.
router = APIRouter(
    prefix="/tenants/{tenant_id}/campaigns",
    tags=["campaigns"],
    dependencies=[Depends(get_tenant_or_404)],
)


@router.get("")
async def list_campaigns(
    tenant_id: uuid.UUID, user: CurrentUser, session: SessionDep, params: ParamsDep
) -> Page[CampaignSummaryOut]:
    """The tenant's campaign catalog - gated by require_tenant_participant
    (any Membership/Player/CampaignGm row anywhere in the tenant), not
    get_tenant_context, per ADR 0030/RFC 0003. Secret campaigns are then
    filtered per row: included only if the caller is that campaign's own GM
    or a tenant admin - a plain Player of a secret campaign they don't GM
    doesn't see it here either (they already know about it directly via
    their own `/me` response, RFC 0004).
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)

    stmt = select(Campaign).where(Campaign.tenant_id == tenant_id)
    if not await is_tenant_admin(session, tenant_id=tenant_id, user_id=user.id):
        stmt = stmt.where(
            (~Campaign.secret)
            | exists().where(
                CampaignGm.campaign_id == Campaign.id,
                CampaignGm.tenant_id == tenant_id,
                CampaignGm.user_id == user.id,
            )
        )
    stmt = stmt.order_by(Campaign.name, Campaign.id)
    page: Page[CampaignSummaryOut] = await apaginate(session, stmt, params)
    return page


@router.get("/{campaign_id}")
async def get_campaign(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    session: SessionDep,
) -> CampaignOut:
    """Unaffected by `secret` - get_campaign_context already only admits a
    player, a GM, or a tenant admin of this specific campaign; secret only
    governs the general browse-all list above, not whether someone who
    already has a legitimate way to reach it can open it directly (ADR
    0030/RFC 0003, same shape as a private GitHub repo).
    """
    return await _campaign_out(tenant_id, campaign_id, session)


async def _get_campaign_or_404(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, session: SessionDep
) -> Campaign:
    """Loads the writable Campaign row, scoped to tenant_id - existence-only
    (no can_access_campaign re-check), the same non-enumerable shape
    get_tenant_or_404 already establishes. For PATCH (behind
    get_campaign_context, which already ran the fuller check) this is the
    same "re-query for the real row" split entities.py's get_entity and
    tenants.py's get_tenant already use - raising here is effectively dead
    code, just what lets mypy narrow. For DELETE (behind get_tenant_context
    only, ADR 0034/RFC 0006) this *is* the actual existence check.
    """
    stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
    campaign = (await session.execute(stmt)).scalar_one_or_none()
    if campaign is None:
        raise CampaignNotFoundError(
            detail=f"No campaign with id {campaign_id} in tenant {tenant_id}"
        )
    return campaign


async def _campaign_out(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, session: SessionDep
) -> CampaignOut:
    campaign = await _get_campaign_or_404(tenant_id, campaign_id, session)
    return CampaignOut.model_validate(campaign)


async def _require_can_manage(
    session: SessionDep, *, tenant_id: uuid.UUID, campaign_id: uuid.UUID, user: CurrentUser
) -> None:
    if not await can_manage_campaign(
        session, user_id=user.id, campaign_id=campaign_id, tenant_id=tenant_id
    ):
        raise CampaignManagementForbiddenError(
            detail=f"Not authorized to manage campaign {campaign_id}"
        )


@router.post("", status_code=201)
async def create_campaign(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    body: CampaignCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> CampaignOut:
    """get_tenant_context (tenant-wide Membership), not can_manage_campaign
    - there's no campaign yet to manage, so this is the bare-tenant-
    collection tier (ADR 0034/RFC 0006). Creates the campaign's dedicated
    Entity (RFC 0003) server-side, in the same transaction - entity_id is
    never accepted from the client.
    """
    entity = Entity(tenant_id=tenant_id, name=body.name, created_by=user.id, updated_by=user.id)
    session.add(entity)
    await session.flush()
    campaign = Campaign(
        tenant_id=tenant_id,
        name=body.name,
        game_system=body.game_system,
        slug=body.slug,
        description=body.description,
        secret=body.secret,
        entity_id=entity.id,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(campaign)
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="campaign.created",
        target_type="campaign",
        target_id=campaign.id,
        detail=campaign.name,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_campaign", tenant_id=tenant_id, campaign_id=campaign.id)
    )
    return await _campaign_out(tenant_id, campaign.id, session)


@router.patch("/{campaign_id}")
async def update_campaign(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    body: CampaignUpdate,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> CampaignOut:
    campaign = await _get_campaign_or_404(tenant_id, campaign_id, session)
    check_if_match(if_match, updated_at=campaign.updated_at)
    await _require_can_manage(session, tenant_id=tenant_id, campaign_id=campaign_id, user=user)

    update = body.model_dump(exclude_unset=True)
    changed_fields = [
        field
        for field in ("name", "game_system", "slug", "description", "secret")
        if field in update
    ]
    for field in changed_fields:
        setattr(campaign, field, update[field])
    if update:
        campaign.updated_by = user.id
    if changed_fields:
        # Field names only, never values - `secret` is GM-only text a
        # log reader must not learn from the log (ADR 0084).
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="campaign.updated",
            target_type="campaign",
            target_id=campaign_id,
            detail=f"fields={','.join(changed_fields)}",
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)


@router.put("/{campaign_id}/picture", status_code=204)
async def upload_campaign_picture(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    session: SessionDep,
    user: CurrentUser,
    file: UploadFile,
) -> None:
    """Same gate `update_campaign` uses (ADR 0056)."""
    await _require_can_manage(session, tenant_id=tenant_id, campaign_id=campaign_id, user=user)
    data, file_type = await read_and_validate_upload(file)
    await upsert_campaign_profile_picture(
        session, tenant_id=tenant_id, campaign_id=campaign_id, data=data, file_type=file_type
    )
    await session.commit()


@router.delete("/{campaign_id}/picture", status_code=204)
async def delete_campaign_picture(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    session: SessionDep,
    user: CurrentUser,
) -> None:
    await _require_can_manage(session, tenant_id=tenant_id, campaign_id=campaign_id, user=user)
    await delete_campaign_profile_picture(session, campaign_id=campaign_id)
    await session.commit()


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    campaign_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    force: Annotated[
        bool,
        Query(
            description=(
                "Delete even if the campaign still has Player or CampaignGm rows, "
                "letting the existing cascade take the whole roster with it."
            )
        ),
    ] = False,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Gated by get_tenant_context specifically, not get_campaign_context -
    deliberately not layered under can_access_campaign, whose own opt-out
    mechanism (TenantAdminCampaignOptOut) must not be able to lock its
    holder out of deleting a campaign they otherwise administer (ADR
    0034/RFC 0006). A GM can rename their own campaign (can_manage_campaign,
    above) but can't unilaterally destroy it - deletion is a tenant-admin
    decision.

    The campaign row is deleted first, then its now-unreferenced Entity
    explicitly as a second statement - campaign.entity_id is ON DELETE
    RESTRICT (RFC 0003), so getting this order backwards would fail
    outright.
    """
    campaign = await _get_campaign_or_404(tenant_id, campaign_id, session)
    check_if_match(if_match, updated_at=campaign.updated_at)

    if not force:
        has_player = (
            await session.execute(
                select(Player.id)
                .where(Player.campaign_id == campaign_id, Player.tenant_id == tenant_id)
                .limit(1)
            )
        ).first() is not None
        has_gm = (
            await session.execute(
                select(CampaignGm.campaign_id)
                .where(CampaignGm.campaign_id == campaign_id, CampaignGm.tenant_id == tenant_id)
                .limit(1)
            )
        ).first() is not None
        if has_player or has_gm:
            raise CampaignNotEmptyError(
                detail=(
                    f"Campaign {campaign_id} still has players or GMs; "
                    "pass ?force=true to delete anyway"
                )
            )

    # The campaign_profile_picture link cascades away with campaign below,
    # but nothing points the other way - the profile_picture row itself
    # would otherwise be orphaned forever (ADR 0056). Must run before the
    # campaign row (and its link) is actually gone.
    await delete_campaign_profile_picture(session, campaign_id=campaign_id)

    entity_id = campaign.entity_id
    campaign_name = campaign.name
    await session.delete(campaign)
    await session.flush()
    await session.delete(await session.get_one(Entity, entity_id))
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="campaign.deleted",
        target_type="campaign",
        target_id=campaign_id,
        detail=campaign_name,
    )
    await session.commit()


@router.put("/{campaign_id}/gms/{user_id}")
async def grant_campaign_gm(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    user_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> CampaignOut:
    """Idempotent - granting GM to someone who already has it is a no-op,
    not a 409 (ADR 0034/RFC 0006), mirroring
    set_item_instance_owner/set_item_instance_container's own "no row
    means no relation, PUT replaces/creates it" shape. created_by is the
    granter (the caller), not the grantee (user_id) - never touched again
    on a re-grant, since the row's existence alone is the fact being
    recorded.

    Validates user_id is a real user first, same as create_membership/
    create_player - without this, a nonexistent user_id would otherwise
    hit CampaignGm.user_id's foreign key directly and surface as a raw,
    unhandled IntegrityError (a bare 500) instead of a clean 422.
    """
    await _require_can_manage(session, tenant_id=tenant_id, campaign_id=campaign_id, user=user)
    if await session.get(User, user_id) is None:
        raise InvalidUserError(detail=f"{user_id} is not an existing user")

    existing = await session.get(CampaignGm, (tenant_id, user_id, campaign_id))
    if existing is None:
        session.add(
            CampaignGm(
                tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id, created_by=user.id
            )
        )
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="campaign_gm.granted",
            target_type="campaign_gm",
            target_id=user_id,
            detail=f"campaign_id={campaign_id}",
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)


@router.delete("/{campaign_id}/gms/{user_id}")
async def revoke_campaign_gm(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    user_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> CampaignOut:
    """can_manage_campaign, OR removing your own GM grant - mirroring how a
    collaborator can always leave something they were granted access to
    (ADR 0034/RFC 0006). No last-GM guard, deliberately: a campaign with
    zero GMs is still fully administrable by any tenant-wide member, unlike
    Membership's own structurally-single-point-of-administration shape.
    200 + the parent campaign, even when the grant didn't exist to begin
    with - deleting a singular sub-resource relationship, same shape as
    clear_item_instance_owner/clear_item_instance_container.
    """
    if user_id != user.id:
        await _require_can_manage(session, tenant_id=tenant_id, campaign_id=campaign_id, user=user)

    existing = await session.get(CampaignGm, (tenant_id, user_id, campaign_id))
    if existing is not None:
        await session.delete(existing)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="campaign_gm.revoked",
            target_type="campaign_gm",
            target_id=user_id,
            detail=f"campaign_id={campaign_id}",
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)


@router.put("/{campaign_id}/admin-opt-out")
async def opt_out_of_campaign_admin_visibility(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    campaign_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> CampaignOut:
    """Self-service only - no user_id in the path, always the caller (ADR
    0034/RFC 0006). Requires the caller to currently hold tenant-wide
    OWNER/ORGA - 422, not a silent no-op, since opting out of a bypass you
    don't hold in the first place is meaningless. Idempotent, matching the
    GM grant above.

    Gated by get_tenant_context, not get_campaign_context - the identical
    reasoning DELETE /campaigns/{id} above already applies to itself:
    can_access_campaign's own opt-out-suppression must not be able to lock
    its holder out of the very route that would undo it. Still loads the
    Campaign row scoped to tenant_id first, for the same non-enumerable
    404 shape - it just doesn't run can_access_campaign against it.

    The is_tenant_admin check below is consequently unreachable via any
    real caller today: get_tenant_context already requires a Membership
    row, and MembershipRole has exactly OWNER/ORGA (ADR 0022) - nothing
    else a Membership row could hold. Kept anyway as the explicit
    statement of the actual business rule, not merely an artifact of
    get_tenant_context's own check - the same dead-but-documented-intent
    shape tenants.py's own get_tenant uses for its post-dependency re-fetch.
    """
    await _get_campaign_or_404(tenant_id, campaign_id, session)
    if not await is_tenant_admin(session, tenant_id=tenant_id, user_id=user.id):
        raise CampaignAdminOptOutRequiresAdminError(
            detail="Opting out requires holding tenant-wide OWNER or ORGA in this tenant"
        )

    existing = await session.get(TenantAdminCampaignOptOut, (tenant_id, user.id, campaign_id))
    if existing is None:
        session.add(
            TenantAdminCampaignOptOut(
                tenant_id=tenant_id, user_id=user.id, campaign_id=campaign_id, created_by=user.id
            )
        )
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="campaign.admin_opted_out",
            target_type="campaign",
            target_id=campaign_id,
            detail=None,
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)


@router.delete("/{campaign_id}/admin-opt-out")
async def opt_back_in_to_campaign_admin_visibility(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    campaign_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> CampaignOut:
    """Self-service only, no precondition - deleting a row that doesn't
    exist is already a no-op (ADR 0034/RFC 0006). Gated by
    get_tenant_context, not get_campaign_context, for the same reason the
    PUT above is: this route is exactly how a holder undoes their own
    opt-out, so it must stay reachable even after that opt-out has already
    taken away their can_access_campaign standing.
    """
    await _get_campaign_or_404(tenant_id, campaign_id, session)
    existing = await session.get(TenantAdminCampaignOptOut, (tenant_id, user.id, campaign_id))
    if existing is not None:
        await session.delete(existing)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="campaign.admin_opted_in",
            target_type="campaign",
            target_id=campaign_id,
            detail=None,
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)


@router.post("/{campaign_id}/notifications", status_code=201)
async def create_campaign_notification_route(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    body: NotificationCreate,
    session: SessionDep,
    user: CurrentUser,
) -> list[NotificationOut]:
    """scope="campaign" - see ADR 0058. Same gate `update_campaign` uses.
    An omitted `recipient_user_id` broadcasts to the campaign's Player +
    CampaignGm rows, so this can return more than one row.
    """
    await _require_can_manage(session, tenant_id=tenant_id, campaign_id=campaign_id, user=user)
    if (
        body.recipient_user_id is not None
        and await session.get(User, body.recipient_user_id) is None
    ):
        raise InvalidUserError(detail=f"{body.recipient_user_id} is not an existing user")

    notifications = await create_campaign_notification(
        session,
        tenant_id=tenant_id,
        campaign_id=campaign_id,
        recipient_user_id=body.recipient_user_id,
        type=body.type,
        title=body.title,
        body=body.body,
        created_by=user.id,
    )
    await session.commit()
    return [NotificationOut.model_validate(n) for n in notifications]
