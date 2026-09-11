import uuid
from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import ParamsDep, SessionDep, get_campaign_context
from lorenzo_api.exceptions import PlayerNotFoundError
from lorenzo_api.models import Being, CampaignGm, Character, CharacterPlayer, Player
from lorenzo_api.schemas.campaigns import GmOut
from lorenzo_api.schemas.players import PlayerDetailOut, PlayerOut

# get_campaign_context here, not per-route (ADR 0020's revised guidance,
# matching entities.py) - every route on this router needs it and none read
# its return value beyond what campaign_id (already a path param) already
# gives them. ADR 0031/RFC 0004: gated by get_campaign_context, not
# get_tenant_context - an ordinary player/GM reaching their own campaign's
# roster has no tenant-wide Membership row to satisfy the stricter gate.
router = APIRouter(
    prefix="/tenants/{tenant_id}/campaigns/{campaign_id}",
    tags=["players"],
    dependencies=[Depends(get_campaign_context)],
)

_character_eager_load = (
    selectinload(Player.character_links)
    .selectinload(CharacterPlayer.character)
    .selectinload(Character.being)
    .selectinload(Being.entity)
)


@router.get("/players")
async def list_players(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, session: SessionDep, params: ParamsDep
) -> Page[PlayerOut]:
    stmt = (
        select(Player)
        .where(Player.campaign_id == campaign_id, Player.tenant_id == tenant_id)
        .options(_character_eager_load)
        .order_by(Player.id)
    )

    def _players_out(players: Sequence[Player]) -> list[PlayerOut]:
        return [PlayerOut.from_player(p) for p in players]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise exact.
    return cast(Page[PlayerOut], await apaginate(session, stmt, params, transformer=_players_out))


@router.get("/players/{player_id}")
async def get_player(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, player_id: uuid.UUID, session: SessionDep
) -> PlayerDetailOut:
    """Same shape as PlayerOut (RFC 0004: Player has no columns the
    summary omits) - its own schema/route anyway, matching the RFC's own
    endpoint table.
    """
    stmt = (
        select(Player)
        .where(
            Player.id == player_id,
            Player.campaign_id == campaign_id,
            Player.tenant_id == tenant_id,
        )
        .options(_character_eager_load)
    )
    player = (await session.execute(stmt)).scalar_one_or_none()
    if player is None:
        raise PlayerNotFoundError(detail=f"No player with id {player_id} in campaign {campaign_id}")
    return PlayerDetailOut.from_player(player)


@router.get("/gms")
async def list_gms(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, session: SessionDep
) -> list[GmOut]:
    """Unpaginated - matching OwnedByResponse's existing precedent of
    skipping pagination for a collection inherently small and bounded by
    construction (ADR 0031/RFC 0004).
    """
    stmt = (
        select(CampaignGm)
        .where(CampaignGm.campaign_id == campaign_id, CampaignGm.tenant_id == tenant_id)
        .order_by(CampaignGm.user_id)
    )
    gms = (await session.execute(stmt)).scalars().all()
    return [GmOut.from_campaign_gm(gm) for gm in gms]
