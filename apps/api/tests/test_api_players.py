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


# --- POST/DELETE /players (ADR 0036/RFC 0007) -----------------------------


async def test_create_player_as_gm_sets_attribution(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id))
        new_player_user = User(authgear_subject_id=f"authgear|new-player-{uuid.uuid4()}")
        session.add(new_player_user)
        await session.commit()
        new_player_user_id = new_player_user.id

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players",
        json={"user_id": str(new_player_user_id)},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == str(new_player_user_id)
    assert body["created_by"] == str(test_user_id)
    assert body["updated_by"] == str(test_user_id)
    assert response.headers["location"].endswith(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{body['id']}"
    )

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, new_player_user_id))
        await session.commit()


async def test_create_player_403_for_a_plain_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.commit()
        other_user_id = other_user.id

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players",
        json={"user_id": str(other_user_id)},
    )

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_user_id))
        await session.commit()


async def test_create_player_422_for_a_nonexistent_user(
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
        await session.commit()
        campaign_id = campaign.id

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players",
        json={"user_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_create_player_409_when_already_a_player(
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
        await session.flush()
        campaign_id = campaign.id
        existing_user = User(authgear_subject_id=f"authgear|existing-{uuid.uuid4()}")
        session.add(existing_user)
        await session.flush()
        session.add(Player(user_id=existing_user.id, campaign_id=campaign_id, tenant_id=tenant_id))
        await session.commit()
        existing_user_id = existing_user.id

    response = await client.post(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players",
        json={"user_id": str(existing_user_id)},
    )

    assert response.status_code == 409

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, existing_user_id))
        await session.commit()


async def test_delete_player_as_gm(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=campaign_id))
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        player = Player(user_id=other_user.id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        player_id, other_user_id = player.id, other_user.id

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}"
    )

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(Player, player_id) is None

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_user_id))
        await session.commit()


async def test_delete_player_self_removal_without_manage_permission(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A player can always leave their own campaign, even without
    can_manage_campaign - the same self-removal carve-out
    revoke_campaign_gm already established.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        player = Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        player_id = player.id

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}"
    )

    assert response.status_code == 204
    async with admin_session_factory() as session:
        assert await session.get(Player, player_id) is None

    await delete_tenant(tenant_id)


async def test_delete_player_403_for_an_unrelated_caller(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.flush()
        campaign_id = campaign.id
        session.add(Player(user_id=test_user_id, campaign_id=campaign_id, tenant_id=tenant_id))
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        other_player = Player(user_id=other_user.id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(other_player)
        await session.commit()
        other_player_id, other_user_id = other_player.id, other_user.id

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{other_player_id}"
    )

    assert response.status_code == 403

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_user_id))
        await session.commit()


async def test_delete_player_404_for_unknown_player(
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
        await session.commit()
        campaign_id = campaign.id

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{uuid.uuid4()}"
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_delete_player_precondition_failed_with_stale_if_match(
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
        await session.flush()
        campaign_id = campaign.id
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        player = Player(user_id=other_user.id, campaign_id=campaign_id, tenant_id=tenant_id)
        session.add(player)
        await session.commit()
        player_id, other_user_id = player.id, other_user.id

    response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/players/{player_id}",
        headers={"If-Match": 'W/"stale"'},
    )

    assert response.status_code == 412

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, other_user_id))
        await session.commit()
