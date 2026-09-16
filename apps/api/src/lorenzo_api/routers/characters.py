import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.campaign_access import (
    campaign_ids_for_character,
    campaign_ids_for_players,
    can_manage_any_campaign_in_tenant,
    can_manage_any_of_campaigns,
    can_manage_every_campaign,
)
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_entity_or_404,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_access import controlled_character_entity_ids
from lorenzo_api.etag import check_if_match
from lorenzo_api.exceptions import (
    CharacterManagementForbiddenError,
    CharacterNotFoundError,
    PlayerNotFoundError,
    TenantNotFoundError,
)
from lorenzo_api.models import (
    Being,
    Character,
    CharacterPlayer,
    Entity,
    GroupMember,
    Membership,
    Player,
)
from lorenzo_api.schemas.characters import (
    CharacterCreate,
    CharacterOut,
    CharacterPromote,
    CharacterSummaryOut,
    CharacterUpdate,
)
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.players import PlayerContextOut

# CharacterOut.players: list[PlayerContextOut] is a forward reference
# (schemas/characters.py only imports schemas/players.py under
# TYPE_CHECKING, to avoid a real circular import - see that module's own
# docstring). Resolving it needs PlayerContextOut in scope somewhere;
# rebuilt explicitly here, at import time, rather than relying on whichever
# module happens to import schemas/players.py first - this router needs
# both anyway and is guaranteed to load once, at app startup.
CharacterOut.model_rebuild(_types_namespace={"PlayerContextOut": PlayerContextOut})

