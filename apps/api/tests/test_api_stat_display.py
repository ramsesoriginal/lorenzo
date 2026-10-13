"""ADR 0278: how a stat is shown (unit, sign, adjustable in play, pinned), the
order of stats and groups, and `PATCH` for stat definitions and groups.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_plain_participant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import Entity, EntityStat


async def _group(client: AsyncClient, tenant_id: uuid.UUID, name: str, **extra: object) -> dict:
    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def _definition(
    client: AsyncClient, tenant_id: uuid.UUID, group_id: str, name: str, **extra: object
) -> dict:
    response = await client.post(
        f"/tenants/{tenant_id}/stat-definitions",
        json={"stat_group_id": group_id, "name": name, "value_type": "int", **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def _listed(client: AsyncClient, tenant_id: uuid.UUID, what: str) -> list[str]:
    body = (await client.get(f"/tenants/{tenant_id}/{what}", params={"size": 100})).json()
    return [item["name"] for item in body["items"]]


# --- the fields ----------------------------------------------------------------


async def test_a_definition_defaults_to_plain_and_takes_its_display_fields(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Vitals")

    plain = await _definition(client, tenant_id, group["id"], "hit_points")
    shown = await _definition(
        client,
        tenant_id,
        group["id"],
        "speed",
        unit="ft",
        adjustable_in_play=True,
        pin=True,
        signed=True,
    )

    for field, value in (
        ("unit", None),
        ("adjustable_in_play", False),
        ("pin", False),
        ("signed", False),
    ):
        assert plain[field] == value
    assert (shown["unit"], shown["adjustable_in_play"], shown["pin"], shown["signed"]) == (
        "ft",
        True,
        True,
        True,
    )
    fetched = (await client.get(f"/tenants/{tenant_id}/stat-definitions/{shown['id']}")).json()
    assert fetched["unit"] == "ft"
    await delete_tenant(tenant_id)


async def test_a_unit_is_short_and_not_empty(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Vitals")

    for unit in ("", "x" * 33):
        response = await client.post(
            f"/tenants/{tenant_id}/stat-definitions",
            json={"stat_group_id": group["id"], "name": "speed", "value_type": "int", "unit": unit},
        )
        assert response.status_code == 422, unit
    await delete_tenant(tenant_id)


# --- order ---------------------------------------------------------------------


async def test_new_rows_go_last_and_a_given_position_is_kept(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    first = await _group(client, tenant_id, "Vitals")
    second = await _group(client, tenant_id, "Abilities")
    placed = await _group(client, tenant_id, "Notes", position=-1)

    assert [first["position"], second["position"], placed["position"]] == [0, 1, -1]
    assert await _listed(client, tenant_id, "stat-groups") == ["Notes", "Vitals", "Abilities"]

    a = await _definition(client, tenant_id, first["id"], "zeta")
    b = await _definition(client, tenant_id, first["id"], "alpha")
    other = await _definition(client, tenant_id, second["id"], "beta")
    assert (a["position"], b["position"]) == (0, 1)
    assert other["position"] == 0  # positions run per group
    await delete_tenant(tenant_id)


async def test_stat_definitions_list_in_group_then_definition_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    vitals = await _group(client, tenant_id, "Vitals")
    abilities = await _group(client, tenant_id, "Abilities")
    await _definition(client, tenant_id, vitals["id"], "speed")
    await _definition(client, tenant_id, vitals["id"], "armour_class")
    await _definition(client, tenant_id, abilities["id"], "strength")

    assert await _listed(client, tenant_id, "stat-definitions") == [
        "speed",
        "armour_class",
        "strength",
    ]
    # Groups are reordered, and the definitions follow their group.
    reordered = await client.put(
        f"/tenants/{tenant_id}/stat-groups/order",
        json={"stat_group_ids": [abilities["id"], vitals["id"]]},
    )
    assert reordered.status_code == 200, reordered.text
    assert [g["name"] for g in reordered.json()] == ["Abilities", "Vitals"]
    assert await _listed(client, tenant_id, "stat-definitions") == [
        "strength",
        "speed",
        "armour_class",
    ]
    await delete_tenant(tenant_id)


async def test_reordering_definitions_renumbers_them_and_checks_the_list(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Abilities")
    ids = [
        (await _definition(client, tenant_id, group["id"], name))["id"]
        for name in ("strength", "dexterity", "constitution")
    ]
    other = await _group(client, tenant_id, "Elsewhere")
    foreign = (await _definition(client, tenant_id, other["id"], "luck"))["id"]
    url = f"/tenants/{tenant_id}/stat-groups/{group['id']}/order"

    done = await client.put(url, json={"stat_definition_ids": [ids[2], ids[0], ids[1]]})

    assert done.status_code == 200, done.text
    assert [(d["name"], d["position"]) for d in done.json()] == [
        ("constitution", 0),
        ("strength", 1),
        ("dexterity", 2),
    ]
    for bad in (
        [ids[0], ids[1]],  # one missing
        [ids[0], ids[0], ids[1], ids[2]],  # one twice
        [ids[0], ids[1], ids[2], foreign],  # one that is not in the group
    ):
        response = await client.put(url, json={"stat_definition_ids": bad})
        assert response.status_code == 422, bad
    await delete_tenant(tenant_id)


async def test_reordering_groups_must_list_every_group_once(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    one = await _group(client, tenant_id, "One")
    await _group(client, tenant_id, "Two")

    response = await client.put(
        f"/tenants/{tenant_id}/stat-groups/order", json={"stat_group_ids": [one["id"]]}
    )

    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_an_entitys_stats_follow_the_vocabulary_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    vitals = await _group(client, tenant_id, "Vitals")
    abilities = await _group(client, tenant_id, "Abilities")
    # Made in the opposite order to the alphabet, so a name sort would be wrong.
    speed = await _definition(client, tenant_id, vitals["id"], "speed")
    hit_points = await _definition(client, tenant_id, vitals["id"], "hit_points")
    strength = await _definition(client, tenant_id, abilities["id"], "strength")
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="Brannoch")
        session.add(entity)
        await session.flush()
        for definition in (strength, hit_points, speed):
            session.add(
                EntityStat(
                    entity_id=entity.id,
                    stat_definition_id=uuid.UUID(definition["id"]),
                    tenant_id=tenant_id,
                    value_int=1,
                )
            )
        await session.commit()
        entity_id = entity.id

    detail = (await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")).json()
    assert [s["name"] for s in detail["stats"]] == ["speed", "hit_points", "strength"]

    await client.put(
        f"/tenants/{tenant_id}/stat-groups/{vitals['id']}/order",
        json={"stat_definition_ids": [hit_points["id"], speed["id"]]},
    )
    await client.put(
        f"/tenants/{tenant_id}/stat-groups/order",
        json={"stat_group_ids": [abilities["id"], vitals["id"]]},
    )
    detail = (await client.get(f"/tenants/{tenant_id}/entities/{entity_id}")).json()
    assert [s["name"] for s in detail["stats"]] == ["strength", "hit_points", "speed"]
    await delete_tenant(tenant_id)


# --- PATCH ---------------------------------------------------------------------


async def test_patching_a_definition_changes_only_what_is_sent(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Vitals")
    speed = await _definition(client, tenant_id, group["id"], "speed", unit="ft", pin=True)
    url = f"/tenants/{tenant_id}/stat-definitions/{speed['id']}"

    patched = await client.patch(url, json={"adjustable_in_play": True, "signed": True})
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert (body["unit"], body["pin"], body["adjustable_in_play"], body["signed"]) == (
        "ft",
        True,
        True,
        True,
    )
    assert body["name"] == "speed"

    cleared = await client.patch(url, json={"unit": None})
    assert cleared.json()["unit"] is None
    moved = await client.patch(url, json={"position": 7})
    assert moved.json()["position"] == 7
    await delete_tenant(tenant_id)


async def test_a_flag_cannot_be_set_to_null_and_name_and_type_are_not_patchable(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Vitals")
    speed = await _definition(client, tenant_id, group["id"], "speed")
    url = f"/tenants/{tenant_id}/stat-definitions/{speed['id']}"

    assert (await client.patch(url, json={"pin": None})).status_code == 422
    unchanged = await client.patch(url, json={"name": "renamed", "value_type": "text"})
    assert unchanged.status_code == 200
    assert unchanged.json()["name"] == "speed"
    assert unchanged.json()["value_type"] == "int"
    await delete_tenant(tenant_id)


async def test_patching_a_group(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    vitals = await _group(client, tenant_id, "Vitals")
    await _group(client, tenant_id, "Abilities")
    url = f"/tenants/{tenant_id}/stat-groups/{vitals['id']}"

    patched = await client.patch(
        url, json={"name": "Hit points", "priority": 4, "mandatory": True, "position": 9}
    )

    assert patched.status_code == 200, patched.text
    assert (patched.json()["name"], patched.json()["priority"]) == ("Hit points", 4)
    assert patched.json()["mandatory"] is True
    assert patched.json()["position"] == 9
    assert (await client.patch(url, json={"name": "Hit points"})).status_code == 200  # no change
    taken = await client.patch(url, json={"name": "Abilities"})
    assert taken.status_code == 409
    assert (await client.patch(url, json={"priority": None})).status_code == 422
    await delete_tenant(tenant_id)


async def test_only_a_tenant_administrator_may_edit_the_vocabulary(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Vitals")
    speed = await _definition(client, tenant_id, group["id"], "speed")
    await make_plain_participant(tenant_id, test_user_id)

    patch = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{speed['id']}", json={"pin": True}
    )
    reorder = await client.put(
        f"/tenants/{tenant_id}/stat-groups/order", json={"stat_group_ids": [group["id"]]}
    )

    assert patch.status_code in (403, 404)
    assert reorder.status_code in (403, 404)
    await delete_tenant(tenant_id)
