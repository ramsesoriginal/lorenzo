"""ADR 0385: renaming a stat definition and an enum value, the rewrite of every stored copy of an
enum value's text, an enum value a formula returns counting as in use, and what a library sees.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup
from conftest import delete_tenant, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text
from test_repository_updates import _local, _world

from lorenzo_api.models import (
    ComputedStatComparison,
    Entity,
    EntityStat,
    StatDefinition,
    StatDefinitionEnumValue,
)


async def _group(client: AsyncClient, tenant_id: uuid.UUID, name: str = "Vitals") -> dict:
    response = await client.post(f"/tenants/{tenant_id}/stat-groups", json={"name": name})
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


async def _entity(tenant_id: uuid.UUID, name: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.commit()
        return entity.id


def _option(definition: dict, value: str) -> dict:
    return next(o for o in definition["enum_options"] if o["value"] == value)


# --- a definition's name -------------------------------------------------------


async def test_a_definition_is_renamed_and_keeps_its_type_group_and_values(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    speed = await _definition(client, tenant_id, group["id"], "speed", unit="ft")
    entity = await _entity(tenant_id, "Ashfang")
    await client.put(
        f"/tenants/{tenant_id}/entities/{entity}/stats/{speed['id']}", json={"value": 30}
    )
    url = f"/tenants/{tenant_id}/stat-definitions/{speed['id']}"

    renamed = await client.patch(url, json={"name": "walking speed", "pin": True})

    assert renamed.status_code == 200, renamed.text
    body = renamed.json()
    assert (body["name"], body["pin"], body["unit"]) == ("walking speed", True, "ft")
    assert (body["value_type"], body["stat_group_id"]) == ("int", group["id"])
    stats = (await client.get(f"/tenants/{tenant_id}/entities/{entity}")).json()["stats"]
    assert [(s["name"], s["value"]) for s in stats] == [("walking speed", 30)]
    assert (await client.patch(url, json={"name": "walking speed"})).status_code == 200
    await delete_tenant(tenant_id)


async def test_a_definition_name_that_is_taken_or_empty_is_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    speed = await _definition(client, tenant_id, group["id"], "speed")
    await _definition(client, tenant_id, group["id"], "reach")
    url = f"/tenants/{tenant_id}/stat-definitions/{speed['id']}"

    taken = await client.patch(url, json={"name": "reach"})
    empty = await client.patch(url, json={"name": ""})
    null = await client.patch(url, json={"name": None})

    assert taken.status_code == 409
    assert taken.json()["type"].endswith("stat-definition-name-taken")
    assert (empty.status_code, null.status_code) == (422, 422)
    assert (await client.get(url)).json()["name"] == "speed"
    await delete_tenant(tenant_id)


async def test_a_stat_the_api_reads_by_name_is_not_renamed(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    weight = await _definition(client, tenant_id, group["id"], "weight")
    url = f"/tenants/{tenant_id}/stat-definitions/{weight['id']}"

    refused = await client.patch(url, json={"name": "heft"})
    still = await client.patch(url, json={"name": "weight", "pin": True})
    made = await _definition(client, tenant_id, group["id"], "mass")
    renamed_to = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{made['id']}", json={"name": "size"}
    )

    assert refused.status_code == 409
    assert refused.json()["type"].endswith("stat-name-reserved")
    assert still.status_code == 200  # no rename, nothing refused
    assert renamed_to.status_code == 200  # as making one called `size` is
    await delete_tenant(tenant_id)


async def test_a_plain_participant_may_not_rename(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id)
    speed = await _definition(client, tenant_id, group["id"], "speed")
    await make_plain_participant(tenant_id, test_user_id)

    patch = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{speed['id']}", json={"name": "pace"}
    )
    value = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{speed['id']}/enum-values/{uuid.uuid4()}",
        json={"value": "x"},
    )

    assert patch.status_code in (403, 404)
    assert value.status_code in (403, 404)
    await delete_tenant(tenant_id)


# --- an enum value -------------------------------------------------------------


async def _rarity(client: AsyncClient, tenant_id: uuid.UUID) -> dict:
    group = await _group(client, tenant_id, "Looks")
    return await _definition(
        client,
        tenant_id,
        group["id"],
        "rarity",
        value_type="enum",
        enum_values=["common", "rare", "legendary"],
    )


async def test_a_definition_says_which_value_has_which_id_and_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)

    rarity = await _rarity(client, tenant_id)

    assert rarity["enum_values"] == ["common", "rare", "legendary"]
    assert [(o["value"], o["sort_order"]) for o in rarity["enum_options"]] == [
        ("common", 0),
        ("rare", 1),
        ("legendary", 2),
    ]
    assert len({o["id"] for o in rarity["enum_options"]}) == 3
    await delete_tenant(tenant_id)


async def test_renaming_an_enum_value_rewrites_what_holds_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    rarity = await _rarity(client, tenant_id)
    group_id = rarity["stat_group_id"]
    tier = await _definition(
        client, tenant_id, group_id, "tier", value_type="enum", enum_values=["a", "b"]
    )
    power = await _definition(client, tenant_id, group_id, "power")
    sword = await _entity(tenant_id, "Sword")
    axe = await _entity(tenant_id, "Axe")
    await client.put(
        f"/tenants/{tenant_id}/entities/{axe}/stats/{rarity['id']}", json={"value": "rare"}
    )
    await client.put(
        f"/tenants/{tenant_id}/entities/{sword}/stats/{tier['id']}", json={"value": "a"}
    )
    await client.put(
        f"/tenants/{tenant_id}/entities/{sword}/stats/{power['id']}", json={"value": 80}
    )
    formula = await client.put(
        f"/tenants/{tenant_id}/entities/{sword}/computed-stats/{rarity['id']}",
        json={
            "kind": "comparison",
            "left_stat_definition_id": power["id"],
            "comparator": "gt",
            "right_constant": 50,
            "true_value": "rare",
            "false_value": "common",
        },
    )
    assert formula.status_code in (200, 201), formula.text
    url = (
        f"/tenants/{tenant_id}/stat-definitions/{rarity['id']}"
        f"/enum-values/{_option(rarity, 'rare')['id']}"
    )

    renamed = await client.patch(url, json={"value": "scarce"})

    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["enum_values"] == ["common", "scarce", "legendary"]
    assert _option(renamed.json(), "scarce")["id"] == _option(rarity, "rare")["id"]
    async with admin_session_factory() as session:
        held = (
            await session.scalars(
                select(EntityStat.value_text).where(
                    EntityStat.stat_definition_id == uuid.UUID(rarity["id"])
                )
            )
        ).all()
        other = await session.scalar(
            select(EntityStat.value_text).where(
                EntityStat.stat_definition_id == uuid.UUID(tier["id"])
            )
        )
        comparison = (
            await session.execute(
                select(ComputedStatComparison.true_value, ComputedStatComparison.false_value)
            )
        ).one()
    assert held == ["scarce"]  # the axe, which holds it
    assert other == "a"  # another stat's value is its own
    assert tuple(comparison) == ("scarce", "common")
    shown = (await client.get(f"/tenants/{tenant_id}/entities/{sword}")).json()["stats"]
    assert {s["name"]: s["value"] for s in shown}["rarity"] == "scarce"
    await delete_tenant(tenant_id)


async def test_renaming_an_enum_value_to_a_taken_one_changes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    rarity = await _rarity(client, tenant_id)
    sword = await _entity(tenant_id, "Sword")
    await client.put(
        f"/tenants/{tenant_id}/entities/{sword}/stats/{rarity['id']}", json={"value": "rare"}
    )
    url = (
        f"/tenants/{tenant_id}/stat-definitions/{rarity['id']}"
        f"/enum-values/{_option(rarity, 'rare')['id']}"
    )

    taken = await client.patch(url, json={"value": "common"})
    same = await client.patch(url, json={"value": "rare"})
    empty = await client.patch(url, json={"value": ""})
    unknown = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{rarity['id']}/enum-values/{uuid.uuid4()}",
        json={"value": "mythic"},
    )

    assert taken.status_code == 409
    assert taken.json()["type"].endswith("stat-enum-value-already-exists")
    assert same.status_code == 200
    assert empty.status_code == 422
    assert unknown.status_code == 404
    shown = (await client.get(f"/tenants/{tenant_id}/entities/{sword}")).json()["stats"]
    assert {s["name"]: s["value"] for s in shown}["rarity"] == "rare"
    await delete_tenant(tenant_id)


async def test_an_enum_value_is_reordered_by_its_sort_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    rarity = await _rarity(client, tenant_id)
    url = f"/tenants/{tenant_id}/stat-definitions/{rarity['id']}/enum-values"

    moved = await client.patch(
        f"{url}/{_option(rarity, 'legendary')['id']}", json={"sort_order": -1}
    )
    null = await client.patch(f"{url}/{_option(rarity, 'rare')['id']}", json={"sort_order": None})

    assert moved.status_code == 200, moved.text
    assert moved.json()["enum_values"] == ["legendary", "common", "rare"]
    assert null.status_code == 422
    await delete_tenant(tenant_id)


async def test_the_value_none_of_binding_is_not_renamed(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    group = await _group(client, tenant_id, "Carrying")
    binding = await _definition(
        client,
        tenant_id,
        group["id"],
        "binding",
        value_type="enum",
        enum_values=["none", "bound"],
    )
    url = f"/tenants/{tenant_id}/stat-definitions/{binding['id']}/enum-values"

    refused = await client.patch(f"{url}/{_option(binding, 'none')['id']}", json={"value": "free"})
    allowed = await client.patch(
        f"{url}/{_option(binding, 'bound')['id']}", json={"value": "attuned"}
    )

    assert refused.status_code == 409
    assert refused.json()["type"].endswith("stat-name-reserved")
    assert allowed.status_code == 200
    await delete_tenant(tenant_id)


async def test_a_value_a_formula_returns_is_in_use(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    rarity = await _rarity(client, tenant_id)
    power = await _definition(client, tenant_id, rarity["stat_group_id"], "power")
    sword = await _entity(tenant_id, "Sword")
    await client.put(
        f"/tenants/{tenant_id}/entities/{sword}/computed-stats/{rarity['id']}",
        json={
            "kind": "comparison",
            "left_stat_definition_id": power["id"],
            "comparator": "gt",
            "right_constant": 50,
            "true_value": "legendary",
            "false_value": "common",
        },
    )
    url = f"/tenants/{tenant_id}/stat-definitions/{rarity['id']}/enum-values"

    returned = await client.delete(f"{url}/{_option(rarity, 'legendary')['id']}")
    free = await client.delete(f"{url}/{_option(rarity, 'rare')['id']}")

    assert returned.status_code == 409
    assert "returned by 1 formula" in returned.json()["detail"]
    assert free.status_code == 200
    await delete_tenant(tenant_id)


async def test_every_column_that_can_hold_an_enum_value_is_one_the_rename_rewrites() -> None:
    """The columns named like the text of an enum value are the three ADR 0385 rewrites. Another
    one appearing (a new formula kind with texts, say) fails here until it is rewritten too."""
    async with admin_session_factory() as session:
        found = {
            (table, column)
            for table, column in (
                await session.execute(
                    text(
                        "SELECT table_name, column_name FROM information_schema.columns c "
                        "JOIN information_schema.tables t USING (table_schema, table_name) "
                        "WHERE table_schema = 'public' AND t.table_type = 'BASE TABLE' "
                        "AND data_type = 'text' "
                        "AND (column_name LIKE '%value_text' OR column_name LIKE '%true_value' "
                        "OR column_name LIKE '%false_value' OR column_name LIKE '%enum_value%')"
                    )
                )
            ).all()
        }
    assert found == {
        ("entity_stat", "value_text"),
        ("computed_stat_comparison", "true_value"),
        ("computed_stat_comparison", "false_value"),
    }


# --- what a library sees ---------------------------------------------------------


async def test_a_definition_rename_reaches_a_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    url = f"/tenants/{world.table}/repositories/{world.repository}"
    try:
        renamed = await world.author.patch(
            f"/tenants/{world.repository}/stat-definitions/{world.ids['Strength']}",
            json={"name": "Might"},
        )
        assert renamed.status_code == 200, renamed.text

        updates = (await world.gm.get(f"{url}/updates")).json()
        assert [(r["name"], [f["field"] for f in r["fields"]]) for r in updates["changed"]] == [
            ("Strength", ["name"])
        ]
        applied = await world.gm.post(
            f"{url}/updates",
            json={
                "actions": [
                    {
                        "kind": "stat_definition",
                        "source_id": str(world.ids["Strength"]),
                        "action": "apply",
                    }
                ]
            },
        )
        assert applied.status_code == 200, applied.text
        async with admin_session_factory() as session:
            names = set(
                await session.scalars(
                    select(StatDefinition.name).where(StatDefinition.tenant_id == world.table)
                )
            )
        assert {"Might", "Mood", "Speed"} == names
    finally:
        await cleanup([world.table, world.repository], [world.author, world.gm])


async def test_an_enum_rename_reaches_a_library_as_an_addition_and_a_refused_removal(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    url = f"/tenants/{world.table}/repositories/{world.repository}"
    try:
        local = await _local(world)
        async with admin_session_factory() as session:
            mood = (
                await session.scalars(
                    select(StatDefinition).where(
                        StatDefinition.tenant_id == world.table, StatDefinition.name == "Mood"
                    )
                )
            ).one()
            session.add(
                EntityStat(
                    entity_id=local[world.ids["Longsword"]],
                    stat_definition_id=mood.id,
                    tenant_id=world.table,
                    value_text="calm",
                )
            )
            calm = (
                await session.scalars(
                    select(StatDefinitionEnumValue.id).where(
                        StatDefinitionEnumValue.stat_definition_id == world.ids["Mood"]
                    )
                )
            ).one()
            await session.commit()
        renamed = await world.author.patch(
            f"/tenants/{world.repository}/stat-definitions/{world.ids['Mood']}/enum-values/{calm}",
            json={"value": "serene"},
        )
        assert renamed.status_code == 200, renamed.text

        updates = (await world.gm.get(f"{url}/updates")).json()
        mood_row = next(r for r in updates["changed"] if r["name"] == "Mood")
        change = next(f for f in mood_row["fields"] if f["field"] == "enum_values")
        assert (change["added"], change["removed"]) == (["serene"], ["calm"])

        applied = await world.gm.post(
            f"{url}/updates",
            json={
                "actions": [
                    {
                        "kind": "stat_definition",
                        "source_id": str(world.ids["Mood"]),
                        "action": "apply",
                    }
                ]
            },
        )
        assert applied.status_code == 200, applied.text
        assert [n["reason"] for n in applied.json()["not_applied"]] == [
            "'calm' is still in use here"
        ]
        async with admin_session_factory() as session:
            allowed = set(
                await session.scalars(
                    select(StatDefinitionEnumValue.value).where(
                        StatDefinitionEnumValue.stat_definition_id == mood.id
                    )
                )
            )
            held = await session.scalar(
                select(EntityStat.value_text).where(EntityStat.stat_definition_id == mood.id)
            )
        assert allowed == {"calm", "serene"}
        assert held == "calm"  # the library's entry keeps the value it held
    finally:
        await cleanup([world.table, world.repository], [world.author, world.gm])
