"""Group mutations are recorded in the activity log - see ADR 0084. Only
real changes are logged: a repeated idempotent add/remove, a bulk call that
adds nobody, and re-retiring an empty group all write nothing. Renames are
deliberately not logged.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_player, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog, CharacterPlayer, User


async def _entries(tenant_id: uuid.UUID) -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like("group.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(action, detail) for action, detail in rows]


async def _make_characters(
    tenant_id: uuid.UUID, count: int
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """`count` characters rostered into one campaign, so the tenant OWNER can
    manage them (`can_manage_character`). Returns (character entity ids,
    throwaway player user ids for the caller to delete).
    """
    character_ids: list[uuid.UUID] = []
    user_ids: list[uuid.UUID] = []
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        for _ in range(count):
            player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
            character = await make_character(
                session, tenant_id=tenant_id, owner_player_id=player.id
            )
            session.add(
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player.id,
                    tenant_id=tenant_id,
                )
            )
            character_ids.append(character.entity_id)
            user_ids.append(player.user_id)
        await session.commit()
    return character_ids, user_ids


async def _delete_users(user_ids: list[uuid.UUID]) -> None:
    async with admin_session_factory() as session:
        for user_id in user_ids:
            await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_group_lifecycle_logs_only_real_changes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    (c1, c2), user_ids = await _make_characters(tenant_id, 2)
    base = f"/tenants/{tenant_id}/groups"

    created = await client.post(base, json={"name": "The Party", "member_character_ids": [str(c1)]})
    assert created.status_code == 201, created.text
    group_id = created.json()["id"]

    member = f"{base}/{group_id}/members/{c2}"
    assert (await client.put(member)).status_code == 200
    assert (await client.put(member)).status_code == 200  # idempotent: no second entry
    assert (await client.delete(member)).status_code == 200
    assert (await client.delete(member)).status_code == 200  # idempotent: no second entry

    bulk = await client.post(f"{base}/{group_id}/members/bulk", json=[str(c2), str(uuid.uuid4())])
    assert bulk.status_code == 200, bulk.text
    again = await client.post(f"{base}/{group_id}/members/bulk", json=[str(c2)])
    assert again.status_code == 200  # nobody newly added: no second entry

    renamed = await client.patch(f"{base}/{group_id}", json={"name": "Renamed"})
    assert renamed.status_code == 200

    duplicate = await client.post(f"{base}/{group_id}/duplicate", json={"name": "Copy"})
    assert duplicate.status_code == 201, duplicate.text
    copy_id = duplicate.json()["id"]

    assert (await client.delete(f"{base}/{group_id}")).status_code == 204
    assert (await client.delete(f"{base}/{group_id}")).status_code == 204  # already empty: no entry

    assert await _entries(tenant_id) == [
        ("group.created", "members=1"),
        ("group.member_added", f"character={c2}"),
        ("group.member_removed", f"character={c2}"),
        ("group.members_bulk_added", "1 added, 1 failed"),
        ("group.duplicated", f"source={group_id}, members=2"),
        ("group.deleted", "members_removed=2"),
    ]
    assert copy_id != group_id

    await delete_tenant(tenant_id)
    await _delete_users(user_ids)
