"""ADR 0141: a stat that holds a float reads as a float in the named columns and in the
per-group stat lists, instead of null. Built through the REST API, the way an importer does."""

import uuid

from conftest import delete_tenant, make_tenant
from httpx import AsyncClient


async def _definition(
    client: AsyncClient, tenant_id: uuid.UUID, group: str, name: str, value_type: str
) -> str:
    """A stat definition in a group of that name, both created if missing."""
    groups = await client.get(f"/tenants/{tenant_id}/stat-groups")
    existing = {g["name"]: g["id"] for g in groups.json()["items"]}
    if group in existing:
        group_id = existing[group]
    else:
        created = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": group})
        assert created.status_code == 201, created.text
        group_id = created.json()["id"]
    definition = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"name": name, "stat_group_id": group_id, "value_type": value_type},
    )
    assert definition.status_code == 201, definition.text
    return definition.json()["id"]


async def _item(client: AsyncClient, tenant_id: uuid.UUID, name: str, **extra: object) -> str:
    created = await client.post(f"/tenants/{tenant_id}/items", json={"name": name, **extra})
    assert created.status_code == 201, created.text
    return created.json()["entity_id"]


async def _set(
    client: AsyncClient, tenant_id: uuid.UUID, entity: str, definition: str, value: object
) -> None:
    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity}/stats/{definition}", json={"value": value}
    )
    assert response.status_code == 200, response.text


def _stats(body: dict, group: str) -> dict[str, object]:
    return {s["name"]: s["value"] for s in body[f"{group}_stats"]}


async def test_a_float_weight_reads_as_a_float_on_an_item(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weight = await _definition(client, tenant_id, "physical", "weight", "float")
    bullet = await _item(client, tenant_id, "Bullet")
    await _set(client, tenant_id, bullet, weight, 0.05)

    item = (await client.get(f"/tenants/{tenant_id}/items/{bullet}")).json()
    listed = (await client.get(f"/tenants/{tenant_id}/items")).json()["items"]

    assert item["weight"] == 0.05
    assert _stats(item, "physical") == {"weight": 0.05}
    assert [i["weight"] for i in listed] == [0.05]
    await delete_tenant(tenant_id)


async def test_a_float_weight_is_inherited_by_an_instance(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weight = await _definition(client, tenant_id, "physical", "weight", "float")
    rope = await _item(client, tenant_id, "Hempen rope, feet of")
    await _set(client, tenant_id, rope, weight, 0.2)

    created = await client.post(f"/tenants/{tenant_id}/item-instances", json={"prototype_id": rope})
    assert created.status_code == 201, created.text
    instance = (
        await client.get(f"/tenants/{tenant_id}/item-instances/{created.json()['entity_id']}")
    ).json()

    assert instance["weight"] == 0.2
    assert _stats(instance, "physical") == {"weight": 0.2}
    await delete_tenant(tenant_id)


async def test_a_stat_that_is_not_a_named_column_reads_as_a_float_in_its_group(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    own_weight = await _definition(client, tenant_id, "physical", "own_weight", "float")
    lamp = await _item(client, tenant_id, "Lamp")
    await _set(client, tenant_id, lamp, own_weight, 1.5)

    item = (await client.get(f"/tenants/{tenant_id}/items/{lamp}")).json()

    assert _stats(item, "physical") == {"own_weight": 1.5}
    assert item["weight"] is None  # there is no stat called weight here
    await delete_tenant(tenant_id)


async def test_an_int_weight_still_reads_as_an_int(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weight = await _definition(client, tenant_id, "physical", "weight", "int")
    anvil = await _item(client, tenant_id, "Anvil")
    await _set(client, tenant_id, anvil, weight, 40)

    item = (await client.get(f"/tenants/{tenant_id}/items/{anvil}")).json()

    assert item["weight"] == 40
    assert isinstance(item["weight"], int)
    assert _stats(item, "physical") == {"weight": 40}
    await delete_tenant(tenant_id)


async def test_a_text_stat_in_a_group_is_still_null_there(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The per-group lists carry numbers only; a text value is in GET .../entities/{id}."""
    tenant_id = await make_tenant(test_user_id)
    damage_type = await _definition(client, tenant_id, "damaging", "damage_type", "text")
    die = await _definition(client, tenant_id, "damaging", "damage_die", "int")
    sword = await _item(client, tenant_id, "Longsword")
    await _set(client, tenant_id, sword, damage_type, "slashing")
    await _set(client, tenant_id, sword, die, 8)

    item = (await client.get(f"/tenants/{tenant_id}/items/{sword}")).json()

    assert _stats(item, "damaging") == {"damage_type": None, "damage_die": 8}
    await delete_tenant(tenant_id)
