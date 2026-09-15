import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import exists, select

from lorenzo_api.campaign_access import can_manage_campaign, is_tenant_admin, is_tenant_participant
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_campaign_context,
    get_tenant_context,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import (
    CampaignAdminOptOutRequiresAdminError,
    CampaignManagementForbiddenError,
    CampaignNotEmptyError,
    CampaignNotFoundError,
    TenantNotFoundError,
)
from lorenzo_api.models import Campaign, CampaignGm, Entity, Player, TenantAdminCampaignOptOut
from lorenzo_api.schemas.campaigns import (
    CampaignCreate,
    CampaignOut,
    CampaignSummaryOut,
    CampaignUpdate,
)

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
    """The tenant's campaign catalog - gated by is_tenant_participant (any
    Membership/Player/CampaignGm row anywhere in the tenant), not
    get_tenant_context, per ADR 0030/RFC 0003. Secret campaigns are then
    filtered per row: included only if the caller is that campaign's own GM
    or a tenant admin - a plain Player of a secret campaign they don't GM
    doesn't see it here either (they already know about it directly via
    their own `/me` response, RFC 0004).
    """
    if not await is_tenant_participant(session, tenant_id=tenant_id, user_id=user.id):
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")

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
    for field in ("name", "game_system", "slug", "description", "secret"):
        if field in update:
            setattr(campaign, field, update[field])
    if update:
        campaign.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)


@router.delete("/{campaign_id}", status_code=204)
async def delete_campaign(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    campaign_id: uuid.UUID,
    session: SessionDep,
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

    entity_id = campaign.entity_id
    await session.delete(campaign)
    await session.flush()
    await session.delete(await session.get_one(Entity, entity_id))
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
    """
    await _require_can_manage(session, tenant_id=tenant_id, campaign_id=campaign_id, user=user)

    existing = await session.get(CampaignGm, (tenant_id, user_id, campaign_id))
    if existing is None:
        session.add(
            CampaignGm(
                tenant_id=tenant_id, user_id=user_id, campaign_id=campaign_id, created_by=user.id
            )
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
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)


@router.put("/{campaign_id}/admin-opt-out")
async def opt_out_of_campaign_admin_visibility(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    session: SessionDep,
    user: CurrentUser,
) -> CampaignOut:
    """Self-service only - no user_id in the path, always the caller (ADR
    0034/RFC 0006). Requires the caller to currently hold tenant-wide
    OWNER/ORGA - 422, not a silent no-op, since opting out of a bypass you
    don't hold in the first place is meaningless. Idempotent, matching the
    GM grant above.
    """
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
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)


@router.delete("/{campaign_id}/admin-opt-out")
async def opt_back_in_to_campaign_admin_visibility(
    tenant_id: uuid.UUID,
    campaign_id: Annotated[uuid.UUID, Depends(get_campaign_context)],
    session: SessionDep,
    user: CurrentUser,
) -> CampaignOut:
    """Self-service only, no precondition - deleting a row that doesn't
    exist is already a no-op (ADR 0034/RFC 0006).
    """
    existing = await session.get(TenantAdminCampaignOptOut, (tenant_id, user.id, campaign_id))
    if existing is not None:
        await session.delete(existing)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _campaign_out(tenant_id, campaign_id, session)
