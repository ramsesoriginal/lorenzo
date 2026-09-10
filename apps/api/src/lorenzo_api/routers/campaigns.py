import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import exists, select

from lorenzo_api.campaign_access import is_tenant_admin, is_tenant_participant
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_campaign_context,
    get_tenant_or_404,
)
from lorenzo_api.exceptions import CampaignNotFoundError, TenantNotFoundError
from lorenzo_api.models import Campaign, CampaignGm
from lorenzo_api.schemas.campaigns import CampaignOut, CampaignSummaryOut

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
    stmt = select(Campaign).where(Campaign.id == campaign_id, Campaign.tenant_id == tenant_id)
    campaign = (await session.execute(stmt)).scalar_one_or_none()
    if campaign is None:
        raise CampaignNotFoundError(
            detail=f"No campaign with id {campaign_id} in tenant {tenant_id}"
        )
    return CampaignOut.model_validate(campaign)
