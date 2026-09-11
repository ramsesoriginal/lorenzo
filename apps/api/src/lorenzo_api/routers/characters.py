import uuid
from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import ParamsDep, SessionDep, get_tenant_context
from lorenzo_api.exceptions import CharacterNotFoundError
from lorenzo_api.models import Being, Character, CharacterPlayer, Player
from lorenzo_api.schemas.characters import CharacterOut, CharacterSummaryOut
from lorenzo_api.schemas.players import PlayerSummaryOut

# CharacterOut.players: list[PlayerSummaryOut] is a forward reference
# (schemas/characters.py only imports schemas/players.py under
# TYPE_CHECKING, to avoid a real circular import - see that module's own
# docstring). Resolving it needs PlayerSummaryOut in scope somewhere;
# rebuilt explicitly here, at import time, rather than relying on whichever
# module happens to import schemas/players.py first - this router needs
# both anyway and is guaranteed to load once, at app startup.
CharacterOut.model_rebuild(_types_namespace={"PlayerSummaryOut": PlayerSummaryOut})

# get_tenant_context (ADR 0031/RFC 0004): deliberately bare-tenant-scoped,
# not campaign-nested - a character has no single fixed campaign (roster
# reuse, ADR 0025), and only tenant-wide members (who already see
# everything) reach this, so there's no separate visibility filtering to
# do the way information_visibility.py has to for entity descriptions.
router = APIRouter(
    prefix="/tenants/{tenant_id}/characters",
    tags=["characters"],
    dependencies=[Depends(get_tenant_context)],
)

_name_eager_load = selectinload(Character.being).selectinload(Being.entity)
_detail_eager_load = (
    _name_eager_load,
    selectinload(Character.player_links)
    .selectinload(CharacterPlayer.player)
    .selectinload(Player.character_links)
    .selectinload(CharacterPlayer.character)
    .selectinload(Character.being)
    .selectinload(Being.entity),
)


@router.get("")
async def list_characters(
    tenant_id: uuid.UUID, session: SessionDep, params: ParamsDep
) -> Page[CharacterSummaryOut]:
    """Specifically a roster of Character rows, not every Being - a bare
    being with no character row doesn't appear here at all (ADR 0031/RFC
    0004).
    """
    stmt = (
        select(Character)
        .where(Character.tenant_id == tenant_id)
        .options(_name_eager_load)
        .order_by(Character.entity_id)
    )

    def _characters_out(characters: Sequence[Character]) -> list[CharacterSummaryOut]:
        return [CharacterSummaryOut.from_character(c) for c in characters]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise exact.
    return cast(
        Page[CharacterSummaryOut],
        await apaginate(session, stmt, params, transformer=_characters_out),
    )


@router.get("/{character_id}")
async def get_character(
    tenant_id: uuid.UUID, character_id: uuid.UUID, session: SessionDep
) -> CharacterOut:
    stmt = (
        select(Character)
        .where(Character.entity_id == character_id, Character.tenant_id == tenant_id)
        .options(*_detail_eager_load)
    )
    character = (await session.execute(stmt)).scalar_one_or_none()
    if character is None:
        raise CharacterNotFoundError(
            detail=f"No character with id {character_id} in tenant {tenant_id}"
        )
    return CharacterOut.from_character(character)
