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

from lorenzo_api.models import CampaignGm, Membership, MembershipRole, OrgaCampaignOptOut, Player


async def is_tenant_orga(
    session: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> bool:
    """Whether a user holds the tenant-wide ORGA role - RFC 0002/ADR 0022.
    Split out since `information_visibility.py` needs the identical check
    but has no single campaign_id to test an opt-out against (unlike
    `can_access_campaign` below) - see that module's own docstring for why
    it handles the opt-out side differently instead of sharing that part
    too.
    """
    membership = await session.get(Membership, (tenant_id, user_id))
    return membership is not None and membership.role is MembershipRole.ORGA


async def can_access_campaign(
    session: AsyncSession, *, user_id: uuid.UUID, campaign_id: uuid.UUID, tenant_id: uuid.UUID
) -> bool:
    """RFC 0002's access rule, checked in the exact order it states them -
    a player row, a campaign_gm row, or tenant-orga without an opt-out.
    Short-circuits: the common case (an ordinary player) resolves after
    just the first query.
    """
    player_stmt = select(Player.id).where(
        Player.user_id == user_id, Player.campaign_id == campaign_id
    )
    if (await session.execute(player_stmt)).first() is not None:
        return True

    if await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is not None:
        return True

    if not await is_tenant_orga(session, tenant_id=tenant_id, user_id=user_id):
        return False

    opted_out = await session.get(OrgaCampaignOptOut, (tenant_id, user_id, campaign_id))
    return opted_out is None
