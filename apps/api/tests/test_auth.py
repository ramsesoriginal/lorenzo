import uuid
from datetime import timedelta

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from conftest import make_campaign
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


async def test_valid_token_grants_access_and_auto_provisions_user(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    subject = f"authgear|{uuid.uuid4()}"
    token = fake_jwks_server.issue_token(subject)

    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert body["authgear_subject_id"] == subject
    assert body["memberships"] == []
    assert body["players"] == []
    assert body["campaign_gm_grants"] == []
    user_id = uuid.UUID(body["id"])

    # Same subject again - must resolve to the SAME user, not create a
    # second row (the atomic-upsert path, ADR 0023).
    token2 = fake_jwks_server.issue_token(subject)
    response2 = await raw_client.get("/me", headers={"Authorization": f"Bearer {token2}"})
    assert response2.status_code == 200
    assert response2.json()["id"] == str(user_id)

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_missing_token_is_rejected(raw_client: AsyncClient) -> None:
    response = await raw_client.get("/me")
    assert response.status_code == 401


async def test_bad_signature_is_rejected(raw_client: AsyncClient) -> None:
    response = await raw_client.get("/me", headers={"Authorization": "Bearer not.a.validtoken"})
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


async def test_expired_token_is_rejected(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    token = fake_jwks_server.issue_token(
        f"authgear|{uuid.uuid4()}", expires_delta=timedelta(seconds=-10)
    )
    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


async def test_wrong_audience_is_rejected(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    token = fake_jwks_server.issue_token(f"authgear|{uuid.uuid4()}", audience="wrong-audience")
    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_wrong_issuer_is_rejected(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    token = fake_jwks_server.issue_token(f"authgear|{uuid.uuid4()}", issuer="wrong-issuer")
    response = await raw_client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401


async def test_me_reports_tenant_memberships(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    subject = f"authgear|{uuid.uuid4()}"
    token = fake_jwks_server.issue_token(subject)
    headers = {"Authorization": f"Bearer {token}"}

    # First request auto-provisions the user - need its id before creating
    # a Membership row for it.
    response = await raw_client.get("/me", headers=headers)
    user_id = uuid.UUID(response.json()["id"])

    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()
        tenant_id = tenant.id

    response2 = await raw_client.get("/me", headers=headers)
    assert response2.status_code == 200
    assert response2.json()["memberships"] == [{"tenant_id": str(tenant_id), "role": "owner"}]

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_me_reports_players_and_campaign_gm_grants(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """ADR 0031/RFC 0004: /me's answer to "user -> [player(campaign) ->
    character | GM(campaign)]" for the caller's own identity, end to end
    over real HTTP - not just at the model layer.
    """
    subject = f"authgear|{uuid.uuid4()}"
    token = fake_jwks_server.issue_token(subject)
    headers = {"Authorization": f"Bearer {token}"}

    response = await raw_client.get("/me", headers=headers)
    user_id = uuid.UUID(response.json()["id"])

    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        player_campaign = await make_campaign(session, tenant_id=tenant_id, name="Player Campaign")
        gm_campaign = await make_campaign(session, tenant_id=tenant_id, name="GM Campaign")

        player = Player(user_id=user_id, campaign_id=player_campaign.id, tenant_id=tenant_id)
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

        session.add(CampaignGm(tenant_id=tenant_id, user_id=user_id, campaign_id=gm_campaign.id))
        await session.commit()
        player_id, player_campaign_id = player.id, player_campaign.id
        gm_campaign_id = gm_campaign.id

    response2 = await raw_client.get("/me", headers=headers)
    assert response2.status_code == 200
    body = response2.json()
    assert len(body["players"]) == 1
    assert body["players"][0]["id"] == str(player_id)
    assert body["players"][0]["campaign_id"] == str(player_campaign_id)
    assert [c["name"] for c in body["players"][0]["characters"]] == ["Alice"]
    assert len(body["campaign_gm_grants"]) == 1
    assert body["campaign_gm_grants"][0]["id"] == str(gm_campaign_id)

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_me_reports_players_and_gm_grants_across_multiple_tenants(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The strongest proof of routers/users.py's own per-tenant resolution
    loop: a player row in one tenant and a GM grant in a *different* tenant
    must both resolve correctly in the same /me call - there is no single
    app.tenant_id that could have authorized both at once, so this fails
    outright if the route ever regresses to one eager-loaded query off
    `user` instead (ADR 0031/RFC 0004).
    """
    subject = f"authgear|{uuid.uuid4()}"
    token = fake_jwks_server.issue_token(subject)
    headers = {"Authorization": f"Bearer {token}"}

    response = await raw_client.get("/me", headers=headers)
    user_id = uuid.UUID(response.json()["id"])

    async with admin_session_factory() as session:
        player_tenant = Tenant()
        gm_tenant = Tenant()
        session.add_all([player_tenant, gm_tenant])
        await session.flush()
        player_tenant_id, gm_tenant_id = player_tenant.id, gm_tenant.id

        player_campaign = await make_campaign(session, tenant_id=player_tenant_id)
        player = Player(user_id=user_id, campaign_id=player_campaign.id, tenant_id=player_tenant_id)
        session.add(player)
        await session.flush()

        character_entity = Entity(tenant_id=player_tenant_id, name="Bob")
        session.add(character_entity)
        await session.flush()
        session.add(Being(entity_id=character_entity.id, tenant_id=player_tenant_id))
        await session.flush()
        session.add(Character(entity_id=character_entity.id, tenant_id=player_tenant_id))
        await session.flush()
        session.add(
            CharacterPlayer(
                character_entity_id=character_entity.id,
                player_id=player.id,
                tenant_id=player_tenant_id,
            )
        )

        gm_campaign = await make_campaign(session, tenant_id=gm_tenant_id, name="GM-only Campaign")
        session.add(CampaignGm(tenant_id=gm_tenant_id, user_id=user_id, campaign_id=gm_campaign.id))
        await session.commit()
        player_id, gm_campaign_id = player.id, gm_campaign.id

    response2 = await raw_client.get("/me", headers=headers)
    assert response2.status_code == 200
    body = response2.json()
    assert len(body["players"]) == 1
    assert body["players"][0]["id"] == str(player_id)
    assert body["players"][0]["tenant_id"] == str(player_tenant_id)
    assert [c["name"] for c in body["players"][0]["characters"]] == ["Bob"]
    assert len(body["campaign_gm_grants"]) == 1
    assert body["campaign_gm_grants"][0]["id"] == str(gm_campaign_id)

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, player_tenant_id))
        await session.delete(await session.get_one(Tenant, gm_tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def test_tenant_scoped_route_requires_real_membership(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Proves get_tenant_context's new membership check end to end through
    a real existing tenant-scoped route (entities), not just /me.
    """
    subject = f"authgear|{uuid.uuid4()}"
    token = fake_jwks_server.issue_token(subject)
    headers = {"Authorization": f"Bearer {token}"}

    me_response = await raw_client.get("/me", headers=headers)
    user_id = uuid.UUID(me_response.json()["id"])

    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    # No Membership yet - must 404, identical in shape to a genuinely
    # unknown tenant (ADR 0023) - a non-member can't distinguish the two.
    no_membership_response = await raw_client.get(f"/tenants/{tenant_id}/entities", headers=headers)
    assert no_membership_response.status_code == 404
    unknown_tenant_response = await raw_client.get(
        f"/tenants/{uuid.uuid4()}/entities", headers=headers
    )
    assert unknown_tenant_response.status_code == 404
    assert no_membership_response.json()["type"] == unknown_tenant_response.json()["type"]
    assert no_membership_response.json()["title"] == unknown_tenant_response.json()["title"]

    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=tenant_id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()

    with_membership_response = await raw_client.get(
        f"/tenants/{tenant_id}/entities", headers=headers
    )
    assert with_membership_response.status_code == 200

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, user_id))
        await session.commit()
