import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign
from httpx import AsyncClient

from lorenzo_api.models import CampaignGm, Membership, MembershipRole, Player, Tenant, User


async def test_list_tenants_includes_every_relationship_kind_with_correct_role(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0030/RFC 0003: GET /tenants answers "every tenant I belong to in
    *any* capacity" - a Membership row (role reported directly), a Player
    row, or a CampaignGm row (both report "participant", since neither is a
    tenant-wide role).
    """
    async with admin_session_factory() as session:
        owner_tenant = Tenant(name="Owner Tenant")
        participant_tenant = Tenant(name="Participant Tenant")
        gm_tenant = Tenant(name="GM Tenant")
        session.add_all([owner_tenant, participant_tenant, gm_tenant])
        await session.flush()
        session.add(
            Membership(tenant_id=owner_tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )

        campaign = await make_campaign(session, tenant_id=participant_tenant.id)
        session.add(
            Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=participant_tenant.id)
        )

        gm_campaign = await make_campaign(session, tenant_id=gm_tenant.id, name="GM Campaign")
        session.add(
            CampaignGm(tenant_id=gm_tenant.id, user_id=test_user_id, campaign_id=gm_campaign.id)
        )
        await session.commit()
        owner_id, participant_id, gm_id = owner_tenant.id, participant_tenant.id, gm_tenant.id

    response = await client.get("/tenants")
    assert response.status_code == 200
    role_by_id = {item["id"]: item["role"] for item in response.json()["items"]}
    assert role_by_id[str(owner_id)] == "owner"
    assert role_by_id[str(participant_id)] == "participant"
    assert role_by_id[str(gm_id)] == "participant"

    await delete_tenant(owner_id)
    await delete_tenant(participant_id)
    await delete_tenant(gm_id)


async def test_list_tenants_excludes_tenants_with_no_relationship(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        unrelated = Tenant()
        session.add(unrelated)
        await session.commit()
        unrelated_id = unrelated.id

    response = await client.get("/tenants")
    assert response.status_code == 200
    assert str(unrelated_id) not in {item["id"] for item in response.json()["items"]}

    await delete_tenant(unrelated_id)


async def test_get_tenant_returns_detail_for_a_member(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant(name="Detail Tenant", description="A world.")
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.ORGA))
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(tenant_id)
    assert body["name"] == "Detail Tenant"
    assert body["description"] == "A world."
    assert "slug" in body

    await delete_tenant(tenant_id)


async def test_get_tenant_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        other_user = User(authgear_subject_id=f"authgear|not-a-member-{uuid.uuid4()}")
        session.add_all([tenant, other_user])
        await session.commit()
        tenant_id, other_user_id = tenant.id, other_user.id

    response = await client.get(f"/tenants/{tenant_id}")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    async with admin_session_factory() as session:
        await session.delete(await session.get_one(Tenant, tenant_id))
        await session.delete(await session.get_one(User, other_user_id))
        await session.commit()


async def test_get_tenant_404_for_unknown_tenant(client: AsyncClient) -> None:
    response = await client.get("/tenants/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
