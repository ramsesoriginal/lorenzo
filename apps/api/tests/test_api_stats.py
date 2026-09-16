import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import StatGroup, StatValueType, Tenant


async def _make_stat_group(
    tenant_id: uuid.UUID, name: str = "physical", priority: int = 0
) -> uuid.UUID:
    async with admin_session_factory() as session:
        stat_group = StatGroup(tenant_id=tenant_id, name=name, priority=priority)
        session.add(stat_group)
        await session.commit()
        return stat_group.id


async def test_create_stat_group_returns_created_shape_and_location(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/stat-groups", json={"name": "physical", "priority": 3}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "physical"
    assert body["priority"] == 3
    assert response.headers["location"].endswith(f"/tenants/{tenant_id}/stat-groups/{body['id']}")

    get_response = await client.get(response.headers["location"])
    assert get_response.status_code == 200
    assert get_response.json() == body

    await delete_tenant(tenant_id)


async def test_create_stat_group_defaults_priority_to_zero(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": "combat"})

    assert response.status_code == 201
    assert response.json()["priority"] == 0

    await delete_tenant(tenant_id)


async def test_create_stat_group_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id

    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": "physical"})
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_get_stat_group_404_for_unknown_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(
        f"/tenants/{tenant_id}/stat-groups/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    await delete_tenant(tenant_id)


async def test_get_stat_group_404_for_wrong_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    stat_group_id = await _make_stat_group(tenant_a)

    response = await client.get(f"/tenants/{tenant_b}/stat-groups/{stat_group_id}")
    assert response.status_code == 404

    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_create_stat_definition_returns_created_shape_and_location(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stat_group_id = await _make_stat_group(tenant_id)

    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"name": "weight", "stat_group_id": str(stat_group_id), "value_type": "int"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "weight"
    assert body["stat_group_id"] == str(stat_group_id)
    assert body["value_type"] == "int"
    assert response.headers["location"].endswith(
        f"/tenants/{tenant_id}/stat-definitions/{body['id']}"
    )

    get_response = await client.get(response.headers["location"])
    assert get_response.status_code == 200
    assert get_response.json() == body

    await delete_tenant(tenant_id)


async def test_create_stat_definition_422_for_unknown_stat_group(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={
            "name": "weight",
            "stat_group_id": str(uuid.uuid4()),
            "value_type": "int",
        },
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_create_stat_definition_422_for_stat_group_in_another_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    stat_group_id = await _make_stat_group(tenant_a)

    response = await client.post(
        f"/tenants/{tenant_b}/stat-definitions",
        json={"name": "weight", "stat_group_id": str(stat_group_id), "value_type": "int"},
    )

    assert response.status_code == 422
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_get_stat_definition_404_for_unknown_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    response = await client.get(
        f"/tenants/{tenant_id}/stat-definitions/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == 404
    await delete_tenant(tenant_id)


async def test_create_stat_definition_404_for_non_member(client: AsyncClient) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id
    stat_group_id = await _make_stat_group(tenant_id)

    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"name": "weight", "stat_group_id": str(stat_group_id), "value_type": "int"},
    )
    assert response.status_code == 404

    await delete_tenant(tenant_id)


async def test_create_stat_definition_accepts_every_value_type(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    stat_group_id = await _make_stat_group(tenant_id)

    for value_type in StatValueType:
        response = await client.post(
            f"/tenants/{tenant_id}/stat-definitions",
            json={
                "name": f"stat-{value_type.value}",
                "stat_group_id": str(stat_group_id),
                "value_type": value_type.value,
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["value_type"] == value_type.value

    await delete_tenant(tenant_id)
