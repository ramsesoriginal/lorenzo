from fastapi import APIRouter
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import CurrentUser, SessionDep, set_tenant_rls_context
from lorenzo_api.exceptions import LastOwnerError
from lorenzo_api.models import (
    Being,
    CampaignGm,
    Character,
    CharacterPlayer,
    Membership,
    MembershipRole,
    Player,
    User,
)
from lorenzo_api.schemas.users import MeOut

router = APIRouter(tags=["users"])

_character_eager_load = (
    selectinload(Player.character_links)
    .selectinload(CharacterPlayer.character)
    .selectinload(Character.being)
    .selectinload(Being.entity)
)


@router.get("/me")
async def get_me(user: CurrentUser, session: SessionDep) -> MeOut:
    """Proves the whole token-verification pipeline end to end over real
    HTTP - see ADR 0023. Not nested under /tenants/{tenant_id}/... - this
    is about the caller's own identity across every tenant they belong to,
    not scoped to one.

    Re-fetched with memberships eager-loaded rather than reusing the
    `user` CurrentUser resolved - that one only ever needs `.id` itself.

    Players/campaign_gm_grants (ADR 0031/RFC 0004) are resolved tenant by
    tenant, deliberately not in one eager-loaded query off `user`. `Player`/
    `CampaignGm` rows self-authorize via `user_id` regardless of
    `app.tenant_id` (ADR 0030's addendum), but what each one references -
    `character_player`/`character`/`being`/`entity` via `Player`; `Campaign`
    via `CampaignGm` - has no `user_id` column of its own for RLS to
    self-authorize against, and this user's players/GM grants can
    legitimately span *multiple* tenants, so there is no single
    `app.tenant_id` that would correctly authorize all of them at once
    regardless (unlike `/me`'s own memberships, campaign_gm, and player
    rows themselves). Confirmed empirically, not assumed: querying this
    chain with `app.tenant_id` never set at all raises
    `UndefinedObjectError`, the same "genuinely never set" failure mode
    every other RLS-protected table already has - `player`/`campaign_gm`
    just happen to have a `user_id`-based escape hatch, and nothing past
    them does.
    """
    stmt = select(User).where(User.id == user.id).options(selectinload(User.memberships))
    full_user = (await session.execute(stmt)).scalar_one()

    player_tenant_ids = (
        await session.execute(select(Player.tenant_id).where(Player.user_id == user.id).distinct())
    ).scalars()
    gm_tenant_ids = (
        await session.execute(
            select(CampaignGm.tenant_id).where(CampaignGm.user_id == user.id).distinct()
        )
    ).scalars()

    players: list[Player] = []
    campaign_gms: list[CampaignGm] = []
    for tenant_id in set(player_tenant_ids) | set(gm_tenant_ids):
        await session.execute(
            text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
        )
        tenant_players = await session.execute(
            select(Player)
            .where(Player.user_id == user.id, Player.tenant_id == tenant_id)
            .options(_character_eager_load)
        )
        players.extend(tenant_players.scalars().all())

        tenant_gms = await session.execute(
            select(CampaignGm)
            .where(CampaignGm.user_id == user.id, CampaignGm.tenant_id == tenant_id)
            .options(selectinload(CampaignGm.campaign))
        )
        campaign_gms.extend(tenant_gms.scalars().all())

    return MeOut.from_user(full_user, players=players, campaign_gms=campaign_gms)


@router.delete("/me", status_code=204)
async def delete_me(user: CurrentUser, session: SessionDep) -> None:
    """ADR 0036/RFC 0007 - removes the caller's own app_user row. Guarded:
    409 LastOwnerError if the caller is the sole OWNER Membership of any
    tenant they belong to - deleting themselves would leave that tenant
    with no one able to administer it at all (the same lockout PATCH/
    DELETE /memberships also guard, from the other direction).

    Every owner-tenant is checked *before* anything is deleted - one
    tenant failing the guard must not leave a half-completed deletion
    behind. Each check needs its own set_tenant_rls_context call first:
    membership's RLS policy admits a caller's own rows via app.user_id
    (ADR 0023's own self-access carve-out for GET /me), but *other* users'
    OWNER rows in the same tenant only become visible once app.tenant_id
    is set for that specific tenant - unlike this function's own
    Membership.user_id-scoped query just below, which needs no such
    context at all.

    Once past every guard, the actual deletion is a bare `DELETE FROM
    app_user`, no RLS context needed for it either: every cascade this
    triggers (Membership/Player/CampaignGm/TenantAdminCampaignOptOut rows
    in *every* tenant this user touched, and every created_by/updated_by
    this user ever left behind, all `ON DELETE CASCADE`/`SET NULL` per ADR
    0029) is a foreign-key referential action, which Postgres always runs
    regardless of row security policies on the referencing tables -
    confirmed against Postgres's own documented row-security semantics,
    not just assumed, and proven out by this module's own cascade test.
    """
    owner_tenant_ids = (
        (
            await session.execute(
                select(Membership.tenant_id).where(
                    Membership.user_id == user.id, Membership.role == MembershipRole.OWNER
                )
            )
        )
        .scalars()
        .all()
    )

    for tenant_id in owner_tenant_ids:
        await set_tenant_rls_context(session, tenant_id)
        owner_ids = (
            (
                await session.execute(
                    select(Membership.user_id).where(
                        Membership.tenant_id == tenant_id, Membership.role == MembershipRole.OWNER
                    )
                )
            )
            .scalars()
            .all()
        )
        if owner_ids == [user.id]:
            raise LastOwnerError(detail=f"User {user.id} is the sole OWNER of tenant {tenant_id}")

    await session.delete(await session.get_one(User, user.id))
    await session.commit()
