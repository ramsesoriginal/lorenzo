"""ADR 0142: the generic stat PUT can add the stat's group to the entity, as the tag routes do."""

import uuid

from conftest import delete_tenant, make_tenant
from httpx import AsyncClient


async def _group_and_definition(
    client: AsyncClient, tenant_id: uuid.UUID, group: str, name: str, value_type: str
) -> tuple[str, str]:
    created = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": group})
    assert created.status_code == 201, created.text
    definition = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"name": name, "stat_group_id": created.json()["id"], "value_type": value_type},
    )
    assert definition.status_code == 201, definition.text
    return created.json()["id"], definition.json()["id"]


async def _item(client: AsyncClient, tenant_id: uuid.UUID, name: str) -> str:
    created = await client.post(f"/tenants/{tenant_id}/items", json={"name": name})
    assert created.status_code == 201, created.text
    return created.json()["entity_id"]


async def _acquired(client: AsyncClient, tenant_id: uuid.UUID, entity: str) -> list[str]:
    detail = (await client.get(f"/tenants/{tenant_id}/entities/{entity}")).json()
    return sorted(group["name"] for group in detail["stat_groups"])


def _put(client: AsyncClient, tenant_id: uuid.UUID, entity: str, definition: str, **body: object):
    return client.put(f"/tenants/{tenant_id}/entities/{entity}/stats/{definition}", json=body)


async def test_the_generic_put_does_not_acquire_the_group_by_default(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    _, weight = await _group_and_definition(client, tenant_id, "physical", "weight", "int")
    anvil = await _item(client, tenant_id, "Anvil")

    response = await _put(client, tenant_id, anvil, weight, value=40)

    assert response.status_code == 200
    assert await _acquired(client, tenant_id, anvil) == []
    await delete_tenant(tenant_id)


async def test_the_generic_put_acquires_the_group_when_asked(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id, weight = await _group_and_definition(client, tenant_id, "physical", "weight", "int")
    anvil = await _item(client, tenant_id, "Anvil")

    response = await _put(client, tenant_id, anvil, weight, value=40, acquire_group=True)

    assert response.status_code == 200
    assert [(g["id"], g["name"]) for g in response.json()["stat_groups"]] == [
        (group_id, "physical")
    ]
    assert await _acquired(client, tenant_id, anvil) == ["physical"]
    await delete_tenant(tenant_id)


async def test_acquiring_the_same_group_twice_is_harmless(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group_id, weight = await _group_and_definition(client, tenant_id, "physical", "weight", "int")
    other = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"name": "height", "stat_group_id": group_id, "value_type": "int"},
    )
    anvil = await _item(client, tenant_id, "Anvil")

    first = await _put(client, tenant_id, anvil, weight, value=40, acquire_group=True)
    again = await _put(client, tenant_id, anvil, weight, value=41, acquire_group=True)
    second_stat = await _put(
        client, tenant_id, anvil, other.json()["id"], value=2, acquire_group=True
    )

    assert (first.status_code, again.status_code, second_stat.status_code) == (200, 200, 200)
    assert await _acquired(client, tenant_id, anvil) == ["physical"]
    await delete_tenant(tenant_id)


async def test_a_write_that_fails_acquires_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    _, weight = await _group_and_definition(client, tenant_id, "physical", "weight", "int")
    anvil = await _item(client, tenant_id, "Anvil")

    wrong_type = await _put(client, tenant_id, anvil, weight, value="heavy", acquire_group=True)

    assert wrong_type.status_code == 422
    assert await _acquired(client, tenant_id, anvil) == []
    await delete_tenant(tenant_id)


async def test_acquire_group_leaves_a_value_written_without_it_alone(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """It only ever adds: a later plain write neither removes the group nor changes its value."""
    tenant_id = await make_tenant(test_user_id)
    _, weight = await _group_and_definition(client, tenant_id, "physical", "weight", "int")
    anvil = await _item(client, tenant_id, "Anvil")
    await _put(client, tenant_id, anvil, weight, value=40, acquire_group=True)

    plain = await _put(client, tenant_id, anvil, weight, value=45)

    assert plain.status_code == 200
    assert await _acquired(client, tenant_id, anvil) == ["physical"]
    await delete_tenant(tenant_id)
