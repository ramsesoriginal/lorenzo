from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from fastapi_problem.error import Problem
from sqlalchemy import delete, select

from lorenzo_api.campaign_access import can_manage_character
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_entity_or_404,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    CharacterManagementForbiddenError,
    InvalidCharacterError,
    InvalidGroupMemberError,
    InvalidUserError,
)
from lorenzo_api.models import Character, Entity, GroupMember, User
from lorenzo_api.notifications import create_group_notification
from lorenzo_api.schemas.common import EntitySummary, ProblemOut
from lorenzo_api.schemas.groups import (
    DuplicateGroupRequest,
    GroupCreate,
    GroupMemberResultItem,
    GroupUpdate,
)
from lorenzo_api.schemas.notifications import NotificationCreate, NotificationOut

# get_tenant_or_404 here, not get_tenant_context - mirrors routers/
# item_instances.py's identical ADR 0032/RFC 0005 precedent: browsing
# groups to pick one as a knowledge-visibility target is exactly the kind
# of thing a plain player (no tenant-wide Membership row, ADR 0022) needs
# to do, not just a tenant admin.
router = APIRouter(
    prefix="/tenants/{tenant_id}/groups",
    tags=["groups"],
    dependencies=[Depends(get_tenant_or_404)],
)


@router.get("")
async def list_groups(
    tenant_id: uuid.UUID, params: ParamsDep, session: SessionDep, user: CurrentUser
) -> Page[EntitySummary]:
    """See ADR 0045: a group has no dedicated table (ADR 0028) - it's any
    entity that appears at least once as group_member.group_entity_id.
    An intentionally-created-but-still-empty group isn't enumerable this
    way, an accepted consequence of that data model, not a new gap.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    stmt = (
        select(Entity)
        .join(GroupMember, GroupMember.group_entity_id == Entity.id)
        .where(Entity.tenant_id == tenant_id)
        .distinct()
        .order_by(Entity.id)
    )

    def _groups_out(entities: Sequence[Entity]) -> list[EntitySummary]:
        return [EntitySummary.from_entity(entity) for entity in entities]

    # apaginate is typed to return Any (fastapi_pagination's own signature) -
    # cast rather than suppress, the declared return type is otherwise exact.
    return cast(
        Page[EntitySummary], await apaginate(session, stmt, params, transformer=_groups_out)
    )


@router.get("/{group_entity_id}")
async def get_group(
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> EntitySummary:
    """A group's own identity is just "an entity with a name" - the same
    lightweight shape list_groups already uses (ADR 0045), not the
    heavier generic GET /entities/{id}. See ADR 0064: needed as the
    Location target for create_group/duplicate_group below, and reused as
    update_group/delete_group's own response shape.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    entity = await get_entity_or_404(session, group_entity_id, tenant_id)
    response.headers["ETag"] = etag_for(entity.updated_at)
    return EntitySummary.from_entity(entity)


