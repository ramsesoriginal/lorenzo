"""GET /tenants/{id}/beings - see ADR 0078."""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Being, Entity, Player, Tenant


async def test_list_beings_includes_bare_beings_and_characters(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Unlike GET .../characters, a bare being with no Character row does
    appear here (is_pc: null), alongside a plain tracked NPC (is_pc:
    false, no owner_player_id) and a player-owned PC (is_pc: true).
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        player = Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()

        pc = await make_character(
            session, tenant_id=tenant_id, name="Alice", owner_player_id=player.id
        )
        tracked_npc = await make_character(session, tenant_id=tenant_id, name="Shopkeeper Bob")

        bare_entity = Entity(tenant_id=tenant_id, name="Unnamed Goblin")
        session.add(bare_entity)
        await session.flush()
        session.add(Being(entity_id=bare_entity.id, tenant_id=tenant_id))
        await session.commit()
        pc_id, tracked_npc_id, bare_id = pc.entity_id, tracked_npc.entity_id, bare_entity.id

    response = await client.get(f"/tenants/{tenant_id}/beings")
    assert response.status_code == 200
    by_id = {b["entity_id"]: b for b in response.json()["items"]}

    assert by_id.keys() == {str(pc_id), str(tracked_npc_id), str(bare_id)}
    assert by_id[str(pc_id)] == {"entity_id": str(pc_id), "name": "Alice", "is_pc": True}
    assert by_id[str(tracked_npc_id)] == {
        "entity_id": str(tracked_npc_id),
        "name": "Shopkeeper Bob",
        "is_pc": False,
    }
    assert by_id[str(bare_id)] == {
        "entity_id": str(bare_id),
        "name": "Unnamed Goblin",
        "is_pc": None,
    }

    await delete_tenant(tenant_id)


async def test_list_beings_q_filters_by_name(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        await make_character(session, tenant_id=tenant_id, name="Goblin Scout")
        await make_character(session, tenant_id=tenant_id, name="Dragon")
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/beings", params={"q": "goblin"})
    assert response.status_code == 200
    names = [b["name"] for b in response.json()["items"]]
    assert names == ["Goblin Scout"]

    await delete_tenant(tenant_id)


async def test_list_beings_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/beings")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_list_beings_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get("/tenants/00000000-0000-0000-0000-000000000000/beings")
    assert response.status_code == 404


async def test_list_beings_cross_tenant_isolation(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        await make_character(session, tenant_id=tenant_a, name="Only In A")
        await session.commit()

    response = await client.get(f"/tenants/{tenant_b}/beings")
    assert response.status_code == 200
    assert response.json()["items"] == []

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)
