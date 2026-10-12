"""ADR 0276: where a stat value comes from (`from_entity`, `computed`) and the
explanation read any participant may call, through the real API.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_plain_participant, make_tenant
from httpx import AsyncClient

from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    StatDefinition,
    StatGroup,
    StatValueType,
    User,
)

MODIFIER = {"kind": "linear", "multiplier": 0.5, "offset": -5, "round_mode": "floor"}


async def _definitions(tenant_id: uuid.UUID, **stats: StatValueType) -> dict[str, uuid.UUID]:
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=tenant_id, name="sheet")
        session.add(group)
        await session.flush()
        ids = {}
        for name, value_type in stats.items():
            definition = StatDefinition(
                tenant_id=tenant_id, stat_group_id=group.id, name=name, value_type=value_type
            )
            session.add(definition)
            await session.flush()
            ids[name] = definition.id
        await session.commit()
    return ids


async def _entity(
    tenant_id: uuid.UUID,
    name: str,
    *,
    prototype: uuid.UUID | None = None,
    stats: dict[uuid.UUID, int] | None = None,
    inside: tuple[uuid.UUID, int] | None = None,
) -> uuid.UUID:
    """`inside` is (container, quantity): this entity sits directly in the container."""
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        if prototype is not None:
            session.add(
                EntityPrototype(entity_id=entity.id, prototype_id=prototype, tenant_id=tenant_id)
            )
        for definition_id, value in (stats or {}).items():
            session.add(
                EntityStat(
                    entity_id=entity.id,
                    stat_definition_id=definition_id,
                    tenant_id=tenant_id,
                    value_int=value,
                )
            )
        if inside is not None:
            session.add(
                Containment(
                    child_entity_id=entity.id,
                    parent_entity_id=inside[0],
                    tenant_id=tenant_id,
                    quantity=inside[1],
                )
            )
        await session.commit()
        return entity.id


async def _formula(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID, stat: uuid.UUID, body: dict
) -> None:
    response = await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/computed-stats/{stat}", json=body
    )
    assert response.status_code == 200, response.text


def _stats(detail: dict) -> dict[str, dict]:
    return {s["name"]: s for s in detail["stats"]}


async def _explain(
    client: AsyncClient, tenant_id: uuid.UUID, entity_id: uuid.UUID, stat: uuid.UUID
):
    return await client.get(f"/tenants/{tenant_id}/entities/{entity_id}/stats/{stat}/explanation")


# --- from_entity and computed ------------------------------------------------


async def test_a_stat_says_whose_it_is_and_where_an_inherited_one_comes_from(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(tenant_id, speed=StatValueType.INT, hit_points=StatValueType.INT)
    dwarf = await _entity(tenant_id, "Dwarf", stats={ids["speed"]: 25})
    brannoch = await _entity(tenant_id, "Brannoch", prototype=dwarf, stats={ids["hit_points"]: 31})

    response = await client.get(f"/tenants/{tenant_id}/entities/{brannoch}")

    assert response.status_code == 200, response.text
    stats = _stats(response.json())
    assert stats["hit_points"]["own"] is True
    assert stats["hit_points"]["from_entity"] is None
    assert stats["speed"]["own"] is False
    assert stats["speed"]["from_entity"] == {"id": str(dwarf), "name": "Dwarf", "quantity": None}
    assert stats["speed"]["computed"] is False
    await delete_tenant(tenant_id)


async def test_an_inherited_formula_is_calculated_and_names_its_holder(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(tenant_id, strength=StatValueType.INT, modifier=StatValueType.INT)
    fighter = await _entity(tenant_id, "Fighter")
    await _formula(
        client,
        tenant_id,
        fighter,
        ids["modifier"],
        {**MODIFIER, "source_stat_definition_id": str(ids["strength"])},
    )
    strong = await _entity(tenant_id, "Strong", prototype=fighter, stats={ids["strength"]: 18})

    stats = _stats((await client.get(f"/tenants/{tenant_id}/entities/{strong}")).json())

    assert stats["modifier"]["value"] == 4
    assert stats["modifier"]["computed"] is True
    assert stats["modifier"]["own"] is False
    assert stats["modifier"]["from_entity"]["name"] == "Fighter"
    assert stats["strength"]["computed"] is False
    await delete_tenant(tenant_id)


async def test_an_own_formula_is_calculated_and_own(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(tenant_id, strength=StatValueType.INT, modifier=StatValueType.INT)
    hero = await _entity(tenant_id, "Hero", stats={ids["strength"]: 14})
    await _formula(
        client,
        tenant_id,
        hero,
        ids["modifier"],
        {**MODIFIER, "source_stat_definition_id": str(ids["strength"])},
    )

    stats = _stats((await client.get(f"/tenants/{tenant_id}/entities/{hero}")).json())

    assert stats["modifier"]["own"] is True
    assert stats["modifier"]["computed"] is True
    assert stats["modifier"]["from_entity"] is None
    await delete_tenant(tenant_id)


# --- the explanation ---------------------------------------------------------


async def test_explaining_a_stored_value(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(tenant_id, speed=StatValueType.INT)
    dwarf = await _entity(tenant_id, "Dwarf", stats={ids["speed"]: 25})
    brannoch = await _entity(tenant_id, "Brannoch", prototype=dwarf)

    own = await _explain(client, tenant_id, dwarf, ids["speed"])
    inherited = await _explain(client, tenant_id, brannoch, ids["speed"])

    assert own.status_code == 200, own.text
    assert own.json() == {
        "stat_definition_id": str(ids["speed"]),
        "name": "speed",
        "value": 25,
        "own": True,
        "computed": False,
        "from_entity": None,
        "formula": None,
        "inputs": [],
        "contents": None,
    }
    assert inherited.json()["from_entity"]["name"] == "Dwarf"
    assert inherited.json()["own"] is False
    await delete_tenant(tenant_id)


async def test_explaining_an_inherited_linear_formula(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The case a player asks about: the formula is on the prototype, the
    input is this being's own."""
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(tenant_id, strength=StatValueType.INT, modifier=StatValueType.INT)
    fighter = await _entity(tenant_id, "Fighter")
    await _formula(
        client,
        tenant_id,
        fighter,
        ids["modifier"],
        {**MODIFIER, "source_stat_definition_id": str(ids["strength"])},
    )
    strong = await _entity(tenant_id, "Strong", prototype=fighter, stats={ids["strength"]: 18})

    response = await _explain(client, tenant_id, strong, ids["modifier"])

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["value"] == 4
    assert body["computed"] is True
    assert body["from_entity"]["name"] == "Fighter"
    assert body["formula"]["kind"] == "linear"
    assert body["formula"]["multiplier"] == "0.5"
    assert body["formula"]["offset"] == "-5"
    assert body["inputs"] == [
        {"stat_definition_id": str(ids["strength"]), "name": "strength", "value": 18}
    ]
    assert body["contents"] is None
    await delete_tenant(tenant_id)


