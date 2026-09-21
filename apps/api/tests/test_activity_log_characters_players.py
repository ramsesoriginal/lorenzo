"""Character and player mutations are recorded in the activity log - see
ADR 0084. Only real changes are logged (a repeated idempotent roster PUT
writes nothing), and renames are deliberately not logged.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog, Player, User


async def _entries(tenant_id: uuid.UUID) -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(
                    AuditLog.tenant_id == tenant_id,
                    AuditLog.action.like("character.%") | AuditLog.action.like("player.%"),
                )
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(action, detail) for action, detail in rows]


async def _make_user() -> uuid.UUID:
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"authgear|log-player-{uuid.uuid4()}")
        session.add(user)
        await session.commit()
        return user.id


async def _delete_users(*user_ids: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        for user_id in user_ids:
            await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def _make_campaign(client: AsyncClient, tenant_id: uuid.UUID) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={
            "name": "Roster",
            "game_system": "D&D 5e",
            "slug": f"roster-{uuid.uuid4()}",
            "description": "",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def _add_player(
    client: AsyncClient, tenant_id: uuid.UUID, campaign_id: str, user_id: uuid.UUID
) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players", json={"user_id": str(user_id)}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_character_and_roster_lifecycle_is_logged(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _make_campaign(client, tenant_id)
    user_a, user_b = await _make_user(), await _make_user()
    player_a = await _add_player(client, tenant_id, campaign_id, user_a)
    player_b = await _add_player(client, tenant_id, campaign_id, user_b)
    base = f"/tenants/{tenant_id}/characters"

    created = await client.post(base, json={"name": "Alice", "owner_player_id": player_a})
    assert created.status_code == 201, created.text
    character_id = created.json()["entity_id"]

    link = f"{base}/{character_id}/players/{player_b}"
    assert (await client.put(link)).status_code == 200
    assert (await client.put(link)).status_code == 200  # idempotent: no second entry
    assert (await client.delete(link)).status_code == 200
    assert (await client.delete(link)).status_code == 200  # idempotent: no second entry

    assert (
        await client.patch(f"{base}/{character_id}", json={"name": "Renamed"})
    ).status_code == 200

    reassign = await client.patch(f"{base}/{character_id}", json={"owner_player_id": player_b})
    assert reassign.status_code == 200, reassign.text
    same = await client.patch(f"{base}/{character_id}", json={"owner_player_id": player_b})
    assert same.status_code == 200  # owner unchanged: no second entry

    assert (await client.delete(f"{base}/{character_id}")).status_code == 204

    assert await _entries(tenant_id) == [
        ("player.added", f"user={user_a}"),
        ("player.added", f"user={user_b}"),
        ("character.created", "players=1"),
        ("character.player_linked", f"player={player_b}"),
        ("character.player_unlinked", f"player={player_b}"),
        ("character.owner_changed", f"owner_player={player_b}"),
        ("character.demoted", None),
    ]

    await delete_tenant(tenant_id)
    await _delete_users(user_a, user_b)


async def test_promoting_a_being_is_logged_once_then_only_owner_changes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _make_campaign(client, tenant_id)
    user_a, user_b = await _make_user(), await _make_user()
    player_a = await _add_player(client, tenant_id, campaign_id, user_a)
    player_b = await _add_player(client, tenant_id, campaign_id, user_b)
    async with admin_session_factory() as session:
        being = await make_being(session, tenant_id=tenant_id)
        await session.commit()
        being_id = being.entity_id
    url = f"/tenants/{tenant_id}/characters/{being_id}"

    assert (await client.put(url, json={"owner_player_id": player_a})).status_code == 201
    assert (await client.put(url, json={"owner_player_id": player_a})).status_code == 200
    assert (await client.put(url, json={"owner_player_id": player_b})).status_code == 200

    entries = (await _entries(tenant_id))[2:]  # after the two player.added entries
    assert entries == [
        ("character.promoted", f"owner_player={player_a}"),
        ("character.owner_changed", f"owner_player={player_b}"),
    ]

    await delete_tenant(tenant_id)
    await _delete_users(user_a, user_b)


async def test_removing_and_leaving_a_campaign_seat_are_told_apart(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _make_campaign(client, tenant_id)
    user_a = await _make_user()
    player_a = await _add_player(client, tenant_id, campaign_id, user_a)

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_a}"
    )
    assert response.status_code == 204

    assert (await _entries(tenant_id))[-1] == ("player.removed", f"removed, user={user_a}")

    await delete_tenant(tenant_id)
    await _delete_users(user_a)


async def test_leaving_your_own_campaign_seat_is_recorded_as_left(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        campaign_id, player_id = campaign.id, player.id

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}"
    )
    assert response.status_code == 204

    assert await _entries(tenant_id) == [("player.removed", f"left, user={test_user_id}")]

    await delete_tenant(tenant_id)
