"""Who can read GET /tenants/{id}/activity-log - see ADR 0084.

The log is for tenant administrators (OWNER or ORGA). It is enforced by
`get_tenant_admin_context`, so an AUTHOR (RFC 0040, ADR 0210), who is a
member but not an administrator, is refused with a 403, and GMs and players
without a Membership never reach it at all (404). These tests pin that down;
tests/test_author_route_audit.py is the table that replaced the tripwire
which used to fail the day a non-administrative role was added.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import CampaignGm, Membership, MembershipRole, Player, Tenant


async def test_an_author_cannot_read_the_activity_log(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(
            Membership(tenant_id=tenant.id, user_id=test_user_id, role=MembershipRole.AUTHOR)
        )
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/activity-log")
    assert response.status_code == 403

    await delete_tenant(tenant_id)


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