async def test_explaining_a_sum_lists_each_term_that_has_a_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(
        tenant_id,
        dexterity_modifier=StatValueType.INT,
        worn_bonus=StatValueType.INT,
        armour_class=StatValueType.INT,
    )
    hero = await _entity(
        tenant_id, "Hero", stats={ids["dexterity_modifier"]: 2, ids["worn_bonus"]: 3}
    )
    await _formula(
        client,
        tenant_id,
        hero,
        ids["armour_class"],
        {
            "kind": "sum",
            "terms": [
                {"stat_definition_id": str(ids["dexterity_modifier"]), "coefficient": 1},
                {"stat_definition_id": str(ids["worn_bonus"]), "coefficient": 1},
            ],
            "offset": 10,
        },
    )

    body = (await _explain(client, tenant_id, hero, ids["armour_class"])).json()

    assert body["value"] == 15
    assert body["formula"]["kind"] == "sum"
    assert body["formula"]["offset"] == "10"
    assert [(i["name"], i["value"]) for i in body["inputs"]] == [
        ("dexterity_modifier", 2),
        ("worn_bonus", 3),
    ]
    await delete_tenant(tenant_id)


async def test_explaining_a_contents_formula_counts_what_is_inside(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Its inputs are spread over what is inside, so it says how many things it counted."""
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(tenant_id, weight=StatValueType.INT, load=StatValueType.INT)
    pack = await _entity(tenant_id, "Pack")
    await _entity(tenant_id, "Anvil", stats={ids["weight"]: 100}, inside=(pack, 1))
    await _entity(tenant_id, "Nail", stats={ids["weight"]: 2}, inside=(pack, 5))
    await _formula(
        client,
        tenant_id,
        pack,
        ids["load"],
        {"kind": "contents", "source_stat_definition_id": str(ids["weight"])},
    )

    body = (await _explain(client, tenant_id, pack, ids["load"])).json()

    assert body["value"] == 110
    assert body["formula"]["kind"] == "contents"
    assert body["inputs"] == []
    assert body["contents"] == {
        "source_stat_definition_id": str(ids["weight"]),
        "source_name": "weight",
        "things": 2,
    }
    await delete_tenant(tenant_id)


# --- who may ask, and what is not there ---------------------------------------


async def test_an_entity_with_no_value_for_the_stat_is_a_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(tenant_id, speed=StatValueType.INT)
    nobody = await _entity(tenant_id, "Nobody")

    response = await _explain(client, tenant_id, nobody, ids["speed"])

    assert response.status_code == 404
    assert response.json()["title"] == "This entity has no value for that stat"
    await delete_tenant(tenant_id)


async def test_a_stat_definition_of_another_tenant_is_a_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other_tenant = await make_tenant(test_user_id)
    ids = await _definitions(other_tenant, speed=StatValueType.INT)
    hero = await _entity(tenant_id, "Hero")

    response = await _explain(client, tenant_id, hero, ids["speed"])

    assert response.status_code == 404
    await delete_tenant(tenant_id)
    await delete_tenant(other_tenant)


async def test_a_plain_participant_may_ask_but_a_stranger_may_not(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Unlike the preview under `computed-stats`, which is for administrators."""
    tenant_id = await make_tenant(test_user_id)
    ids = await _definitions(tenant_id, speed=StatValueType.INT)
    hero = await _entity(tenant_id, "Hero", stats={ids["speed"]: 30})
    await make_plain_participant(tenant_id, test_user_id)

    as_player = await _explain(client, tenant_id, hero, ids["speed"])
    assert as_player.status_code == 200, as_player.text

    async with admin_session_factory() as session:
        stranger = User(authgear_subject_id=f"authgear|stranger-{uuid.uuid4()}")
        session.add(stranger)
        await session.commit()
        stranger_id = stranger.id
    stranger_tenant = await make_tenant(stranger_id)
    as_stranger = await _explain(client, stranger_tenant, hero, ids["speed"])
    assert as_stranger.status_code == 404

    await delete_tenant(tenant_id)
    await delete_tenant(stranger_tenant)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, stranger_id))
        await session.commit()