# get_tenant_or_404 here, not get_tenant_context (ADR 0036/RFC 0007,
# mirroring routers/item_instances.py's identical ADR 0032/RFC 0005
# precedent): a plain player rolling their own PC needs no tenant-wide
# Membership row (ADR 0022) to reach POST/PUT/PATCH/DELETE below, so
# gating the whole router on one would lock them out of self-service
# entirely. The two pre-existing GET routes each re-add their own explicit
# get_tenant_context-equivalent check instead (see _require_tenant_member),
# preserving their original ADR 0031/RFC 0004 behavior unchanged - only
# tenant-wide members reach them, same as before this revision. The write
# routes use self-or-managed authorization, narrower still, per-route.
router = APIRouter(
    prefix="/tenants/{tenant_id}/characters",
    tags=["characters"],
    dependencies=[Depends(get_tenant_or_404)],
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


async def _require_tenant_member(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser
) -> None:
    """The membership half of get_tenant_context, without its redundant
    tenant-existence check - get_tenant_or_404 (this router's own
    dependency) already ran that. Preserves list_characters/get_character's
    original ADR 0031/RFC 0004 behavior (only tenant-wide members reach
    them) now that the router itself no longer enforces it up front.
    """
    if await session.get(Membership, (tenant_id, user.id)) is None:
        raise TenantNotFoundError(detail=f"No tenant with id {tenant_id}")


@router.get("")
async def list_characters(
    tenant_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
    mine: Annotated[
        bool,
        Query(
            description=(
                "Only characters owned by the caller (owner_player_id resolves to "
                "one of their own Player rows) - not the broader roster of "
                "characters they merely co-pilot, see ADR 0049."
            )
        ),
    ] = False,
) -> Page[CharacterSummaryOut]:
    """Specifically a roster of Character rows, not every Being - a bare
    being with no character row doesn't appear here at all (ADR 0031/RFC
    0004).
    """
    await _require_tenant_member(session, tenant_id=tenant_id, user=user)
    stmt = select(Character).where(Character.tenant_id == tenant_id)
    if mine:
        # Mirrors entity_access.py's own "resolve the caller's Player rows
        # in this tenant first" idiom rather than an inline subquery - see
        # ADR 0049.
        player_ids = (
            (
                await session.execute(
                    select(Player.id).where(
                        Player.user_id == user.id, Player.tenant_id == tenant_id
                    )
                )
            )
            .scalars()
            .all()
        )
        stmt = stmt.where(Character.owner_player_id.in_(player_ids))
    stmt = stmt.options(_name_eager_load).order_by(Character.entity_id)

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
    tenant_id: uuid.UUID, character_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> CharacterOut:
    await _require_tenant_member(session, tenant_id=tenant_id, user=user)
    return await _character_out(tenant_id, character_id, session)


@router.get("/{character_id}/groups")
async def list_character_groups(
    tenant_id: uuid.UUID, character_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[EntitySummary]:
    """ADR 0045's nice-to-have: the reverse of GET /tenants/{tenant_id}/
    groups/{group_entity_id}/members - which groups this character belongs
    to, sparing a client from fetching every tenant group and
    cross-referencing membership client-side. Gated the same way as this
    router's other two pre-existing GET routes (_require_tenant_member),
    not routers/groups.py's own broader is_tenant_participant - consistency
    with this router's own neighbors, not with groups.py.
    """
    await _require_tenant_member(session, tenant_id=tenant_id, user=user)
    await _get_character_or_404(tenant_id, character_id, session)

    stmt = (
        select(Entity)
        .join(GroupMember, GroupMember.group_entity_id == Entity.id)
        .where(GroupMember.character_entity_id == character_id, GroupMember.tenant_id == tenant_id)
        .order_by(Entity.id)
    )
    groups = (await session.execute(stmt)).scalars().all()
    return [EntitySummary.from_entity(group) for group in groups]


async def _get_character_or_404(
    tenant_id: uuid.UUID, character_id: uuid.UUID, session: SessionDep
) -> Character:
    stmt = select(Character).where(
        Character.entity_id == character_id, Character.tenant_id == tenant_id
    )
    character = (await session.execute(stmt)).scalar_one_or_none()
    if character is None:
        raise CharacterNotFoundError(
            detail=f"No character with id {character_id} in tenant {tenant_id}"
        )
    return character


async def _get_being_or_404(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep
) -> Being:
    """PUT /{character_id} targets a `being`, not necessarily one already
    promoted to `character` - CharacterNotFoundError also covers "no being
    at all here", the same non-enumerable collapsing every other not-found
    condition in this codebase already does (ADR 0031/RFC 0004).
    """
    stmt = select(Being).where(Being.entity_id == entity_id, Being.tenant_id == tenant_id)
    being = (await session.execute(stmt)).scalar_one_or_none()
    if being is None:
        raise CharacterNotFoundError(detail=f"No being with id {entity_id} in tenant {tenant_id}")
    return being


async def _character_out(
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


# --- Self-or-managed authorization (ADR 0036/RFC 0007) --------------------
#
# Three genuinely different "managed" tiers, each consuming its own
# campaign_access.py predicate - deliberately not one shared helper, so
# none of the three can quietly re-broaden or narrow another:
#
# - _authorize_roster_touch: writes that add, remove, or reassign one or
#   more *specific* Player rows (CharacterCreate's player_ids/
#   owner_player_id, a CharacterPromote/CharacterUpdate owner
#   reassignment, and the roster sub-resource PUT/DELETE's own {player_id})
#   - can_manage_campaign on every campaign among the touched Player rows
#   specifically ("no more and no less"), falling back to
#   can_manage_any_campaign_in_tenant when there's nothing to scope the
#   check to at all (an ownerless NPC, or clearing owner_player_id).
# - _authorize_rename: a PATCH that touches only `name` - can_manage_campaign
#   on any *one* of the character's current campaigns (RFC 0005's identical
#   "already uniformly visible everywhere it's rostered" reasoning).
# - _authorize_demote: DELETE - can_manage_campaign on *every* campaign the
#   character currently belongs to, since demotion ends its presence
#   everywhere at once.
#
# Self-service differs between these two families too. The first three
# writes (create/promote/roster-link) reference specific Player rows of
# their own, so self-ness is "every referenced id is a Player row the
# caller holds" - checked directly. Rename and demote reference no player
# id of their own; self-ness there reuses controlled_character_entity_ids
# directly (entity_access.py) - "does the caller directly control this
# character via their own Player rows" - per this RFC's own explicit
# reuse of that predicate rather than re-deriving it.


async def _caller_player_ids(
    session: SessionDep, *, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    stmt = select(Player.id).where(Player.user_id == user_id, Player.tenant_id == tenant_id)
    return frozenset((await session.execute(stmt)).scalars().all())


async def _require_players_exist(
    session: SessionDep, *, player_ids: frozenset[uuid.UUID], tenant_id: uuid.UUID
) -> frozenset[uuid.UUID]:
    """Validates every given player id is a real Player row in this tenant
    (404 otherwise) and returns the set of campaigns those rows belong to
    (campaign_access.campaign_ids_for_players) - shared by every write below
    that references player_ids/owner_player_id, so a body (or roster
    sub-resource URL) referencing a nonexistent player_id fails clearly,
    before any authorization tier is even evaluated.
    """
    if not player_ids:
        return frozenset()
    found_ids = frozenset(
        (
            await session.execute(
                select(Player.id).where(Player.id.in_(player_ids), Player.tenant_id == tenant_id)
            )
        )
        .scalars()
        .all()
    )
    missing = player_ids - found_ids
    if missing:
        raise PlayerNotFoundError(
            detail=f"No player with id {sorted(missing, key=str)[0]} in tenant {tenant_id}"
        )
    return await campaign_ids_for_players(session, player_ids=player_ids, tenant_id=tenant_id)


async def _authorize_roster_touch(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    touched_player_ids: frozenset[uuid.UUID],
) -> None:
    campaign_ids = await _require_players_exist(
        session, player_ids=touched_player_ids, tenant_id=tenant_id
    )
    caller_player_ids = await _caller_player_ids(session, user_id=user.id, tenant_id=tenant_id)
    if touched_player_ids and touched_player_ids <= caller_player_ids:
        return
    if touched_player_ids:
        if await can_manage_every_campaign(
            session, user_id=user.id, campaign_ids=campaign_ids, tenant_id=tenant_id
        ):
            return
    elif await can_manage_any_campaign_in_tenant(session, user_id=user.id, tenant_id=tenant_id):
        return
    raise CharacterManagementForbiddenError(
        detail="Not authorized to manage this character's roster"
    )


async def _authorize_rename(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, character_id: uuid.UUID
) -> None:
    controlled = await controlled_character_entity_ids(
        session, user_id=user.id, tenant_id=tenant_id
    )
    if character_id in controlled:
        return
    campaign_ids = await campaign_ids_for_character(
        session, character_entity_id=character_id, tenant_id=tenant_id
    )
    if campaign_ids:
        if await can_manage_any_of_campaigns(
            session, user_id=user.id, campaign_ids=campaign_ids, tenant_id=tenant_id
        ):
            return
    elif await can_manage_any_campaign_in_tenant(session, user_id=user.id, tenant_id=tenant_id):
        return
    raise CharacterManagementForbiddenError(
        detail=f"Not authorized to manage character {character_id}"
    )


async def _authorize_demote(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, character_id: uuid.UUID
) -> None:
    controlled = await controlled_character_entity_ids(
        session, user_id=user.id, tenant_id=tenant_id
    )
    if character_id in controlled:
        return
    campaign_ids = await campaign_ids_for_character(
        session, character_entity_id=character_id, tenant_id=tenant_id
    )
    if campaign_ids:
        if await can_manage_every_campaign(
            session, user_id=user.id, campaign_ids=campaign_ids, tenant_id=tenant_id
        ):
            return
    elif await can_manage_any_campaign_in_tenant(session, user_id=user.id, tenant_id=tenant_id):
        return
    raise CharacterManagementForbiddenError(
        detail=f"Not authorized to manage character {character_id}"
    )


@router.post("", status_code=201)
async def create_character(
    tenant_id: uuid.UUID,
    body: CharacterCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> CharacterOut:
    """One transaction creates Entity + Being + Character + one
    CharacterPlayer row per touched player id - owner_player_id is always
    folded into the roster too, if given and not already present (ADR
    0036/RFC 0007).
    """
    roster_player_ids: set[uuid.UUID] = set(body.player_ids)
    if body.owner_player_id is not None:
        roster_player_ids.add(body.owner_player_id)
    touched = frozenset(roster_player_ids)

    await _authorize_roster_touch(
        session, tenant_id=tenant_id, user=user, touched_player_ids=touched
    )

    entity = Entity(tenant_id=tenant_id, name=body.name, created_by=user.id, updated_by=user.id)
    session.add(entity)
    await session.flush()
    session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
    await session.flush()
    session.add(
        Character(
            entity_id=entity.id,
            tenant_id=tenant_id,
            owner_player_id=body.owner_player_id,
            created_by=user.id,
            updated_by=user.id,
        )
    )
    await session.flush()
    for player_id in roster_player_ids:
        session.add(
            CharacterPlayer(character_entity_id=entity.id, player_id=player_id, tenant_id=tenant_id)
        )

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_character", tenant_id=tenant_id, character_id=entity.id)
    )
    return await _character_out(tenant_id, entity.id, session)


@router.put("/{character_id}")
async def promote_character(
    tenant_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterPromote,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> CharacterOut:
    """Promotes an existing `being` into a character - idempotent, not
    one-shot: `201` the first time (no Character row existed yet), `200` on
    any later call (ADR 0036/RFC 0007). The first call sets
    `character.created_by`/`updated_by` to the promoter; `entity.created_by`
    keeps whatever it already was, from whenever the being was originally
    made - a repeat call only ever touches `character.updated_by`, never
    `entity`'s own columns.
    """
    await _get_being_or_404(tenant_id, character_id, session)
    entity = await get_entity_or_404(session, character_id, tenant_id)
    check_if_match(if_match, updated_at=entity.updated_at)
    existing = await session.get(Character, character_id)

    touched = frozenset({body.owner_player_id}) if body.owner_player_id is not None else frozenset()
    await _authorize_roster_touch(
        session, tenant_id=tenant_id, user=user, touched_player_ids=touched
    )

    if existing is None:
        session.add(
            Character(
                entity_id=character_id,
                tenant_id=tenant_id,
                owner_player_id=body.owner_player_id,
                created_by=user.id,
                updated_by=user.id,
            )
        )
        response.status_code = 201
        response.headers["Location"] = str(
            request.url_for("get_character", tenant_id=tenant_id, character_id=character_id)
        )
    else:
        existing.owner_player_id = body.owner_player_id
        existing.updated_by = user.id

    await session.flush()
    if body.owner_player_id is not None:
        link = await session.get(CharacterPlayer, (character_id, body.owner_player_id))
        if link is None:
            session.add(
                CharacterPlayer(
                    character_entity_id=character_id,
                    player_id=body.owner_player_id,
                    tenant_id=tenant_id,
                )
            )

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _character_out(tenant_id, character_id, session)


@router.patch("/{character_id}")
async def update_character(
    tenant_id: uuid.UUID,
    character_id: uuid.UUID,
    body: CharacterUpdate,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> CharacterOut:
    """Rename and/or reassign owner_player_id - which "managed" tier applies
    depends on what's actually changing (ADR 0036/RFC 0007). `name` lives on
    the underlying Entity (character.being.entity.name), so a rename touches
    entity.name/updated_by, not any Character column; reassigning
    owner_player_id touches character.owner_player_id/updated_by (and folds
    the new owner into the roster too, if not already present) but never
    entity's own columns.
    """
    character = await _get_character_or_404(tenant_id, character_id, session)
    entity = await get_entity_or_404(session, character_id, tenant_id)
    check_if_match(if_match, updated_at=entity.updated_at)

    update = body.model_dump(exclude_unset=True)
    reassigning_owner = (
        "owner_player_id" in update and update["owner_player_id"] != character.owner_player_id
    )

    if reassigning_owner:
        new_owner = update["owner_player_id"]
        touched = frozenset({new_owner}) if new_owner is not None else frozenset()
        await _authorize_roster_touch(
            session, tenant_id=tenant_id, user=user, touched_player_ids=touched
        )
    else:
        await _authorize_rename(session, tenant_id=tenant_id, user=user, character_id=character_id)

    if "name" in update:
        entity.name = update["name"]
        entity.updated_by = user.id

    if reassigning_owner:
        new_owner = update["owner_player_id"]
        character.owner_player_id = new_owner
        character.updated_by = user.id
        if new_owner is not None:
            link = await session.get(CharacterPlayer, (character_id, new_owner))
            if link is None:
                session.add(
                    CharacterPlayer(
                        character_entity_id=character_id, player_id=new_owner, tenant_id=tenant_id
                    )
                )

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await _character_out(tenant_id, character_id, session)


@router.delete("/{character_id}", status_code=204)
async def delete_character(
    tenant_id: uuid.UUID,
    character_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Demotes - deletes only the `character` row (CharacterPlayer/
    GroupMember rows referencing it cascade away with it); `being`/`entity`
    survive untouched, along with anything the character owned, contained,
    or knew (ADR 0036/RFC 0007, resolving ADR 0031/RFC 0004's own open
    question). Authorization uses the every-campaign tier: demotion ends
    the character's presence everywhere it's rostered at once.
    """
    character = await _get_character_or_404(tenant_id, character_id, session)
    entity = await get_entity_or_404(session, character_id, tenant_id)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_demote(session, tenant_id=tenant_id, user=user, character_id=character_id)

    await session.delete(character)
    await session.commit()


@router.put("/{character_id}/players/{player_id}")
async def add_character_player(
    tenant_id: uuid.UUID,
    character_id: uuid.UUID,
    player_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> CharacterOut:
    """Roster link as its own sub-resource - idempotent, mirroring
    grant_campaign_gm/set_item_instance_owner's own "no row means no
    relation, PUT creates it" shape (ADR 0036/RFC 0007).
    """
    await _get_character_or_404(tenant_id, character_id, session)
    entity = await get_entity_or_404(session, character_id, tenant_id)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_roster_touch(
        session, tenant_id=tenant_id, user=user, touched_player_ids=frozenset({player_id})
    )

    existing = await session.get(CharacterPlayer, (character_id, player_id))
    if existing is None:
        session.add(
            CharacterPlayer(
                character_entity_id=character_id, player_id=player_id, tenant_id=tenant_id
            )
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _character_out(tenant_id, character_id, session)


@router.delete("/{character_id}/players/{player_id}")
async def remove_character_player(
    tenant_id: uuid.UUID,
    character_id: uuid.UUID,
    player_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> CharacterOut:
    """200 + the parent character, not 204 - removing one roster link leaves
    the character itself intact (ADR 0032/RFC 0005's own singular
    sub-resource shape, reused here for a genuinely n:m one).
    """
    await _get_character_or_404(tenant_id, character_id, session)
    entity = await get_entity_or_404(session, character_id, tenant_id)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _authorize_roster_touch(
        session, tenant_id=tenant_id, user=user, touched_player_ids=frozenset({player_id})
    )

    existing = await session.get(CharacterPlayer, (character_id, player_id))
    if existing is not None:
        await session.delete(existing)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await _character_out(tenant_id, character_id, session)
