"""ADR 0444: `min` and `max` formulas, and a bool and an enum read as numbers, through the real
API - evaluation against the entity being read, the write-time checks, kind changes, preview,
explanation, dependents, the guard on an enum's order, and RLS on the new tables.
"""

import uuid
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text
from test_api_computed_stats import _entity, _put, _sheet, _stats

from lorenzo_api.db import engine
from lorenzo_api.models import (
    ComputedStatExtremum,
    ComputedStatExtremumInput,
    EntityPrototype,
    EntityStat,
    StatDefinition,
    StatDefinitionEnumValue,
    StatGroup,
    StatValueType,
)


def _stat(stat: uuid.UUID) -> dict:
    return {"stat_definition_id": str(stat)}


def _const(value: float) -> dict:
    return {"constant": value}


def _extremum(kind: str, *inputs: dict, round_mode: str = "none") -> dict:
    return {"kind": kind, "inputs": list(inputs), "round_mode": round_mode}


async def _add_enum(
    tenant_id: uuid.UUID, name: str, values: dict[str, int]
) -> uuid.UUID:
    """An enum stat in the tenant's `abilities` group, its values with the given `sort_order`."""
    async with admin_session_factory() as session:
        group_id = await session.scalar(
            select(StatGroup.id).where(StatGroup.tenant_id == tenant_id)
        )
        definition = StatDefinition(
            tenant_id=tenant_id,
            stat_group_id=group_id,
            name=name,
            value_type=StatValueType.ENUM,
        )
        session.add(definition)
        await session.flush()
        for value, sort_order in values.items():
            session.add(
                StatDefinitionEnumValue(
                    tenant_id=tenant_id,
                    stat_definition_id=definition.id,
                    value=value,
                    sort_order=sort_order,
                )
            )
        await session.commit()
        return definition.id


async def _hold(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    stat: uuid.UUID,
    *,
    flag: bool | None = None,
    text_value: str | None = None,
) -> None:
    async with admin_session_factory() as session:
        session.add(
            EntityStat(
                entity_id=entity_id,
                stat_definition_id=stat,
                tenant_id=tenant_id,
                value_bool=flag,
                value_text=text_value,
            )
        )
        await session.commit()


# --- evaluation ---------------------------------------------------------------------------


