"""GET /tenants/{tenant_id}/activity-log - see ADR 0063. A first,
deliberately narrow slice: only the seven named mutation points below are
logged, not an exhaustive audit trail.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Tenant, User


async def _actions(client: AsyncClient, tenant_id: uuid.UUID) -> list[str]:
    response = await client.get(f"/tenants/{tenant_id}/activity-log")
    assert response.status_code == 200
    return [item["action"] for item in response.json()["items"]]


async def test_activity_log_records_membership_lifecycle(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        invitee = User(authgear_subject_id=f"authgear|activity-invitee-{uuid.uuid4()}")
        session.add(invitee)
        await session.commit()
        invitee_id = invitee.id

    create_response = await client.post(
        f"/tenants/{tenant_id}/memberships", json={"user_id": str(invitee_id), "role": "orga"}
    )
    assert create_response.status_code == 201

    update_response = await client.patch(
        f"/tenants/{tenant_id}/memberships/{invitee_id}", json={"role": "owner"}
    )
    assert update_response.status_code == 200

    delete_response = await client.delete(f"/tenants/{tenant_id}/memberships/{invitee_id}")
    assert delete_response.status_code == 204

    actions = await _actions(client, tenant_id)
    assert "membership.created" in actions
    assert "membership.role_changed" in actions
    assert "membership.deleted" in actions

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, invitee_id))
        await session.commit()


async def test_activity_log_records_campaign_and_gm_lifecycle(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    create_response = await client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={
            "name": "Logged Campaign",
            "game_system": "D&D 5e",
            "slug": "logged-campaign",
            "description": "",
        },
    )
    assert create_response.status_code == 201
    campaign_id = create_response.json()["id"]

    async with admin_session_factory() as session:
        gm = User(authgear_subject_id=f"authgear|activity-gm-{uuid.uuid4()}")
        session.add(gm)
        await session.commit()
        gm_id = gm.id

    grant_response = await client.put(f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{gm_id}")
    assert grant_response.status_code == 200

    revoke_response = await client.delete(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}/gms/{gm_id}"
    )
    assert revoke_response.status_code == 200

    delete_response = await client.delete(f"/tenants/{tenant_id}/campaigns/{campaign_id}")
    assert delete_response.status_code == 204

    actions = await _actions(client, tenant_id)
    assert "campaign.created" in actions
    assert "campaign_gm.granted" in actions
    assert "campaign_gm.revoked" in actions
    assert "campaign.deleted" in actions

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, gm_id))
        await session.commit()


async def test_activity_log_is_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)

    await client.post(
        f"/tenants/{tenant_a}/campaigns",
        json={"name": "A", "game_system": "D&D 5e", "slug": "a-campaign", "description": ""},
    )

    actions_a = await _actions(client, tenant_a)
    actions_b = await _actions(client, tenant_b)
    assert "campaign.created" in actions_a
    assert "campaign.created" not in actions_b

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_activity_log_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.get(f"/tenants/{tenant_id}/activity-log")
    assert response.status_code == 404

    await delete_tenant(tenant_id)
