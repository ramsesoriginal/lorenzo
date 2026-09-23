"""Who can read GET /tenants/{id}/activity-log - see ADR 0084.

The log is for tenant administrators. That is enforced today by
`get_tenant_context` requiring a `Membership` row, combined with
`MembershipRole` having only administrative values (OWNER, ORGA) - so
"any tenant-wide member" and "OWNER/ORGA" are the same set. GMs and
players without a Membership never reach it at all. These tests pin that
down, including a tripwire for the day a non-administrative role is added.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import CampaignGm, Membership, MembershipRole, Player, Tenant


async def test_membership_roles_are_all_administrative() -> None:
    """Tripwire. The activity log's read gate is `get_tenant_context`, i.e.
    "has any Membership row". That is only "OWNER/ORGA-only" (ADR 0084)
    while every `MembershipRole` is an administrative role. If this fails
    because a new role was added, the log's gate must become an explicit
    `campaign_access.is_tenant_admin` check *in the same change* - otherwise
    the new role silently gains read access to every GM's and player's
    attributed actions.
    """
    assert set(MembershipRole) == {MembershipRole.OWNER, MembershipRole.ORGA}


async def test_orga_can_read_the_activity_log(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.ORGA))
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/activity-log")
    assert response.status_code == 200

    await delete_tenant(tenant_id)


async def test_a_player_without_membership_cannot_read_the_activity_log(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        session.add(Player(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/activity-log")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_a_gm_without_membership_cannot_read_the_activity_log(
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

    response = await client.get(f"/tenants/{tenant_id}/activity-log")
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_owner_can_read_the_activity_log(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(f"/tenants/{tenant_id}/activity-log")
    assert response.status_code == 200

    await delete_tenant(tenant_id)
