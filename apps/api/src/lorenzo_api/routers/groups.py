from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, Depends
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from lorenzo_api.campaign_access import can_manage_character
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_entity_or_404,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.exceptions import CharacterManagementForbiddenError, InvalidUserError
from lorenzo_api.models import Entity, GroupMember, User
from lorenzo_api.notifications import create_group_notification
from lorenzo_api.schemas.common import EntitySummary
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

    stmt = (
        select(Entity)
        .join(GroupMember, GroupMember.character_entity_id == Entity.id)
        .where(GroupMember.group_entity_id == group_entity_id, GroupMember.tenant_id == tenant_id)
        .order_by(Entity.id)
    )
    members = (await session.execute(stmt)).scalars().all()
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