async def test_a_min_caps_and_a_max_floors(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    """Dexterity 18 in armour that caps the modifier at +2 gives 2, not 4; a floor keeps hit points
    from going below zero. Each instance reads its own stats, as every formula does."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        dex_modifier=StatValueType.INT,
        dex_cap=StatValueType.INT,
        dex_bonus=StatValueType.INT,
        hit_points=StatValueType.INT,
        hit_points_shown=StatValueType.INT,
    )
    hero = await _entity(tenant_id, "Hero")
    capped = await _put(
        client,
        sheet.formula_url(hero, "dex_bonus"),
        _extremum("min", _stat(sheet["dex_modifier"]), _stat(sheet["dex_cap"])),
    )
    await _put(
        client,
        sheet.formula_url(hero, "hit_points_shown"),
        _extremum("max", _stat(sheet["hit_points"]), _const(0)),
    )
    fast = await _entity(
        tenant_id, "Fast", prototype=hero, stats={sheet["dex_modifier"]: 4, sheet["dex_cap"]: 2}
    )
    slow = await _entity(
        tenant_id,
        "Slow",
        prototype=hero,
        stats={sheet["dex_modifier"]: -1, sheet["dex_cap"]: 2, sheet["hit_points"]: -3},
    )

    assert capped["formula"]["kind"] == "min"
    assert [i.get("stat_definition_id") for i in capped["formula"]["inputs"]] == [
        str(sheet["dex_modifier"]),
        str(sheet["dex_cap"]),
    ]
    fasts = await _stats(client, tenant_id, fast)
    assert fasts["dex_bonus"] == 2
    # Fast holds no hit points: the stat an input reads has no value, so the formula has none.
    assert "hit_points_shown" not in fasts
    slows = await _stats(client, tenant_id, slow)
    assert (slows["dex_bonus"], slows["hit_points_shown"]) == (-1, 0)
    await delete_tenant(tenant_id)


async def test_a_min_of_constants_and_mixed_inputs_takes_the_smallest(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, a=StatValueType.INT, b=StatValueType.INT, fixed=StatValueType.INT
    )
    hero = await _entity(tenant_id, "Hero", stats={sheet["a"]: 7, sheet["b"]: 3})

    await _put(client, sheet.formula_url(hero, "fixed"), _extremum("max", _const(2), _const(9)))
    assert (await _stats(client, tenant_id, hero))["fixed"] == 9
    await _put(
        client,
        sheet.formula_url(hero, "fixed"),
        _extremum("min", _stat(sheet["a"]), _stat(sheet["b"]), _const(5), _stat(sheet["a"])),
    )
    assert (await _stats(client, tenant_id, hero))["fixed"] == 3
    await delete_tenant(tenant_id)


async def test_a_min_over_a_float_rounds_for_an_int_target(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, speed=StatValueType.FLOAT, whole=StatValueType.INT, exact=StatValueType.FLOAT
    )
    hero = await _entity(tenant_id, "Hero")
    async with admin_session_factory() as session:
        session.add(
            EntityStat(
                entity_id=hero,
                stat_definition_id=sheet["speed"],
                tenant_id=tenant_id,
                value_float=7.5,
            )
        )
        await session.commit()

    refused = await client.put(
        sheet.formula_url(hero, "whole"), json=_extremum("min", _stat(sheet["speed"]), _const(9))
    )
    await _put(
        client,
        sheet.formula_url(hero, "whole"),
        _extremum("min", _stat(sheet["speed"]), _const(9), round_mode="floor"),
    )
    await _put(
        client, sheet.formula_url(hero, "exact"), _extremum("min", _stat(sheet["speed"]), _const(9))
    )

    assert refused.status_code == 422
    assert "rounding mode" in refused.json()["detail"]
    stats = await _stats(client, tenant_id, hero)
    assert (stats["whole"], stats["exact"]) == (7, 7.5)
    await delete_tenant(tenant_id)


# --- a bool and an enum as numbers ----------------------------------------------------------


async def test_a_bool_is_one_or_zero_in_linear_sum_min_and_max(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        proficient=StatValueType.BOOL,
        proficiency=StatValueType.INT,
        bonus=StatValueType.INT,
        total=StatValueType.INT,
        either=StatValueType.INT,
    )
    trained = await _entity(tenant_id, "Trained", stats={sheet["proficiency"]: 3})
    await _hold(tenant_id, trained, sheet["proficient"], flag=True)
    untrained = await _entity(tenant_id, "Untrained", stats={sheet["proficiency"]: 3})
    await _hold(tenant_id, untrained, sheet["proficient"], flag=False)
    proto = await _entity(tenant_id, "Proto")
    await _put(
        client,
        sheet.formula_url(proto, "bonus"),
        {
            "kind": "linear",
            "source_stat_definition_id": str(sheet["proficient"]),
            "multiplier": 3,
        },
    )
    await _put(
        client,
        sheet.formula_url(proto, "total"),
        {
            "kind": "sum",
            "terms": [
                {"stat_definition_id": str(sheet["proficient"]), "coefficient": 10},
                {"stat_definition_id": str(sheet["proficiency"]), "coefficient": 1},
            ],
        },
    )
    await _put(
        client,
        sheet.formula_url(proto, "either"),
        _extremum("max", _stat(sheet["proficient"]), _stat(sheet["bonus"])),
    )
    async with admin_session_factory() as session:
        for entity in (trained, untrained):
            session.add(EntityPrototype(entity_id=entity, prototype_id=proto, tenant_id=tenant_id))
        await session.commit()

    on = await _stats(client, tenant_id, trained)
    off = await _stats(client, tenant_id, untrained)

    assert (on["bonus"], on["total"], on["either"]) == (3, 13, 3)
    assert (off["bonus"], off["total"], off["either"]) == (0, 3, 0)
    await delete_tenant(tenant_id)


async def test_an_enum_is_its_sort_order_not_its_position(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The values are listed common, rare, legendary but numbered 10, 5, 30: a formula reads 5 for
    `rare`, as the author numbered it."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, rank_score=StatValueType.INT, capped=StatValueType.INT)
    tier = await _add_enum(tenant_id, "tier", {"common": 10, "rare": 5, "legendary": 30})
    sheet.ids["tier"] = tier
    proto = await _entity(tenant_id, "Proto")
    await _put(
        client,
        sheet.formula_url(proto, "rank_score"),
        {"kind": "linear", "source_stat_definition_id": str(tier), "multiplier": 2, "offset": 1},
    )
    await _put(
        client,
        sheet.formula_url(proto, "capped"),
        _extremum("min", _stat(tier), _const(20)),
    )
    things = {}
    for label in ("common", "rare", "legendary"):
        thing = await _entity(tenant_id, label.title())
        async with admin_session_factory() as session:
            session.add(EntityPrototype(entity_id=thing, prototype_id=proto, tenant_id=tenant_id))
            await session.commit()
        await _hold(tenant_id, thing, tier, text_value=label)
        things[label] = thing

    scores = {
        label: (await _stats(client, tenant_id, thing))
        for label, thing in things.items()
    }

    assert [(s["rank_score"], s["capped"]) for s in scores.values()] == [(21, 10), (11, 5), (61, 20)]
    await delete_tenant(tenant_id)


async def test_a_text_stat_is_still_refused_and_a_comparison_still_reads_numbers_only(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        name=StatValueType.TEXT,
        flag=StatValueType.BOOL,
        total=StatValueType.INT,
        verdict=StatValueType.BOOL,
    )
    entity = await _entity(tenant_id, "Hero")

    text_in_a_min = await client.put(
        sheet.formula_url(entity, "total"), json=_extremum("min", _stat(sheet["name"]), _const(1))
    )
    bool_in_a_comparison = await client.put(
        sheet.formula_url(entity, "verdict"),
        json={
            "kind": "comparison",
            "left_stat_definition_id": str(sheet["flag"]),
            "comparator": "ge",
            "right_constant": 1,
        },
    )

    assert text_in_a_min.status_code == 422
    assert bool_in_a_comparison.status_code == 422
    await delete_tenant(tenant_id)


# --- write-time checks -------------------------------------------------------------------------


async def test_min_and_max_type_and_shape_checks(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        a=StatValueType.INT,
        b=StatValueType.INT,
        total=StatValueType.INT,
        label=StatValueType.TEXT,
    )
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "total")
    a, b = _stat(sheet["a"]), _stat(sheet["b"])

    cases = {
        "one input": (url, _extremum("min", a)),
        "six inputs": (url, _extremum("max", a, b, a, b, a, b)),
        "an input that is both": (url, _extremum("min", {**a, "constant": 1}, b)),
        "an input that is neither": (url, _extremum("min", {}, b)),
        "reads itself": (url, _extremum("min", _stat(sheet["total"]), b)),
        "a text target": (sheet.formula_url(entity, "label"), _extremum("min", a, b)),
        "int target, fractional constant": (url, _extremum("max", a, _const(0.5))),
    }
    statuses = {label: (await client.put(u, json=b_)).status_code for label, (u, b_) in cases.items()}

    assert statuses == dict.fromkeys(cases, 422)
    await delete_tenant(tenant_id)


async def test_min_and_max_cycles_are_rejected(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.INT, b=StatValueType.INT)
    entity = await _entity(tenant_id, "Hero")
    await _put(client, sheet.formula_url(entity, "a"), _extremum("min", _stat(sheet["b"]), _const(1)))

    looped = await client.put(
        sheet.formula_url(entity, "b"), json=_extremum("max", _stat(sheet["a"]), _const(1))
    )

    assert looped.status_code == 422
    assert "b -> a -> b" in looped.json()["detail"]
    await delete_tenant(tenant_id)


async def test_changing_to_and_from_a_min_replaces_its_rows(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.INT, total=StatValueType.INT)
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "total")
    first = await client.put(url, json=_extremum("min", _stat(sheet["a"]), _const(4)))
    flipped = await client.put(
        url,
        json=_extremum("max", _const(1), _const(2), _const(3)),
        headers={"If-Match": first.headers["ETag"]},
    )
    linear = await client.put(
        url,
        json={"kind": "linear", "source_stat_definition_id": str(sheet["a"]), "multiplier": 2},
        headers={"If-Match": flipped.headers["ETag"]},
    )

    assert (first.status_code, flipped.status_code, linear.status_code) == (200, 200, 200)
    assert flipped.json()["formula"]["kind"] == "max"
    async with admin_session_factory() as session:
        for model in (ComputedStatExtremum, ComputedStatExtremumInput):
            left = await session.scalar(select(model.entity_id).where(model.tenant_id == tenant_id))
            assert left is None, model
    await delete_tenant(tenant_id)


# --- preview, explanation, dependents -------------------------------------------------------


async def test_preview_explanation_and_dependents_know_min_and_max(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        dex_modifier=StatValueType.INT,
        dex_cap=StatValueType.INT,
        dex_bonus=StatValueType.INT,
    )
    hero = await _entity(
        tenant_id, "Hero", stats={sheet["dex_modifier"]: 4, sheet["dex_cap"]: 2}
    )
    url = sheet.formula_url(hero, "dex_bonus")
    formula = _extremum("min", _stat(sheet["dex_modifier"]), _stat(sheet["dex_cap"]), _const(9))

    preview = await client.post(f"{url}/preview", json={"formula": formula})
    await _put(client, url, formula)
    explained = await client.get(
        f"/tenants/{tenant_id}/entities/{hero}/stats/{sheet['dex_bonus']}/explanation"
    )
    dependents = await client.get(
        f"/tenants/{tenant_id}/stat-definitions/{sheet['dex_cap']}/dependents"
    )

    assert preview.status_code == 200, preview.text
    assert preview.json()["value"] == 2
    assert [(i["name"], i["value"]) for i in preview.json()["inputs"]] == [
        ("dex_modifier", 4),
        ("dex_cap", 2),
    ]
    body = explained.json()
    assert body["value"] == 2
    assert body["picked"] == {
        "position": 1,
        "stat_definition_id": str(sheet["dex_cap"]),
        "name": "dex_cap",
        "value": 2,
    }
    assert dependents.json() == [
        {"entity_id": str(hero), "stat_definition_id": str(sheet["dex_bonus"]), "kind": "min"}
    ]
    await delete_tenant(tenant_id)


async def test_an_explanation_of_a_constant_pick_names_no_stat(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.INT, capped=StatValueType.INT)
    hero = await _entity(tenant_id, "Hero", stats={sheet["a"]: 30})
    await _put(
        client, sheet.formula_url(hero, "capped"), _extremum("min", _stat(sheet["a"]), _const(20))
    )

    explained = await client.get(
        f"/tenants/{tenant_id}/entities/{hero}/stats/{sheet['capped']}/explanation"
    )

    assert explained.json()["picked"] == {
        "position": 1,
        "stat_definition_id": None,
        "name": None,
        "value": 20,
    }
    await delete_tenant(tenant_id)


# --- the guard on an enum's order ----------------------------------------------------------


async def test_an_enum_a_formula_reads_cannot_be_reordered_or_lose_a_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, score=StatValueType.INT)
    tier = await _add_enum(tenant_id, "tier", {"common": 1, "rare": 2})
    unread = await _add_enum(tenant_id, "colour", {"red": 1, "blue": 2})
    hero = await _entity(tenant_id, "Hero")
    await _put(
        client,
        sheet.formula_url(hero, "score"),
        {"kind": "linear", "source_stat_definition_id": str(tier), "multiplier": 1},
    )
    base = f"/tenants/{tenant_id}/stat-definitions"
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(StatDefinitionEnumValue.id, StatDefinitionEnumValue.value).where(
                    StatDefinitionEnumValue.tenant_id == tenant_id
                )
            )
        ).tuples()
        ids = {value: row_id for row_id, value in rows}

    moved = await client.patch(f"{base}/{tier}/enum-values/{ids['rare']}", json={"sort_order": 9})
    removed = await client.delete(f"{base}/{tier}/enum-values/{ids['rare']}")
    renamed = await client.patch(
        f"{base}/{tier}/enum-values/{ids['rare']}", json={"value": "scarce"}
    )
    same_order = await client.patch(
        f"{base}/{tier}/enum-values/{ids['common']}", json={"sort_order": 1}
    )
    other_moved = await client.patch(
        f"{base}/{unread}/enum-values/{ids['red']}", json={"sort_order": 9}
    )
    other_removed = await client.delete(f"{base}/{unread}/enum-values/{ids['blue']}")

    assert (moved.status_code, removed.status_code) == (409, 409)
    assert moved.json()["type"].endswith("stat-enum-order-read-by-formula")
    assert "score of Hero" in moved.json()["detail"]
    assert renamed.status_code == 200, renamed.text
    assert same_order.status_code == 200, same_order.text
    assert (other_moved.status_code, other_removed.status_code) == (200, 200)
    await delete_tenant(tenant_id)


# --- RLS ---------------------------------------------------------------------------------------


async def test_extremum_tables_are_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_ids = []
    for _ in range(2):
        tenant_id = await make_tenant(test_user_id)
        sheet = await _sheet(tenant_id, strength=StatValueType.INT, total=StatValueType.INT)
        entity = await _entity(tenant_id, "Hero")
        await _put(
            client,
            sheet.formula_url(entity, "total"),
            _extremum("min", _stat(sheet["strength"]), _const(2)),
        )
        tenant_ids.append(tenant_id)

    try:
        for tenant_id in tenant_ids:
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                for table in ("computed_stat_extremum", "computed_stat_extremum_input"):
                    tenants = (
                        (await conn.execute(text(f"SELECT tenant_id FROM {table}"))).scalars().all()
                    )
                    assert set(tenants) == {tenant_id}
    finally:
        for tenant_id in tenant_ids:
            await delete_tenant(tenant_id)
