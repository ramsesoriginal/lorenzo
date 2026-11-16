"""ADR 0443: a duplicate name on create is a 409, and a field a stat cannot change is refused."""

import uuid

from conftest import delete_tenant, make_tenant
from httpx import AsyncClient


async def _group(client: AsyncClient, tenant_id: uuid.UUID, name: str = "Vitals") -> dict:
    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


async def _definition(client: AsyncClient, tenant_id: uuid.UUID, group_id: str, name: str) -> dict:
    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": group_id, "name": name, "value_type": "int"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_a_stat_group_with_a_name_that_exists_is_a_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    await _group(client, tenant_id, "Vitals")

    again = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": "Vitals"})
    other = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": "Skills"})

    assert again.status_code == 409, again.text
    assert again.json()["type"].endswith("stat-group-name-taken")
    assert "Vitals" in again.json()["detail"]
    assert other.status_code == 201
    listed = (await client.get(f"/tenants/{tenant_id}/stat-groups")).json()["items"]
    assert sorted(g["name"] for g in listed) == ["Skills", "Vitals"]
    await delete_tenant(tenant_id)


async def test_a_stat_definition_with_a_name_that_exists_is_a_409(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    vitals = await _group(client, tenant_id, "Vitals")
    skills = await _group(client, tenant_id, "Skills")
    await _definition(client, tenant_id, vitals["id"], "speed")

    # The name is the tenant's, not the group's: another group does not free it.
    again = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": skills["id"], "name": "speed", "value_type": "float"},
    )
    other = await _definition(client, tenant_id, skills["id"], "reach")

    assert again.status_code == 409, again.text
    assert again.json()["type"].endswith("stat-definition-name-taken")
    assert "speed" in again.json()["detail"]
    assert other["name"] == "reach"
    listed = (await client.get(f"/tenants/{tenant_id}/stat-definitions")).json()["items"]
    assert sorted(d["name"] for d in listed) == ["reach", "speed"]
    await delete_tenant(tenant_id)


async def test_patching_the_type_or_the_group_of_a_stat_is_a_422_naming_the_field(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    vitals = await _group(client, tenant_id, "Vitals")
    skills = await _group(client, tenant_id, "Skills")
    speed = await _definition(client, tenant_id, vitals["id"], "speed")
    url = f"/tenants/{tenant_id}/stat-definitions/{speed['id']}"

    retype = await client.patch(url, json={"value_type": "float"})
    move = await client.patch(url, json={"stat_group_id": skills["id"]})
    same = await client.patch(url, json={"value_type": "int", "pin": True})
    null = await client.patch(url, json={"stat_group_id": None})

    for refused, field in ((retype, "value_type"), (move, "stat_group_id")):
        assert refused.status_code == 422, refused.text
        assert refused.json()["type"].endswith("stat-definition-field-immutable")
        assert field in refused.json()["detail"]
    assert same.status_code == 422  # carrying it is the refusal, whatever the value
    assert null.status_code == 422
    after = (await client.get(url)).json()
    assert (after["value_type"], after["stat_group_id"], after["pin"]) == (
        "int",
        vitals["id"],
        False,
    )
    await delete_tenant(tenant_id)


async def test_the_other_fields_of_a_stat_patch_still_apply(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    vitals = await _group(client, tenant_id, "Vitals")
    speed = await _definition(client, tenant_id, vitals["id"], "speed")

    patched = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{speed['id']}", json={"unit": "ft", "pin": True}
    )

    assert patched.status_code == 200, patched.text
    assert (patched.json()["unit"], patched.json()["pin"]) == ("ft", True)
    await delete_tenant(tenant_id)
