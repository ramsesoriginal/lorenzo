"""The two player self-service switches (RFC 0034, ADR 0185): stored,
set by whoever manages the campaign, logged, and shown. Nothing reads them
yet, so there is no enforcement to test here.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_player, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog, Player, User


async def _campaign_with_player(owner_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A tenant owned by owner_id with one campaign and one other player."""
    tenant_id = await make_tenant(owner_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        await session.commit()
        return tenant_id, campaign.id, player.id


async def _entries(tenant_id: uuid.UUID, like: str) -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like(like))
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(action, detail) for action, detail in rows]


async def _delete_player_user(player_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        player = await session.get_one(Player, player_id)
        await session.delete(await session.get_one(User, player.user_id))
        await session.commit()


async def test_defaults_are_on_and_no_override(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id, player_id = await _campaign_with_player(test_user_id)

    campaign = (await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")).json()
    assert campaign["player_self_service"] is True
    roster = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}/players")
    [row] = roster.json()["items"]
    assert row["self_service"] is None
    assert row["self_service_effective"] is True

    await _delete_player_user(player_id)
    await delete_tenant(tenant_id)


async def test_campaign_setting_is_patched_and_flows_to_the_roster(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id, player_id = await _campaign_with_player(test_user_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}"

    patched = await client.patch(base, json={"player_self_service": False})
    assert patched.status_code == 200
    assert patched.json()["player_self_service"] is False

    [row] = (await client.get(f"{base}/players")).json()["items"]
    assert row["self_service"] is None
    assert row["self_service_effective"] is False
    detail = (await client.get(f"{base}/players/{player_id}")).json()
    assert detail["self_service_effective"] is False

    assert await _entries(tenant_id, "campaign.updated") == [
        ("campaign.updated", "fields=player_self_service")
    ]

    await _delete_player_user(player_id)
    await delete_tenant(tenant_id)


async def test_campaign_setting_cannot_be_null(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id, player_id = await _campaign_with_player(test_user_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}", json={"player_self_service": None}
    )
    assert response.status_code == 422
    campaign = (await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")).json()
    assert campaign["player_self_service"] is True

    await _delete_player_user(player_id)
    await delete_tenant(tenant_id)


async def test_player_override_is_set_overrides_and_is_cleared(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id, player_id = await _campaign_with_player(test_user_id)
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}"
    path = f"{base}/players/{player_id}"

    # Campaign on, player forbidden.
    forbidden = await client.patch(path, json={"self_service": False})
    assert forbidden.status_code == 200
    assert forbidden.json()["self_service"] is False
    assert forbidden.json()["self_service_effective"] is False

    # Campaign off, the same player allowed.
    await client.patch(base, json={"player_self_service": False})
    allowed = await client.patch(path, json={"self_service": True})
    assert allowed.json()["self_service"] is True
    assert allowed.json()["self_service_effective"] is True

    # Cleared: back to following the campaign (off).
    cleared = await client.patch(path, json={"self_service": None})
    assert cleared.json()["self_service"] is None
    assert cleared.json()["self_service_effective"] is False

    # Leaving the field out changes nothing, and logs nothing.
    untouched = await client.patch(path, json={})
    assert untouched.status_code == 200
    assert untouched.json()["self_service"] is None
    assert (
        await _entries(tenant_id, "player.updated")
        == [("player.updated", "fields=self_service")] * 3
    )

    await _delete_player_user(player_id)
    await delete_tenant(tenant_id)


async def test_setting_the_value_a_player_already_has_logs_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, campaign_id, player_id = await _campaign_with_player(test_user_id)
    path = f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}"

    assert (await client.patch(path, json={"self_service": None})).status_code == 200
    assert await _entries(tenant_id, "player.updated") == []

    await _delete_player_user(player_id)
    await delete_tenant(tenant_id)


async def test_player_patch_checks_if_match(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id, campaign_id, player_id = await _campaign_with_player(test_user_id)
    path = f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}"

    stale = await client.patch(path, json={"self_service": False}, headers={"If-Match": 'W/"x"'})
    assert stale.status_code == 412

    token = (await client.get(path)).json()["updated_at"]
    fresh = await client.patch(
        path, json={"self_service": False}, headers={"If-Match": f'W/"{token}"'}
    )
    assert fresh.status_code == 200

    await _delete_player_user(player_id)
    await delete_tenant(tenant_id)


async def test_a_player_cannot_set_their_own_switch(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The caller plays in the campaign but manages nothing: neither their
    own override nor the campaign's setting is theirs to change."""
    other_owner = uuid.uuid4()
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"authgear|owner-{other_owner}")
        session.add(user)
        await session.commit()
        owner_id = user.id
    tenant_id = await make_tenant(owner_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        campaign_id, player_id = campaign.id, player.id
    base = f"/tenants/{tenant_id}/campaigns/{campaign_id}"

    own = await client.patch(f"{base}/players/{player_id}", json={"self_service": True})
    assert own.status_code == 403
    campaign_patch = await client.patch(base, json={"player_self_service": False})
    assert campaign_patch.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, owner_id))
        await session.commit()


async def test_unknown_player_is_404(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id, campaign_id, player_id = await _campaign_with_player(test_user_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{uuid.uuid4()}",
        json={"self_service": True},
    )
    assert response.status_code == 404

    await _delete_player_user(player_id)
    await delete_tenant(tenant_id)