async def _group_members(
    session: SessionDep, *, tenant_id: uuid.UUID, group_entity_id: uuid.UUID
) -> list[Entity]:
    stmt = (
        select(Entity)
        .join(GroupMember, GroupMember.character_entity_id == Entity.id)
        .where(GroupMember.group_entity_id == group_entity_id, GroupMember.tenant_id == tenant_id)
        .order_by(Entity.id)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{group_entity_id}/members")
async def list_group_members(
    tenant_id: uuid.UUID, group_entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[EntitySummary]:
    """Not paginated - bounded by one group's membership, mirroring GET
    .../item-instances/owned-by/{owner_entity_id}'s identical precedent.

    404 only if group_entity_id isn't a real entity in this tenant at all;
    an empty list (not a 404) if it is one but currently has no members -
    unlike ADR 0040's item-instance precedent, a group's bare existence
    isn't a secret the way another character's inventory is, so there's no
    reason to hide that distinction here.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await get_entity_or_404(session, group_entity_id, tenant_id)
    members = await _group_members(session, tenant_id=tenant_id, group_entity_id=group_entity_id)
    return [EntitySummary.from_entity(member) for member in members]


async def _require_can_manage_group(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, group_entity_id: uuid.UUID
) -> None:
    """Every member of the group must be one the caller can manage
    (campaign_access.can_manage_character) - fail-closed, not a partial
    send: being authorized to message *some* but not all of a group's
    members doesn't authorize messaging the group as a whole (ADR 0059).
    An empty group trivially passes - there is nothing to be unauthorized
    for, matching list_group_members' own "empty, not a secret" stance.
    Reused as-is by every group-write route below (ADR 0064) that needs
    "does the caller have standing over this group at all" - renaming,
    deleting, removing a member, and duplicating (see duplicate_group's
    own docstring for why that one needs no separate per-member check).
    """
    member_ids = (
        await session.execute(
            select(GroupMember.character_entity_id).where(
                GroupMember.group_entity_id == group_entity_id, GroupMember.tenant_id == tenant_id
            )
        )
    ).scalars()
    for character_entity_id in member_ids:
        if not await can_manage_character(
            session, user_id=user.id, tenant_id=tenant_id, character_entity_id=character_entity_id
        ):
            raise CharacterManagementForbiddenError(
                detail=f"Not authorized to manage group {group_entity_id}"
            )


def _require_not_self_loop(*, group_entity_id: uuid.UUID, character_entity_id: uuid.UUID) -> None:
    """Pre-checked rather than left to surface as a raw
    group_member_no_self_loop CHECK violation - a real, reachable case
    since nothing stops an entity from independently acquiring both a
    group role and a Character row (RFC 0001). See ADR 0064. Not needed
    by create_group's own initial members: the new group's id is
    server-generated after the request body is already parsed, so a
    client-supplied character id can't collide with it.
    """
    if character_entity_id == group_entity_id:
        raise InvalidGroupMemberError(
            detail=f"{character_entity_id} cannot be a member of its own group"
        )


async def _authorize_add_member(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, character_entity_id: uuid.UUID
) -> None:
    """Adding character_entity_id as a *new* member needs a check
    _require_can_manage_group doesn't cover, since a not-yet-member isn't
    part of "every current member" (ADR 0064) - shared by create_group's
    initial members, add_group_member, and bulk_add_group_members so the
    three can't drift.
    """
    exists = (
        await session.execute(
            select(Character.entity_id).where(
                Character.entity_id == character_entity_id, Character.tenant_id == tenant_id
            )
        )
    ).first()
    if exists is None:
        raise InvalidCharacterError(
            detail=f"{character_entity_id} is not an existing character in tenant {tenant_id}"
        )
    if not await can_manage_character(
        session, user_id=user.id, tenant_id=tenant_id, character_entity_id=character_entity_id
    ):
        raise CharacterManagementForbiddenError(
            detail=f"Not authorized to manage character {character_entity_id}"
        )


async def _add_member_core(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    character_entity_id: uuid.UUID,
) -> None:
    """Idempotent - inserting an already-existing membership is a no-op,
    mirroring grant_campaign_gm's own idempotent PUT shape. No auth/
    validation here - see _authorize_add_member, run by every caller
    first.
    """
    existing = await session.get(GroupMember, (group_entity_id, character_entity_id))
    if existing is None:
        session.add(
            GroupMember(
                group_entity_id=group_entity_id,
                character_entity_id=character_entity_id,
                tenant_id=tenant_id,
            )
        )


@router.post("", status_code=201)
async def create_group(
    tenant_id: uuid.UUID,
    body: GroupCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> EntitySummary:
    """Creates a fresh bare Entity to serve as the group, plus one
    GroupMember row per id in member_character_ids - see ADR 0064. Gated
    by require_tenant_participant only: a brand-new, still-empty group is
    exactly as low-stakes to create as it already is to browse (ADR
    0045). Each initial member is individually validated/authorized by
    _authorize_add_member, same as adding one later - creating a group
    with members you don't control isn't a free pass just because the
    group itself is new. Duplicate ids in member_character_ids collapse
    silently (dict.fromkeys, order-preserving) rather than hitting
    GroupMember's own composite-PK violation as a bare 500.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    member_ids = list(dict.fromkeys(body.member_character_ids))
    for character_entity_id in member_ids:
        await _authorize_add_member(
            session, tenant_id=tenant_id, user=user, character_entity_id=character_entity_id
        )

    entity = Entity(tenant_id=tenant_id, name=body.name, created_by=user.id, updated_by=user.id)
    session.add(entity)
    await session.flush()
    for character_entity_id in member_ids:
        await _add_member_core(
            session,
            tenant_id=tenant_id,
            group_entity_id=entity.id,
            character_entity_id=character_entity_id,
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_group", tenant_id=tenant_id, group_entity_id=entity.id)
    )
    response.headers["ETag"] = etag_for(entity.updated_at)
    return EntitySummary.from_entity(entity)


@router.patch("/{group_entity_id}")
async def update_group(
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    body: GroupUpdate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntitySummary:
    """Rename only - a group has nothing else of its own to update. See
    ADR 0064.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    entity = await get_entity_or_404(session, group_entity_id, tenant_id)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _require_can_manage_group(
        session, tenant_id=tenant_id, user=user, group_entity_id=group_entity_id
    )

    update = body.model_dump(exclude_unset=True)
    if "name" in update:
        entity.name = update["name"]
        entity.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    entity = await get_entity_or_404(session, group_entity_id, tenant_id)
    response.headers["ETag"] = etag_for(entity.updated_at)
    return EntitySummary.from_entity(entity)


@router.delete("/{group_entity_id}", status_code=204)
async def delete_group(
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Removes every GroupMember row naming this group - it stops being a
    group - but deliberately does not delete the underlying Entity: RFC
    0001 is explicit that nothing stops the same entity_id from playing
    more than one role, so an entity that was already something else
    before being used as a group must survive this. An entity created
    purely via create_group and later fully emptied this way is left an
    orphaned bare entity with no members and no other role - a real,
    accepted gap, not solved here (see ADR 0064). Idempotent - a group
    with zero members already is a no-op.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    entity = await get_entity_or_404(session, group_entity_id, tenant_id)
    check_if_match(if_match, updated_at=entity.updated_at)
    await _require_can_manage_group(
        session, tenant_id=tenant_id, user=user, group_entity_id=group_entity_id
    )

    await session.execute(
        delete(GroupMember).where(
            GroupMember.group_entity_id == group_entity_id, GroupMember.tenant_id == tenant_id
        )
    )
    await session.commit()


@router.post("/{group_entity_id}/members/bulk")
async def bulk_add_group_members(
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    body: list[uuid.UUID],
    session: SessionDep,
    user: CurrentUser,
) -> list[GroupMemberResultItem]:
    """Adds several characters to a group in one call - see ADR 0064.
    _require_can_manage_group is checked **once**, up front - it doesn't
    vary per item, the same reasoning ADR 0062's own up-front
    _require_owner check gives. Existence, the self-loop guard, and
    can_manage_character *do* vary per item, so each runs inside its own
    session.begin_nested() (a SQL SAVEPOINT) - the exact
    bulk_assign_item_instances/bulk_create_memberships pattern (ADR
    0044/0062): never all-or-nothing, a caught Problem becomes that
    item's own "error" entry, everything else already applied proceeds to
    the one shared commit.

    Registered *before* /{group_entity_id}/members/{character_entity_id}
    below - "bulk" would fail that route's UUID path converter anyway,
    but registering the more specific literal path first matches this
    codebase's established defensive convention (routers/item_
    instances.py's /owned-by and /by-slug precedent) rather than relying
    on that converter behavior alone.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await get_entity_or_404(session, group_entity_id, tenant_id)
    await _require_can_manage_group(
        session, tenant_id=tenant_id, user=user, group_entity_id=group_entity_id
    )

    results: list[GroupMemberResultItem] = []
    for character_entity_id in body:
        try:
            async with session.begin_nested():
                _require_not_self_loop(
                    group_entity_id=group_entity_id, character_entity_id=character_entity_id
                )
                await _authorize_add_member(
                    session,
                    tenant_id=tenant_id,
                    user=user,
                    character_entity_id=character_entity_id,
                )
                await _add_member_core(
                    session,
                    tenant_id=tenant_id,
                    group_entity_id=group_entity_id,
                    character_entity_id=character_entity_id,
                )
        except Problem as exc:
            results.append(
                GroupMemberResultItem(
                    character_entity_id=character_entity_id,
                    status="error",
                    problem=ProblemOut(**exc.marshal()),
                )
            )
            continue
        results.append(GroupMemberResultItem(character_entity_id=character_entity_id, status="ok"))

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return results


@router.put("/{group_entity_id}/members/{character_entity_id}")
async def add_group_member(
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    character_entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> list[EntitySummary]:
    """Idempotent add - a re-PUT of an existing membership is a no-op,
    mirroring grant_campaign_gm's exact shape. See ADR 0064. Returns the
    group's full, updated member list (list_group_members' own shape) -
    more immediately useful than a bare parent reference, and the caller
    already knows this shape from GET .../members.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await get_entity_or_404(session, group_entity_id, tenant_id)
    await _require_can_manage_group(
        session, tenant_id=tenant_id, user=user, group_entity_id=group_entity_id
    )
    _require_not_self_loop(group_entity_id=group_entity_id, character_entity_id=character_entity_id)
    await _authorize_add_member(
        session, tenant_id=tenant_id, user=user, character_entity_id=character_entity_id
    )

    await _add_member_core(
        session,
        tenant_id=tenant_id,
        group_entity_id=group_entity_id,
        character_entity_id=character_entity_id,
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    members = await _group_members(session, tenant_id=tenant_id, group_entity_id=group_entity_id)
    return [EntitySummary.from_entity(member) for member in members]


@router.delete("/{group_entity_id}/members/{character_entity_id}")
async def remove_group_member(
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    character_entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> list[EntitySummary]:
    """Idempotent remove - already covered by _require_can_manage_group
    alone, since the member being removed is by definition a *current*
    member. See ADR 0064.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await get_entity_or_404(session, group_entity_id, tenant_id)
    await _require_can_manage_group(
        session, tenant_id=tenant_id, user=user, group_entity_id=group_entity_id
    )

    existing = await session.get(GroupMember, (group_entity_id, character_entity_id))
    if existing is not None:
        await session.delete(existing)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    members = await _group_members(session, tenant_id=tenant_id, group_entity_id=group_entity_id)
    return [EntitySummary.from_entity(member) for member in members]


@router.post("/{group_entity_id}/duplicate", status_code=201)
async def duplicate_group(
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    body: DuplicateGroupRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> EntitySummary:
    """Copies group_entity_id's entire current roster into a fresh group -
    see ADR 0064. _require_can_manage_group against the *source* only:
    proving the caller can manage every one of its current members already
    authorizes copying that same set onto a new group, no separate
    per-member check needed on the copy. name defaults to the source's own
    name when omitted; an empty source produces an empty duplicate, not an
    error.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    source = await get_entity_or_404(session, group_entity_id, tenant_id)
    await _require_can_manage_group(
        session, tenant_id=tenant_id, user=user, group_entity_id=group_entity_id
    )
    member_ids = (
        (
            await session.execute(
                select(GroupMember.character_entity_id).where(
                    GroupMember.group_entity_id == group_entity_id,
                    GroupMember.tenant_id == tenant_id,
                )
            )
        )
        .scalars()
        .all()
    )

    new_entity = Entity(
        tenant_id=tenant_id,
        name=body.name if body.name is not None else source.name,
        created_by=user.id,
        updated_by=user.id,
    )
    session.add(new_entity)
    await session.flush()
    for character_entity_id in member_ids:
        session.add(
            GroupMember(
                group_entity_id=new_entity.id,
                character_entity_id=character_entity_id,
                tenant_id=tenant_id,
            )
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_group", tenant_id=tenant_id, group_entity_id=new_entity.id)
    )
    response.headers["ETag"] = etag_for(new_entity.updated_at)
    return EntitySummary.from_entity(new_entity)


@router.post("/{group_entity_id}/notifications", status_code=201)
async def create_group_notification_route(
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    body: NotificationCreate,
    session: SessionDep,
    user: CurrentUser,
) -> list[NotificationOut]:
    """scope="group" - see ADR 0059. An omitted `recipient_user_id`
    broadcasts to every player controlling any member character (roster
    reuse across every member at once, ADR 0025), so this can return more
    than one row.
    """
    await get_entity_or_404(session, group_entity_id, tenant_id)
    await _require_can_manage_group(
        session, tenant_id=tenant_id, user=user, group_entity_id=group_entity_id
    )
    if (
        body.recipient_user_id is not None
        and await session.get(User, body.recipient_user_id) is None
    ):
        raise InvalidUserError(detail=f"{body.recipient_user_id} is not an existing user")

    notifications = await create_group_notification(
        session,
        tenant_id=tenant_id,
        group_entity_id=group_entity_id,
        recipient_user_id=body.recipient_user_id,
        type=body.type,
        title=body.title,
        body=body.body,
        created_by=user.id,
    )
    await session.commit()
    return [NotificationOut.model_validate(n) for n in notifications]
