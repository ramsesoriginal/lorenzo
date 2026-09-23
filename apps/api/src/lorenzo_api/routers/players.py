import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import can_manage_campaign
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_campaign_context,
    set_tenant_rls_context,
)
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import (
    CampaignManagementForbiddenError,
    InvalidUserError,
    PlayerAlreadyExistsError,
    PlayerNotFoundError,
)
from lorenzo_api.models import Being, CampaignGm, Character, CharacterPlayer, Player, User
from lorenzo_api.schemas.campaigns import GmOut
from lorenzo_api.schemas.players import PlayerCreate, PlayerOut, PlayerSummaryOut

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
) -> Page[PlayerSummaryOut]:
    stmt = (
        select(Player)
        .where(Player.campaign_id == campaign_id, Player.tenant_id == tenant_id)
        .options(_character_eager_load)
        .order_by(Player.id)
    )

    def _players_out(players: Sequence[Player]) -> list[PlayerSummaryOut]:
        return [PlayerSummaryOut.from_player(p) for p in players]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise exact.
    return cast(
        Page[PlayerSummaryOut], await apaginate(session, stmt, params, transformer=_players_out)
    )


@router.get("/players/{player_id}")
async def get_player(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, player_id: uuid.UUID, session: SessionDep
) -> PlayerOut:
    """Same shape as PlayerSummaryOut (RFC 0004: Player has no columns the
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
    return PlayerOut.from_player(player)


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


# --- Player join/leave (ADR 0036/RFC 0007) --------------------------------


async def _get_player_or_404(
    tenant_id: uuid.UUID, campaign_id: uuid.UUID, player_id: uuid.UUID, session: SessionDep
) -> Player:
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
    return player


@router.post("/players", status_code=201)
async def create_player(
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    body: PlayerCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> PlayerSummaryOut:
    """can_manage_campaign gates adding - a GM building their own roster,
    or a tenant admin, not a self-service join (RFC 0007's own Open
    questions: no invite-link/visibility mechanism exists yet that would
    make self-service joining safe).
    """
    if not await can_manage_campaign(
        session, user_id=user.id, campaign_id=campaign_id, tenant_id=tenant_id
    ):
        raise CampaignManagementForbiddenError(
            detail=f"Not authorized to manage campaign {campaign_id}"
        )
    if await session.get(User, body.user_id) is None:
        raise InvalidUserError(detail=f"{body.user_id} is not an existing user")

    existing_stmt = select(Player.id).where(
        Player.campaign_id == campaign_id, Player.user_id == body.user_id
    )
    if (await session.execute(existing_stmt)).first() is not None:
        raise PlayerAlreadyExistsError(
            detail=f"User {body.user_id} already has a player in campaign {campaign_id}"
        )

    player = Player(
        user_id=body.user_id,
        campaign_id=campaign_id,
        tenant_id=tenant_id,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(player)
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="player.added",
        target_type="player",
        target_id=player.id,
        detail=f"user={body.user_id}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for(
            "get_player", tenant_id=tenant_id, campaign_id=campaign_id, player_id=player.id
        )
    )
    created = await _get_player_or_404(tenant_id, campaign_id, player.id, session)
    return PlayerSummaryOut.from_player(created)


@router.delete("/players/{player_id}", status_code=204)
async def delete_player(
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    player_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """can_manage_campaign, or the player leaving their own campaign
    voluntarily - the self-service half doesn't require can_manage_campaign
    at all, mirroring revoke_campaign_gm's identical self-removal
    carve-out.
    """
    player = await _get_player_or_404(tenant_id, campaign_id, player_id, session)
    check_if_match(if_match, updated_at=player.updated_at)

    if player.user_id != user.id and not await can_manage_campaign(
        session, user_id=user.id, campaign_id=campaign_id, tenant_id=tenant_id
    ):
        raise CampaignManagementForbiddenError(
            detail=f"Not authorized to manage campaign {campaign_id}"
        )

    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="player.removed",
        target_type="player",
        target_id=player_id,
        detail=f"{'left' if player.user_id == user.id else 'removed'}, user={player.user_id}",
    )
    await session.delete(player)
    await session.commit()
