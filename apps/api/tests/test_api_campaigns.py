import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_player
from httpx import AsyncClient

from lorenzo_api.models import CampaignGm, Membership, MembershipRole, Player, Tenant, User


async def test_list_campaigns_hides_secret_from_a_plain_participant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0030/RFC 0003: a plain participant (a Player row, no
    Membership/CampaignGm) sees non-secret campaigns but not a secret one
    they don't GM."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        visible = await make_campaign(session, tenant_id=tenant_id, name="Visible")
        secret = await make_campaign(session, tenant_id=tenant_id, name="Secret")
        secret.secret = True
        await make_player(session, tenant_id=tenant_id, campaign_id=visible.id)
        # The caller (test_user_id) needs their own Player row too, in
        # *some* campaign, to count as is_tenant_participant at all.
        session.add(Player(user_id=test_user_id, campaign_id=visible.id, tenant_id=tenant_id))
        await session.commit()
        visible_id, secret_id = visible.id, secret.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(visible_id) in ids
    assert str(secret_id) not in ids

    await delete_tenant(tenant_id)


async def test_list_campaigns_shows_secret_to_its_own_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        secret = await make_campaign(session, tenant_id=tenant_id, name="Secret")
        secret.secret = True
        await session.flush()
        session.add(CampaignGm(tenant_id=tenant_id, user_id=test_user_id, campaign_id=secret.id))
        await session.commit()
        secret_id = secret.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(secret_id) in ids

    await delete_tenant(tenant_id)


async def test_list_campaigns_shows_secret_to_a_tenant_admin(
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
        secret = await make_campaign(session, tenant_id=tenant_id, name="Secret")
        secret.secret = True
        await session.commit()
        secret_id = secret.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(secret_id) in ids

    await delete_tenant(tenant_id)


async def test_list_campaigns_404_for_a_caller_with_no_relationship_to_the_tenant(
    client: AsyncClient,
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_get_campaign_reachable_via_player_gm_or_admin(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Reachable")
        await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        session.add(
            Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        await session.commit()
        campaign_id = campaign.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(campaign_id)
    assert body["name"] == "Reachable"
    assert body["secret"] is False
    assert "entity_id" not in body

    await delete_tenant(tenant_id)


async def test_get_campaign_ignores_secret_when_otherwise_reachable(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0030/RFC 0003: secret only governs the browse-all list, not
    whether someone who already has a legitimate way to reach a campaign
    (their own Player row here) can open it directly."""
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Secret But Mine")
        campaign.secret = True
        await session.flush()
        await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
        session.add(Membership(tenant_id=tenant_id, user_id=test_user_id, role=MembershipRole.ORGA))
        await session.commit()
        campaign_id = campaign.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 200

    await delete_tenant(tenant_id)


async def test_get_campaign_404_when_caller_cannot_access_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """get_tenant_or_404 (unlike get_tenant_context) admits any real tenant
    regardless of membership - test_user_id reaches the tenant fine here,
    then get_campaign_context's own can_access_campaign check is what
    actually rejects a campaign they have no player/gm/admin relationship
    to (ADR 0030/RFC 0003), the "reachable tenant, unreachable campaign"
    case this dependency exists to distinguish.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Not Mine")
        # Someone else's Player row, not test_user_id's - proves the
        # campaign is real and has players, just not this caller.
        other_user = User(authgear_subject_id=f"authgear|other-{uuid.uuid4()}")
        session.add(other_user)
        await session.flush()
        session.add(Player(user_id=other_user.id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()
        campaign_id = campaign.id

    response = await client.get(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    await delete_tenant(tenant_id)


async def test_get_campaign_404_for_unknown_campaign_in_a_real_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        await session.commit()
        tenant_id = tenant.id

    unknown_campaign_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/tenants/{tenant_id}/campaigns/{unknown_campaign_id}")
    assert response.status_code == 404

    await delete_tenant(tenant_id)
