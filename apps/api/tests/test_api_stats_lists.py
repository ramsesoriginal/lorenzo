"""GET /tenants/{id}/stat-groups and /stat-definitions - the listings the
by-id routes never had (ADR 0085): a tenant's stat vocabulary has to be
discoverable, and therefore exportable, without already knowing its ids.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Tenant


async def _make_group(client: AsyncClient, tenant_id: uuid.UUID, name: str) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/stat-groups", json={"name": name, "priority": 1}
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def _make_definition(
    client: AsyncClient, tenant_id: uuid.UUID, group_id: str, name: str
) -> str:
    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": group_id, "name": name, "value_type": "int"},
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


async def test_list_stat_groups_is_name_ordered_paginated_and_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    await _make_group(client, tenant_a, "Physical")
    await _make_group(client, tenant_a, "Combat")
    await _make_group(client, tenant_b, "Elsewhere")

    response = await client.get(f"/tenants/{tenant_a}/stat-groups")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [group["name"] for group in body["items"]] == ["Combat", "Physical"]

    first_page = await client.get(f"/tenants/{tenant_a}/stat-groups", params={"size": 1})
    assert [g["name"] for g in first_page.json()["items"]] == ["Combat"]
    assert first_page.json()["pages"] == 2

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_list_stat_definitions_resolve_to_a_listed_group(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id = await _make_group(client, tenant_id, "Physical")
    definition_id = await _make_definition(client, tenant_id, group_id, "weight")

    groups = (await client.get(f"/tenants/{tenant_id}/stat-groups")).json()["items"]
    definitions = (await client.get(f"/tenants/{tenant_id}/stat-definitions")).json()["items"]

    assert [d["id"] for d in definitions] == [definition_id]
    assert definitions[0]["stat_group_id"] in {g["id"] for g in groups}

    await delete_tenant(tenant_id)


async def test_stat_lists_are_hidden_from_non_members(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    assert (await client.get(f"/tenants/{tenant_id}/stat-groups")).status_code == 404
    assert (await client.get(f"/tenants/{tenant_id}/stat-definitions")).status_code == 404

    await delete_tenant(tenant_id)
