"""GET /tenants/{id}/knowledge - the tenant-wide index of who knows what
(ADR 0085). Ids only; administrators only (a Membership row is required,
and every MembershipRole is administrative).
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_player, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import CampaignGm, Entity, Item, Knowledge, Player, Tenant, User


async def _make_entity(tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _make_information(client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/entities/{entity_id}/information",
        json={
            "title": "A private title",
            "type": "secret",
            "is_public": False,
            "content": "private body",
            "locale": "en",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_list_knowledge_returns_entity_and_player_knowers_as_ids_only(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    subject_id = await _make_entity(tenant_id, "Ashfang")
    knower_id = await _make_entity(tenant_id, "Alice")
    information_id = await _make_information(client, tenant_id, subject_id)
    grant = await client.put(
        f"/tenants/{tenant_id}/information/{information_id}/knowers/{knower_id}"
    )
    assert grant.status_code == 200, grant.text

    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        session.add(
            Knowledge(
                tenant_id=tenant_id,
                knower_player_id=player.id,
                information_id=uuid.UUID(information_id),
            )
        )
        await session.commit()
        player_id, player_user_id = player.id, player.user_id

    response = await client.get(f"/tenants/{tenant_id}/knowledge")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert response.json()["total"] == 2

    by_kind = {("entity" if item["knower_entity_id"] else "player"): item for item in items}
    assert by_kind["entity"]["knower_entity_id"] == str(knower_id)
    assert by_kind["entity"]["knower_player_id"] is None
    assert by_kind["player"]["knower_player_id"] == str(player_id)
    for item in items:
        assert item["information_id"] == information_id
        assert item["entity_id"] == str(subject_id)
        # Ids only: nothing from the information itself leaks into the index.
        assert set(item) == {
            "id",
            "information_id",
            "entity_id",
            "knower_entity_id",
            "knower_player_id",
            "created_at",
        }

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, player_user_id))
        await session.commit()


async def test_list_knowledge_is_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    subject_id = await _make_entity(tenant_a, "Ashfang")
    knower_id = await _make_entity(tenant_a, "Alice")
    information_id = await _make_information(client, tenant_a, subject_id)
    await client.put(f"/tenants/{tenant_a}/information/{information_id}/knowers/{knower_id}")

    assert (await client.get(f"/tenants/{tenant_a}/knowledge")).json()["total"] == 1
    assert (await client.get(f"/tenants/{tenant_b}/knowledge")).json()["total"] == 0

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_gm_and_player_without_membership_cannot_list_knowledge(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        session.add(CampaignGm(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    assert (await client.get(f"/tenants/{tenant_id}/knowledge")).status_code == 404

    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Other")
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
    assert (await client.get(f"/tenants/{tenant_id}/knowledge")).status_code == 404

    await delete_tenant(tenant_id)
