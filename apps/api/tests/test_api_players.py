import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign
from httpx import AsyncClient

from lorenzo_api.models import (
    Being,
    CampaignGm,
    Character,
    CharacterPlayer,
    Entity,
    Membership,
    MembershipRole,
    Player,
    Tenant,
    User,
)


async def test_list_players_returns_each_players_characters(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0031/RFC 0004: characters resolved through character_player,
    "which of my characters, in which campaign" in one call.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(session, tenant_id=tenant_id)
        campaign_id = campaign.id

        player = Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.flush()

        character_entity = Entity(tenant_id=tenant_id, name="Alice")
        session.add(character_entity)
        await session.flush()
        session.add(Being(entity_id=character_entity.id, tenant_id=tenant_id))
        await session.flush()
        session.add(Character(entity_id=character_entity.id, tenant_id=tenant_id))
        await session.flush()
        session.add(
            CharacterPlayer(
                character_entity_id=character_entity.id, player_id=player.id, tenant_id=tenant_id
            )
        )
        await session.commit()
        player_id = player.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}/players")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == str(player_id)
    assert body["items"][0]["user_id"] == str(test_user_id)
    assert [c["name"] for c in body["items"][0]["characters"]] == ["Alice"]
    assert [c["is_pc"] for c in body["items"][0]["characters"]] == [False]

    await delete_tenant(tenant_id)


async def test_get_player_detail(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(session, tenant_id=tenant_id)
        campaign_id = campaign.id
        player = Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        player_id = player.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}")
    assert response.status_code == 200
    assert response.json()["characters"] == []

    await delete_tenant(tenant_id)


async def test_get_player_404_for_unknown_player_in_a_real_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(session, tenant_id=tenant_id)
        campaign_id = campaign.id
        await session.commit()

    unknown_player_id = uuid.uuid4()
    response = await client.get(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{unknown_player_id}"
    )
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_list_gms_is_unpaginated(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        campaign = await make_campaign(session, tenant_id=tenant_id)
        campaign_id = campaign.id

        gm_user = User(authgear_subject_id=f"authgear|gm-{uuid.uuid4()}")
        session.add(gm_user)
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=gm_user.id, campaign_id=campaign_id))
        await session.commit()
        gm_user_id = gm_user.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert body == [{"user_id": str(gm_user_id)}]

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, gm_user_id))
        await session.commit()


async def test_players_router_404_for_a_caller_with_no_relationship_to_the_tenant(
    client: AsyncClient,
) -> None:
    """Gated by get_campaign_context (ADR 0030/0031), not get_tenant_context -
    but test_user_id (client's fixed caller) still needs *some* legitimate
    reason this 404s: here, simply no Membership/Player/CampaignGm at all.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        campaign_id = campaign.id
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}/players")
    assert response.status_code == 404

    await delete_tenant(tenant_id)
