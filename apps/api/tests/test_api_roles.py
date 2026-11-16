"""ADR 0449: a stat or a group is read by its role and not by its name - assigning a role (type,
uniqueness, no game system), the default for a name that is a role, what the item read does with
a renamed role-holder, a system's `ds_weight`, and the reserved value of a binding.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Entity, Item


async def _group(client: AsyncClient, tenant_id: uuid.UUID, name: str, **extra: object) -> dict:
    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def _stat_response(
    client: AsyncClient,
    tenant_id: uuid.UUID,
    group_id: str,
    name: str,
    value_type: str = "int",
    **extra: object,
):
    return await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": group_id, "name": name, "value_type": value_type, **extra},
    )


async def _stat(
    client: AsyncClient,
    tenant_id: uuid.UUID,
    group_id: str,
    name: str,
    value_type: str = "int",
    **extra: object,
) -> dict:
    response = await _stat_response(client, tenant_id, group_id, name, value_type, **extra)
    assert response.status_code == 201, response.text
    return response.json()


async def _item(tenant_id: uuid.UUID, name: str = "Sword") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _set(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID, stat: dict, value: object
) -> None:
    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/stats/{stat['id']}", json={"value": value}
    )
    assert response.status_code == 200, response.text


# --- the default: a name that is a role ---


async def test_a_stat_or_group_named_after_a_free_role_takes_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    physical = await _group(client, tenant_id, "physical")
    other = await _group(client, tenant_id, "Extras")
    weight = await _stat(client, tenant_id, physical["id"], "weight")
    text_weight = await _stat(client, tenant_id, other["id"], "height", "text")
    plain = await _stat(client, tenant_id, other["id"], "Reach")

    assert physical["role"] == "physical" and other["role"] is None
    assert weight["role"] == "weight"
    assert text_weight["role"] is None  # a text stat is not read as a height
    assert plain["role"] is None
    await delete_tenant(tenant_id)


async def test_null_says_none_and_a_taken_role_is_not_the_default(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "physical", role=None)
    height = await _stat(client, tenant_id, group["id"], "height", role=None)
    first = await _stat(client, tenant_id, group["id"], "weight")
    gear = await _group(client, tenant_id, "Gear")
    taken = await _stat_response(client, tenant_id, gear["id"], "load", role="weight")
    # A free role still goes to a stat of that name by default.
    other = await _stat(client, tenant_id, gear["id"], "hp")

    assert group["role"] is None
    assert height["role"] is None
    assert first["role"] == "weight"
    assert taken.status_code == 409
    assert other["role"] == "hp"
    await delete_tenant(tenant_id)


# --- assigning a role ---


async def test_a_role_is_assigned_and_cleared_on_a_stat_and_a_group(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    body = await _group(client, tenant_id, "Body")
    mass = await _stat(client, tenant_id, body["id"], "mass")

    group = await client.patch(
        f"/tenants/{tenant_id}/stat-groups/{body['id']}", json={"role": "physical"}
    )
    stat = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{mass['id']}", json={"role": "weight"}
    )
    cleared = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{mass['id']}", json={"role": None}
    )
    unknown = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{mass['id']}", json={"role": "mana"}
    )

    assert (group.status_code, group.json()["role"]) == (200, "physical")
    assert (stat.status_code, stat.json()["role"]) == (200, "weight")
    assert (cleared.status_code, cleared.json()["role"]) == (200, None)
    assert unknown.status_code == 422
    await delete_tenant(tenant_id)


async def test_a_role_is_held_once_and_needs_a_type_that_fits(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Body")
    await _stat(client, tenant_id, group["id"], "mass", role="weight")
    other_group = await _group(client, tenant_id, "Other", role="tags")
    text = await _stat(client, tenant_id, group["id"], "Title", "text")
    plain_int = await _stat(client, tenant_id, group["id"], "Count")

    second = await _stat_response(client, tenant_id, group["id"], "load", role="weight")
    wrong_type = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{text['id']}", json={"role": "weight"}
    )
    binding_as_int = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{plain_int['id']}", json={"role": "binding"}
    )
    second_group = await client.post(
        f"/tenants/{tenant_id}/stat-groups", json={"name": "More", "role": "tags"}
    )
    binding_no_none = await _stat_response(
        client, tenant_id, group["id"], "lock", "enum", role="binding", enum_values=["held"]
    )
    binding = await _stat_response(
        client, tenant_id, group["id"], "lock", "enum", role="binding", enum_values=["none", "held"]
    )

    assert other_group["role"] == "tags"
    assert second.status_code == 409
    assert wrong_type.status_code == 422
    assert binding_as_int.status_code == 422
    assert second_group.status_code == 409
    assert binding_no_none.status_code == 422
    assert (binding.status_code, binding.json()["role"]) == (201, "binding")
    await delete_tenant(tenant_id)


# --- a role-holder is neutral ---


async def test_a_role_holder_belongs_to_no_game_system(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    system = (
        await client.post(
            f"/tenants/{tenant_id}/systems", json={"slug": "ds", "name": "Draw Steel"}
        )
    ).json()
    ds_group = await _group(client, tenant_id, "Draw Steel", system_id=system["id"])
    neutral = await _group(client, tenant_id, "Body")
    held = await _stat(client, tenant_id, neutral["id"], "mass", role="weight")

    group_in_system = await client.post(
        f"/tenants/{tenant_id}/stat-groups",
        json={"name": "Armour", "system_id": system["id"], "role": "physical"},
    )
    stat_in_system = await _stat_response(
        client, tenant_id, ds_group["id"], "ds_weight", role="weight"
    )
    group_takes_role = await client.patch(
        f"/tenants/{tenant_id}/stat-groups/{ds_group['id']}", json={"role": "physical"}
    )
    group_takes_system = await client.patch(
        f"/tenants/{tenant_id}/stat-groups/{neutral['id']}", json={"system_id": system["id"]}
    )
    cleared = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{held['id']}", json={"role": None}
    )
    moved = await client.patch(
        f"/tenants/{tenant_id}/stat-groups/{neutral['id']}", json={"system_id": system["id"]}
    )

    assert group_in_system.status_code == 422
    assert stat_in_system.status_code == 422
    assert group_takes_role.status_code == 422
    assert group_takes_system.status_code == 422  # the group still has a stat that holds a role
    assert cleared.status_code == 200
    assert moved.status_code == 422  # mass does not start with ds_
    await delete_tenant(tenant_id)


# --- what the API reads ---


async def test_the_item_read_follows_the_role_and_not_the_name(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    body = await _group(client, tenant_id, "Body", role="physical")
    mass = await _stat(client, tenant_id, body["id"], "mass", role="weight")
    item = await _item(tenant_id)
    await _set(client, tenant_id, item, mass, 7)

    read = (await client.get(f"/tenants/{tenant_id}/items/{item}")).json()

    assert read["weight"] == 7
    assert read["physical_stats"] == [{"name": "mass", "value": 7}]
    await delete_tenant(tenant_id)


async def test_renaming_a_role_holder_does_not_change_what_is_read(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    physical = await _group(client, tenant_id, "physical")
    weight = await _stat(client, tenant_id, physical["id"], "weight")
    item = await _item(tenant_id)
    await _set(client, tenant_id, item, weight, 3)

    renamed = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{weight['id']}", json={"name": "mass"}
    )
    group_renamed = await client.patch(
        f"/tenants/{tenant_id}/stat-groups/{physical['id']}", json={"name": "Body"}
    )
    read = (await client.get(f"/tenants/{tenant_id}/items/{item}")).json()

    assert (renamed.status_code, renamed.json()["role"]) == (200, "weight")
    assert (group_renamed.status_code, group_renamed.json()["role"]) == (200, "physical")
    assert read["weight"] == 3
    assert read["physical_stats"] == [{"name": "mass", "value": 3}]
    await delete_tenant(tenant_id)


async def test_a_stat_named_after_a_role_without_it_is_not_read(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    physical = await _group(client, tenant_id, "physical")
    weight = await _stat(client, tenant_id, physical["id"], "weight")
    item = await _item(tenant_id)
    await _set(client, tenant_id, item, weight, 3)

    await client.patch(f"/tenants/{tenant_id}/stat-definitions/{weight['id']}", json={"role": None})
    read = (await client.get(f"/tenants/{tenant_id}/items/{item}")).json()

    assert read["weight"] is None
    await delete_tenant(tenant_id)


async def test_a_game_systems_own_weight_is_an_ordinary_stat(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    system = (
        await client.post(
            f"/tenants/{tenant_id}/systems", json={"slug": "ds", "name": "Draw Steel"}
        )
    ).json()
    group = await _group(client, tenant_id, "Draw Steel", system_id=system["id"])
    ds_weight = await _stat(client, tenant_id, group["id"], "ds_weight")
    physical = await _group(client, tenant_id, "physical")
    weight = await _stat(client, tenant_id, physical["id"], "weight")
    item = await _item(tenant_id)
    await _set(client, tenant_id, item, ds_weight, 99)
    await _set(client, tenant_id, item, weight, 4)

    read = (await client.get(f"/tenants/{tenant_id}/items/{item}")).json()

    assert ds_weight["role"] is None
    assert read["weight"] == 4
    await delete_tenant(tenant_id)


# --- the binding's `none` ---


async def test_the_none_of_a_binding_is_reserved_by_role_not_by_name(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Gear")
    lock = await _stat(
        client, tenant_id, group["id"], "lock", "enum", role="binding", enum_values=["none", "held"]
    )
    plain = await _stat(
        client, tenant_id, group["id"], "mood", "enum", enum_values=["none", "calm"]
    )
    by_value = {v["value"]: v["id"] for v in lock["enum_options"]}
    plain_by_value = {v["value"]: v["id"] for v in plain["enum_options"]}

    refused = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{lock['id']}/enum-values/{by_value['none']}",
        json={"value": "nothing"},
    )
    allowed = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{plain['id']}/enum-values/{plain_by_value['none']}",
        json={"value": "nothing"},
    )

    assert refused.status_code == 409
    assert allowed.status_code == 200
    await delete_tenant(tenant_id)
