from fastapi import APIRouter
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import CurrentUser, SessionDep
from lorenzo_api.models import Being, CampaignGm, Character, CharacterPlayer, Player, User
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
