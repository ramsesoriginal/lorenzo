"""RFC 0002's campaign access rule, as a plain, directly-testable helper -
see ADR 0026. Deliberately not a FastAPI dependency yet: there is no
campaign-scoped route to protect. Lives outside dependencies.py on purpose
- this is a domain-access-rule predicate with no HTTP-specific concerns,
meant to be wrapped by a thin get_campaign_context dependency later rather
than have its logic duplicated there.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    CampaignGm,
    Membership,
    MembershipRole,
    Player,
    TenantAdminCampaignOptOut,
)


async def is_tenant_orga(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Whether a user holds the tenant-wide ORGA role specifically - RFC
    0002/ADR 0022. Split out since `information_visibility.py` needs the
    identical check but has no single campaign_id to test an opt-out
    against (unlike `can_access_campaign` below) - see that module's own
    docstring for why it handles the opt-out side differently instead of
    sharing that part too. Deliberately narrower than `is_tenant_admin`
    below: information *visibility* stays ORGA-only per RFC 0009's
    "administrative access != automatic character/GM knowledge" principle,
    even though campaign *reachability* now admits OWNER too.
    """
    membership = await session.get(Membership, (tenant_id, user_id))
    return membership is not None and membership.role is MembershipRole.ORGA


async def is_tenant_admin(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Whether a user holds either tenant-wide role (OWNER or ORGA) - ADR
    0030/RFC 0003. Widens `can_access_campaign`'s blanket-bypass branch
    from ORGA-only to both; see that function's own docstring for why this
    doesn't widen information visibility too.
    """
    membership = await session.get(Membership, (tenant_id, user_id))
    return membership is not None and membership.role in (MembershipRole.OWNER, MembershipRole.ORGA)


async def is_tenant_participant(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Whether a user has *any* relationship to a tenant at all - a
    Membership row (any role), a Player row, or a CampaignGm row, anywhere
    in it (ADR 0030/RFC 0003). Gates `GET /tenants/{id}/campaigns`: an
    ordinary participant should be able to browse the tenant's campaign
    catalog even with zero tenant-wide Membership rows, which ADR 0022
    already established as a legitimate, non-error state. Same
    three-short-circuiting-existence-checks shape as `can_access_campaign`,
    just tenant-wide rather than scoped to one campaign.
    """
    if await session.get(Membership, (tenant_id, user_id)) is not None:
        return True

    player_stmt = select(Player.id).where(Player.user_id == user_id, Player.tenant_id == tenant_id)
    if (await session.execute(player_stmt)).first() is not None:
        return True

    gm_stmt = select(CampaignGm.campaign_id).where(
        CampaignGm.user_id == user_id, CampaignGm.tenant_id == tenant_id
    )
    return (await session.execute(gm_stmt)).first() is not None


async def can_access_campaign(
    session: AsyncSession, *, user_id: uuid.UUID, campaign_id: uuid.UUID, tenant_id: uuid.UUID
) -> bool:
    """RFC 0002's access rule, checked in the exact order it states them -
    a player row, a campaign_gm row, or a tenant admin without an opt-out.
    Short-circuits: the common case (an ordinary player) resolves after
    just the first query.

    Bypass revised from ORGA-only to `is_tenant_admin` (OWNER or ORGA) by
    ADR 0030/RFC 0003 - deliberately narrower in effect than it sounds:
    this only widens campaign *reachability* (can this user GET this
    campaign at all), not information *visibility* (which secrets they see
    once inside it, still gated by `is_tenant_orga` alone in
    information_visibility.py). An OWNER can now reach a campaign's
    metadata/roster the same way an ORGA already could; they still see no
    more of its GM-only secrets than a plain participant would.

    The opt-out mechanism (TenantAdminCampaignOptOut, renamed from
    OrgaCampaignOptOut) widens symmetrically - it now applies to whichever
    of OWNER/ORGA the caller holds, not just ORGA.
    """
    player_stmt = select(Player.id).where(
        Player.user_id == user_id, Player.campaign_id == campaign_id
    )
    if (await session.execute(player_stmt)).first() is not None:
        return True

    if await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is not None:
        return True

    if not await is_tenant_admin(session, tenant_id=tenant_id, user_id=user_id):
        return False

    opted_out = await session.get(TenantAdminCampaignOptOut, (tenant_id, user_id, campaign_id))
    return opted_out is None
