"""Shared notification fan-out logic for the five scopes - see ADR 0058/0059.

Every function here does core mechanics only - no auth, no commit
(matching routers/item_instances.py's own `_perform_split` precedent) -
each POST .../notifications route calls one of these, then commits itself.
Fanned out at creation (one row per recipient), never resolved at read
time - see ADR 0058's own reasoning.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    CampaignGm,
    CharacterPlayer,
    GroupMember,
    Membership,
    Notification,
    Player,
)


def _build(
    *,
    batch_id: uuid.UUID,
    user_id: uuid.UUID,
    tenant_id: uuid.UUID | None,
    scope: str,
    source_id: uuid.UUID | None,
    type: str,
    title: str,
    body: str,
    created_by: uuid.UUID | None,
) -> Notification:
    return Notification(
        batch_id=batch_id,
        user_id=user_id,
        tenant_id=tenant_id,
        scope=scope,
        source_id=source_id,
        type=type,
        title=title,
        body=body,
        created_by=created_by,
    )


async def _tenant_roster_user_ids(session: AsyncSession, *, tenant_id: uuid.UUID) -> set[uuid.UUID]:
    """The same Membership+Player+CampaignGm union `list_tenant_roster`
    (routers/tenants.py) already computes - every user with any standing
    in this tenant.
    """
    membership_ids = (
        await session.execute(select(Membership.user_id).where(Membership.tenant_id == tenant_id))
    ).scalars()
    player_ids = (
        await session.execute(select(Player.user_id).where(Player.tenant_id == tenant_id))
    ).scalars()
    gm_ids = (
        await session.execute(select(CampaignGm.user_id).where(CampaignGm.tenant_id == tenant_id))
    ).scalars()
    return set(membership_ids) | set(player_ids) | set(gm_ids)


async def create_tenant_notification(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    recipient_user_id: uuid.UUID | None,
    type: str,
    title: str,
    body: str,
    created_by: uuid.UUID | None,
) -> list[Notification]:
    """scope="tenant". An omitted `recipient_user_id` broadcasts to the
    tenant's full roster. Every row shares one `batch_id` (ADR 0061), so
    the sender can later pull the whole broadcast's read state in one
    query (`GET /me/notifications/sent?batch_id=...`).
    """
    recipient_ids = (
        {recipient_user_id}
        if recipient_user_id is not None
        else await _tenant_roster_user_ids(session, tenant_id=tenant_id)
    )
    batch_id = uuid.uuid4()
    notifications = [
        _build(
            batch_id=batch_id,
            user_id=user_id,
            tenant_id=tenant_id,
            scope="tenant",
            source_id=None,
            type=type,
            title=title,
            body=body,
            created_by=created_by,
        )
        for user_id in recipient_ids
    ]
    session.add_all(notifications)
    return notifications


async def create_campaign_notification(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    recipient_user_id: uuid.UUID | None,
    type: str,
    title: str,
    body: str,
    created_by: uuid.UUID | None,
) -> list[Notification]:
    """scope="campaign". An omitted `recipient_user_id` broadcasts to that
    campaign's Player + CampaignGm rows.
    """
    if recipient_user_id is not None:
        recipient_ids = {recipient_user_id}
    else:
        player_ids = (
            await session.execute(
                select(Player.user_id).where(
                    Player.campaign_id == campaign_id, Player.tenant_id == tenant_id
                )
            )
        ).scalars()
        gm_ids = (
            await session.execute(
                select(CampaignGm.user_id).where(
                    CampaignGm.campaign_id == campaign_id, CampaignGm.tenant_id == tenant_id
                )
            )
        ).scalars()
        recipient_ids = set(player_ids) | set(gm_ids)

    batch_id = uuid.uuid4()
    notifications = [
        _build(
            batch_id=batch_id,
            user_id=user_id,
            tenant_id=tenant_id,
            scope="campaign",
            source_id=campaign_id,
            type=type,
            title=title,
            body=body,
            created_by=created_by,
        )
        for user_id in recipient_ids
    ]
    session.add_all(notifications)
    return notifications


async def create_character_notification(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    character_entity_id: uuid.UUID,
    recipient_user_id: uuid.UUID | None,
    type: str,
    title: str,
    body: str,
    created_by: uuid.UUID | None,
) -> list[Notification]:
    """scope="character". An omitted `recipient_user_id` broadcasts to
    every player controlling this character via `CharacterPlayer` (roster
    reuse, ADR 0025) - a character rostered into two campaigns notifies
    every player controlling it in either.
    """
    if recipient_user_id is not None:
        recipient_ids = {recipient_user_id}
    else:
        stmt = (
            select(Player.user_id)
            .join(CharacterPlayer, CharacterPlayer.player_id == Player.id)
            .where(CharacterPlayer.character_entity_id == character_entity_id)
        )
        recipient_ids = set((await session.execute(stmt)).scalars())

    batch_id = uuid.uuid4()
    notifications = [
        _build(
            batch_id=batch_id,
            user_id=user_id,
            tenant_id=tenant_id,
            scope="character",
            source_id=character_entity_id,
            type=type,
            title=title,
            body=body,
            created_by=created_by,
        )
        for user_id in recipient_ids
    ]
    session.add_all(notifications)
    return notifications


async def create_group_notification(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    group_entity_id: uuid.UUID,
    recipient_user_id: uuid.UUID | None,
    type: str,
    title: str,
    body: str,
    created_by: uuid.UUID | None,
) -> list[Notification]:
    """scope="group" - see ADR 0059. A group's members are always
    characters (`GroupMember.character_entity_id`, ADR 0028) - an omitted
    `recipient_user_id` broadcasts to every player controlling *any*
    member character via `CharacterPlayer` (the same roster-reuse join
    `create_character_notification` uses for one character, extended to
    every member at once).
    """
    if recipient_user_id is not None:
        recipient_ids = {recipient_user_id}
    else:
        stmt = (
            select(Player.user_id)
            .join(CharacterPlayer, CharacterPlayer.player_id == Player.id)
            .join(
                GroupMember, GroupMember.character_entity_id == CharacterPlayer.character_entity_id
            )
            .where(
                GroupMember.group_entity_id == group_entity_id, GroupMember.tenant_id == tenant_id
            )
        )
        recipient_ids = set((await session.execute(stmt)).scalars())

    batch_id = uuid.uuid4()
    notifications = [
        _build(
            batch_id=batch_id,
            user_id=user_id,
            tenant_id=tenant_id,
            scope="group",
            source_id=group_entity_id,
            type=type,
            title=title,
            body=body,
            created_by=created_by,
        )
        for user_id in recipient_ids
    ]
    session.add_all(notifications)
    return notifications


def create_platform_notification(
    *, recipient_user_id: uuid.UUID, type: str, title: str, body: str, created_by: uuid.UUID | None
) -> Notification:
    """scope="platform". Always single-recipient - see ADR 0058's own
    named non-goal (no broadcast-to-every-user mechanism yet). Still gets
    its own `batch_id` (ADR 0061), for consistency with the other four
    scopes even though it's always a batch of one.
    """
    return _build(
        batch_id=uuid.uuid4(),
        user_id=recipient_user_id,
        tenant_id=None,
        scope="platform",
        source_id=None,
        type=type,
        title=title,
        body=body,
        created_by=created_by,
    )
