"""Tenant/campaign administrative settings are logged - see ADR 0084 (the
coverage rule: any actor, administrative settings included). `detail`
carries changed field *names* only, never values.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog


async def _entries(tenant_id: uuid.UUID, action: str) -> list[AuditLog]:
    async with admin_session_factory() as session:
        return list(
            (
                await session.execute(
                    select(AuditLog)
                    .where(AuditLog.tenant_id == tenant_id, AuditLog.action == action)
                    .order_by(AuditLog.created_at)
                )
            )
            .scalars()
            .all()
        )


async def _make_campaign(client: AsyncClient, tenant_id: uuid.UUID) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/campaigns",
        json={
            "name": "Admin Actions",
            "game_system": "D&D 5e",
            "slug": f"admin-actions-{uuid.uuid4()}",
            "description": "",
        },
    )
    assert response.status_code == 201
    return str(response.json()["id"])


async def test_tenant_patch_is_logged_with_field_names_only(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(
        f"/tenants/{tenant_id}", json={"name": "A Very Distinctive Name", "description": "d"}
    )
    assert response.status_code == 200

    (entry,) = await _entries(tenant_id, "tenant.updated")
    assert entry.actor_id == test_user_id
    assert entry.target_id == tenant_id
    assert entry.detail == "fields=name,description"
    assert "Distinctive" not in (entry.detail or "")

    await delete_tenant(tenant_id)


async def test_tenant_patch_that_changes_nothing_is_not_logged(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.patch(f"/tenants/{tenant_id}", json={})
    assert response.status_code == 200

    assert await _entries(tenant_id, "tenant.updated") == []

    await delete_tenant(tenant_id)


async def test_campaign_patch_is_logged_with_field_names_only(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _make_campaign(client, tenant_id)

    response = await client.patch(
        f"/tenants/{tenant_id}/campaigns/{campaign_id}",
        json={"name": "Renamed Secretly", "secret": True},
    )
    assert response.status_code == 200

    (entry,) = await _entries(tenant_id, "campaign.updated")
    assert entry.target_id == uuid.UUID(campaign_id)
    assert entry.detail == "fields=name,secret"
    assert "Secretly" not in (entry.detail or "")

    empty = await client.patch(f"/tenants/{tenant_id}/campaigns/{campaign_id}", json={})
    assert empty.status_code == 200
    assert len(await _entries(tenant_id, "campaign.updated")) == 1

    await delete_tenant(tenant_id)


async def test_admin_opt_out_and_back_in_are_logged_once_each(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    campaign_id = await _make_campaign(client, tenant_id)
    url = f"/tenants/{tenant_id}/campaigns/{campaign_id}/admin-opt-out"

    assert (await client.put(url)).status_code == 200
    assert (await client.put(url)).status_code == 200  # idempotent: no second entry
    assert (await client.delete(url)).status_code == 200
    assert (await client.delete(url)).status_code == 200  # idempotent: no second entry

    assert len(await _entries(tenant_id, "campaign.admin_opted_out")) == 1
    assert len(await _entries(tenant_id, "campaign.admin_opted_in")) == 1

    await delete_tenant(tenant_id)
