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

from lorenzo_api.entity_access import controlled_character_entity_ids
from lorenzo_api.models import (
    CampaignGm,
    CharacterPlayer,
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


async def can_manage_campaign(
    session: AsyncSession, *, user_id: uuid.UUID, campaign_id: uuid.UUID, tenant_id: uuid.UUID
) -> bool:
    """A CampaignGm row, OR tenant-wide OWNER/ORGA - regardless of any
    TenantAdminCampaignOptOut for this campaign (RFC 0006). Deliberately
    does not reuse can_access_campaign wholesale: that predicate is about
    *play* visibility (a tenant admin's opt-out exists so they can play an
    ordinary character without their admin access bleeding in), while
    administrative capability over the campaign as an object is a
    different axis, tied to who can administer the tenant at all (ADR
    0010: "ownership transfer is just changing which membership row has
    role=owner") - an opt-out shouldn't strip that. A plain player is
    never a manager. Pulled forward into this ADR (0032) rather than
    waiting for campaign CRUD's own ADR (0034), since RFC 0005's
    item-instance authorization needs it too - both RFCs consume this one
    predicate, neither owns it exclusively.
    """
    if await session.get(CampaignGm, (tenant_id, user_id, campaign_id)) is not None:
        return True
    return await is_tenant_admin(session, tenant_id=tenant_id, user_id=user_id)


async def can_manage_any_campaign_in_tenant(
    session: AsyncSession, *, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> bool:
    """Whether the caller can_manage_campaign on *at least one* campaign in
    this tenant - RFC 0005's fallback for ownerless item-instance creation
    (no character to resolve a specific campaign from). Narrower than
    is_tenant_participant: a plain player with no GM standing anywhere
    doesn't qualify just by being a tenant member, matching RFC 0005's own
    "populating the world with unclaimed items reads closer to authoring
    than to ordinary play" reasoning.
    """
    if await is_tenant_admin(session, tenant_id=tenant_id, user_id=user_id):
        return True
    gm_stmt = (
        select(CampaignGm.campaign_id)
        .where(CampaignGm.user_id == user_id, CampaignGm.tenant_id == tenant_id)
        .limit(1)
    )
    return (await session.execute(gm_stmt)).first() is not None


async def campaign_ids_for_character(
    session: AsyncSession, *, character_entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    """Every campaign a character is currently rostered into, via its
    CharacterPlayer -> Player -> campaign_id chain - RFC 0005's "assigning
    to someone else's character" check needs this to test can_manage_campaign
    against the *specific* campaign(s) that character belongs to, not every
    campaign in the tenant.
    """
    stmt = (
        select(Player.campaign_id)
        .join(CharacterPlayer, CharacterPlayer.player_id == Player.id)
        .where(
            CharacterPlayer.character_entity_id == character_entity_id,
            Player.tenant_id == tenant_id,
        )
    )
    return frozenset((await session.execute(stmt)).scalars().all())


async def can_manage_any_of_campaigns(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    campaign_ids: frozenset[uuid.UUID],
    tenant_id: uuid.UUID,
) -> bool:
    """can_manage_campaign on at least one of campaign_ids - RFC 0005's "any
    one is enough" rule for assigning an item instance to someone else's
    character: that character's inventory is already shared uniformly
    across every campaign it's rostered into (ADR 0025), so one campaign's
    GM oversight is enough.
    """
    return any(
        [
            await can_manage_campaign(
                session, user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            for campaign_id in campaign_ids
        ]
    )


async def can_manage_character(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    character_entity_id: uuid.UUID,
) -> bool:
    """Self-control OR can-manage-any-one-of-its-campaigns OR (rostered
    into no campaign at all) can-manage-any-campaign-in-tenant - the "any
    one is enough" authorization shape routers/characters.py's own PATCH
    rename path first established (ADR 0036/RFC 0007), promoted here so a
    second call site (group-scoped notifications, ADR 0059) doesn't need
    its own copy of the same three-way check.
    """
    controlled = await controlled_character_entity_ids(
        session, user_id=user_id, tenant_id=tenant_id
    )
    if character_entity_id in controlled:
        return True
    campaign_ids = await campaign_ids_for_character(
        session, character_entity_id=character_entity_id, tenant_id=tenant_id
    )
    if campaign_ids:
        return await can_manage_any_of_campaigns(
            session, user_id=user_id, campaign_ids=campaign_ids, tenant_id=tenant_id
        )
    return await can_manage_any_campaign_in_tenant(session, user_id=user_id, tenant_id=tenant_id)


async def can_manage_every_campaign(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    campaign_ids: frozenset[uuid.UUID],
    tenant_id: uuid.UUID,
) -> bool:
    """can_manage_campaign on *every* one of campaign_ids - the "all, not
    any" counterpart to can_manage_any_of_campaigns above, added for RFC
    0007's character authorization. Two of that RFC's three "managed" tiers
    need this, not just DELETE /characters/{id}'s own "every campaign the
    character currently belongs to" (demotion ends its presence everywhere
    at once, so every campaign needs to consent, not just one): the
    roster-link tier (adding/removing/reassigning a *specific* set of
    Player rows - CharacterCreate's player_ids, an owner reassignment, or
    the roster sub-resource PUT/DELETE) also needs "no more and no less"
    standing - exactly the campaigns of the Player row(s) actually being
    touched, all of them, not just one - which is this same "all" shape
    applied to a (usually much smaller, often single-element) set rather
    than a character's full current roster. An empty campaign_ids is
    vacuously true (`all([])`) - callers passing an empty set here are
    expected to have already handled "nothing to scope the check to at
    all" via their own tenant-wide fallback (mirroring
    can_manage_any_of_campaigns' identical non-handling of the empty case,
    and RFC 0005/RFC 0007's own explicit ownerless-creation fallback).
    """
    return all(
        [
            await can_manage_campaign(
                session, user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id
            )
            for campaign_id in campaign_ids
        ]
    )


async def campaign_ids_for_players(
    session: AsyncSession, *, player_ids: frozenset[uuid.UUID], tenant_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    """Every campaign a given set of Player rows belongs to - RFC 0007's own
    "specific campaign(s) of the Player row(s) actually being touched" set
    for a roster-link write, resolved directly from Player rows rather than
    campaign_ids_for_character's CharacterPlayer walk: a character being
    created or promoted doesn't exist yet for that walk to start from, and
    a reassignment/roster-sub-resource write only ever touches one or a
    few specific Player rows, not a character's whole existing roster. No
    empty-set short-circuit here (unlike routers/characters.py's own
    _require_players_exist, which already guards its only call site) -
    SQLAlchemy's in_() already handles an empty collection safely, and its
    one caller never actually calls this with one.
    """
    stmt = select(Player.campaign_id).where(
        Player.id.in_(player_ids), Player.tenant_id == tenant_id
    )
    return frozenset((await session.execute(stmt)).scalars().all())
