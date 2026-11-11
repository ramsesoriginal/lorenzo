"""ADR 0446: `select` formulas through the real API - a value from a table by threshold or by
match, results that are constants or stats, every target type, the write-time checks, kind
changes, preview, explanation, dependents, the enum guard and rename, and RLS on the new tables.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text, update
from test_api_computed_stats import _entity, _put, _sheet, _stats
from test_api_extremum_formulas import _add_enum, _hold

from lorenzo_api.db import engine
from lorenzo_api.models import (
    ComputedStatSelect,
    ComputedStatSelectStep,
    EntityStat,
    StatDefinitionEnumValue,
    StatValueType,
)


def _from(value: float, **result: object) -> dict:
    return {"from": value, "result": result}


def _is(value: str, **result: object) -> dict:
    return {"value": value, "result": result}


def _select(source: uuid.UUID, mode: str, *steps: dict, otherwise: dict | None = None) -> dict:
    return {
        "kind": "select",
        "source_stat_definition_id": str(source),
        "mode": mode,
        "steps": list(steps),
        "otherwise": otherwise,
    }


async def _text_stat(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, stat: uuid.UUID, value: str
) -> None:
    await _hold(tenant_id, entity_id, stat, text_value=value)


# --- by threshold ------------------------------------------------------------------------------


async def test_a_threshold_select_is_a_table_by_level(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The proficiency bonus by level, one formula where it was a staircase of linear and floor."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, level=StatValueType.INT, proficiency=StatValueType.INT)
    base = await _entity(tenant_id, "Base")
    saved = await _put(
        client,
        sheet.formula_url(base, "proficiency"),
        _select(
            sheet["level"],
            "threshold",
            _from(1, number=2),
            _from(5, number=3),
            _from(9, number=4),
            _from(13, number=5),
            otherwise={"number": 0},
        ),
    )
    levels = {}
    for level in (0, 1, 4, 5, 7, 13, 20):
        thing = await _entity(tenant_id, f"L{level}", prototype=base, stats={sheet["level"]: level})
        levels[level] = (await _stats(client, tenant_id, thing))["proficiency"]

    assert saved["formula"]["kind"] == "select"
    assert [float(s["from"]) for s in saved["formula"]["steps"]] == [1, 5, 9, 13]
    assert levels == {0: 0, 1: 2, 4: 2, 5: 3, 7: 3, 13: 5, 20: 5}
    await delete_tenant(tenant_id)


async def test_a_select_without_otherwise_has_no_value_below_the_first_step(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, level=StatValueType.INT, bonus=StatValueType.INT)
    base = await _entity(tenant_id, "Base")
    await _put(
        client,
        sheet.formula_url(base, "bonus"),
        _select(sheet["level"], "threshold", _from(3, number=1)),
    )
    low = await _entity(tenant_id, "Low", prototype=base, stats={sheet["level"]: 2})
    unset = await _entity(tenant_id, "Unset", prototype=base)
    high = await _entity(tenant_id, "High", prototype=base, stats={sheet["level"]: 3})

    assert "bonus" not in await _stats(client, tenant_id, low)
    # A source with no value gives none either, otherwise or not.
    assert "bonus" not in await _stats(client, tenant_id, unset)
    assert (await _stats(client, tenant_id, high))["bonus"] == 1
    await delete_tenant(tenant_id)


async def test_a_threshold_reads_a_bool_and_an_enum_as_numbers(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, flag=StatValueType.BOOL, from_flag=StatValueType.INT, from_tier=StatValueType.INT
    )
    tier = await _add_enum(tenant_id, "tier", {"common": 10, "rare": 5, "legendary": 30})
    sheet.ids["tier"] = tier
    base = await _entity(tenant_id, "Base")
    await _put(
        client,
        sheet.formula_url(base, "from_flag"),
        _select(sheet["flag"], "threshold", _from(1, number=7), otherwise={"number": 0}),
    )
    await _put(
        client,
        sheet.formula_url(base, "from_tier"),
        _select(
            tier, "threshold", _from(10, number=1), _from(30, number=2), otherwise={"number": 0}
        ),
    )
    things = {}
    for label, flag, level in (
        ("a", True, "legendary"),
        ("b", False, "rare"),
        ("c", False, "common"),
    ):
        thing = await _entity(tenant_id, label, prototype=base)
        await _hold(tenant_id, thing, sheet["flag"], flag=flag)
        await _hold(tenant_id, thing, tier, text_value=level)
        things[label] = await _stats(client, tenant_id, thing)

    # `rare` is numbered 5, below the first step, so it falls to otherwise; `common` is 10.
    assert [(s["from_flag"], s["from_tier"]) for s in things.values()] == [(7, 2), (0, 0), (0, 1)]
    await delete_tenant(tenant_id)


# --- by match ----------------------------------------------------------------------------------


async def test_a_match_select_picks_a_constant_or_a_stat_by_an_enum(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The dexterity bonus by armour category: a stat for light, a constant for medium and heavy
    (the cap in one formula that was a min and a table)."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, dex_modifier=StatValueType.INT, dex_bonus=StatValueType.INT)
    armour = await _add_enum(tenant_id, "armour", {"light": 1, "medium": 2, "heavy": 3})
    base = await _entity(tenant_id, "Base")
    await _put(
        client,
        sheet.formula_url(base, "dex_bonus"),
        _select(
            armour,
            "match",
            _is("light", stat_definition_id=str(sheet["dex_modifier"])),
            _is("medium", number=2),
            _is("heavy", number=0),
        ),
    )
    results = {}
    for kind in ("light", "medium", "heavy"):
        thing = await _entity(tenant_id, kind, prototype=base, stats={sheet["dex_modifier"]: 4})
        await _hold(tenant_id, thing, armour, text_value=kind)
        results[kind] = (await _stats(client, tenant_id, thing))["dex_bonus"]

    assert results == {"light": 4, "medium": 2, "heavy": 0}
    await delete_tenant(tenant_id)


async def test_a_match_over_a_text_source_gives_a_float_a_text_or_a_flag(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        category=StatValueType.TEXT,
        cost=StatValueType.FLOAT,
        label=StatValueType.TEXT,
        magical=StatValueType.BOOL,
    )
    base = await _entity(tenant_id, "Base")
    await _put(
        client,
        sheet.formula_url(base, "cost"),
        _select(sheet["category"], "match", _is("potion", number=2.5), _is("scroll", number=10)),
    )
    await _put(
        client,
        sheet.formula_url(base, "label"),
        _select(
            sheet["category"],
            "match",
            _is("potion", text="Drink"),
            otherwise={"text": "Other"},
        ),
    )
    await _put(
        client,
        sheet.formula_url(base, "magical"),
        _select(sheet["category"], "match", _is("wand", flag=True), otherwise={"flag": False}),
    )
    results = {}
    for category in ("potion", "scroll", "wand"):
        thing = await _entity(tenant_id, category, prototype=base)
        await _text_stat(tenant_id, thing, sheet["category"], category)
        results[category] = await _stats(client, tenant_id, thing)

    assert results["potion"]["cost"] == 2.5 and results["scroll"]["cost"] == 10
    assert "cost" not in results["wand"]
    assert [results[c]["label"] for c in ("potion", "scroll", "wand")] == [
        "Drink",
        "Other",
        "Other",
    ]
    assert [results[c]["magical"] for c in ("potion", "scroll", "wand")] == [False, False, True]
    await delete_tenant(tenant_id)


async def test_a_select_can_return_an_enum_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, level=StatValueType.INT)
    tier = await _add_enum(tenant_id, "tier", {"novice": 1, "master": 2})
    base = await _entity(tenant_id, "Base")
    await _put(
        client,
        f"/tenants/{tenant_id}/entities/{base}/computed-stats/{tier}",
        _select(
            sheet["level"],
            "threshold",
            _from(1, text="novice"),
            _from(10, text="master"),
        ),
    )
    thing = await _entity(tenant_id, "Hero", prototype=base, stats={sheet["level"]: 12})

    assert (await _stats(client, tenant_id, thing))["tier"] == "master"
    await delete_tenant(tenant_id)


# --- write-time checks -----------------------------------------------------------------------


async def test_select_shape_and_type_checks(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        level=StatValueType.INT,
        speed=StatValueType.FLOAT,
        category=StatValueType.TEXT,
        total=StatValueType.INT,
        reach=StatValueType.FLOAT,
        label=StatValueType.TEXT,
        flag=StatValueType.BOOL,
    )
    kind = await _add_enum(tenant_id, "kind", {"a": 1, "b": 2})
    sized = await _add_enum(tenant_id, "sized", {"small": 1, "large": 2})
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "total")
    level, category = sheet["level"], sheet["category"]

    cases = {
        "no steps": (url, _select(level, "threshold")),
        "steps that do not rise": (
            url,
            _select(level, "threshold", _from(5, number=1), _from(5, number=2)),
        ),
        "steps that fall": (
            url,
            _select(level, "threshold", _from(5, number=1), _from(2, number=2)),
        ),
        "a threshold step with a value": (
            url,
            _select(level, "threshold", {"from": 1, "value": "x", "result": {"number": 1}}),
        ),
        "a match step with a from": (
            url,
            _select(category, "match", {"from": 1, "value": "x", "result": {"number": 1}}),
        ),
        "a text source for a threshold": (
            url,
            _select(category, "threshold", _from(1, number=1)),
        ),
        "a number source for a match": (url, _select(level, "match", _is("x", number=1))),
        "the same value twice": (
            url,
            _select(category, "match", _is("x", number=1), _is("x", number=2)),
        ),
        "a value the enum does not allow": (
            url,
            _select(kind, "match", _is("a", number=1), _is("zzz", number=2)),
        ),
        "a result that is two things": (
            url,
            _select(level, "threshold", _from(1, number=1, text="x")),
        ),
        "a result that is nothing": (url, _select(level, "threshold", _from(1))),
        "a text result for an int stat": (url, _select(level, "threshold", _from(1, text="x"))),
        "a fractional result for an int stat": (
            url,
            _select(level, "threshold", _from(1, number=0.5)),
        ),
        "a float stat result for an int stat": (
            url,
            _select(level, "threshold", _from(1, stat_definition_id=str(sheet["speed"]))),
        ),
        "a number result for a text stat": (
            sheet.formula_url(entity, "label"),
            _select(level, "threshold", _from(1, number=1)),
        ),
        "a stat result for a text stat": (
            sheet.formula_url(entity, "label"),
            _select(level, "threshold", _from(1, stat_definition_id=str(level))),
        ),
        "a number result for a bool stat": (
            sheet.formula_url(entity, "flag"),
            _select(level, "threshold", _from(1, number=1)),
        ),
        "a text that is not an allowed enum value": (
            f"/tenants/{tenant_id}/entities/{entity}/computed-stats/{sized}",
            _select(level, "threshold", _from(1, text="medium")),
        ),
        "a result stat that is text": (
            url,
            _select(level, "threshold", _from(1, stat_definition_id=str(category))),
        ),
        "reads itself": (
            url,
            _select(level, "threshold", _from(1, stat_definition_id=str(sheet["total"]))),
        ),
        "sixty-five steps": (
            url,
            _select(level, "threshold", *[_from(i, number=i) for i in range(65)]),
        ),
    }
    statuses = {
        label: (await client.put(u, json=body)).status_code for label, (u, body) in cases.items()
    }

    assert statuses == dict.fromkeys(cases, 422)
    sixty_four = await client.put(
        url, json=_select(level, "threshold", *[_from(i, number=i) for i in range(64)])
    )
    assert sixty_four.status_code == 200, sixty_four.text
    await delete_tenant(tenant_id)


async def test_select_cycles_are_rejected(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.INT, b=StatValueType.INT)
    entity = await _entity(tenant_id, "Hero")
    await _put(
        client,
        sheet.formula_url(entity, "a"),
        _select(sheet["b"], "threshold", _from(1, number=1)),
    )

    looped = await client.put(
        sheet.formula_url(entity, "b"),
        json=_select(sheet["a"], "threshold", _from(1, number=1)),
    )
    via_a_result = await client.put(
        sheet.formula_url(entity, "b"),
        json=_select(sheet["b"], "threshold", _from(1, stat_definition_id=str(sheet["a"]))),
    )

    assert looped.status_code == 422
    assert "b -> a -> b" in looped.json()["detail"]
    assert via_a_result.status_code == 422
    await delete_tenant(tenant_id)


async def test_changing_to_and_from_a_select_replaces_its_rows(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.INT, out=StatValueType.INT)
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "out")
    first = await client.put(
        url, json=_select(sheet["a"], "threshold", _from(1, number=1), _from(2, number=2))
    )
    fewer = await client.put(
        url,
        json=_select(sheet["a"], "threshold", _from(1, number=9), otherwise={"number": 3}),
        headers={"If-Match": first.headers["ETag"]},
    )
    linear = await client.put(
        url,
        json={"kind": "linear", "source_stat_definition_id": str(sheet["a"]), "multiplier": 1},
        headers={"If-Match": fewer.headers["ETag"]},
    )

    assert (first.status_code, fewer.status_code, linear.status_code) == (200, 200, 200)
    async with admin_session_factory() as session:
        for model in (ComputedStatSelect, ComputedStatSelectStep):
            left = await session.scalar(select(model.entity_id).where(model.tenant_id == tenant_id))
            assert left is None, model
    await delete_tenant(tenant_id)


# --- preview, explanation, dependents -----------------------------------------------------------


async def test_preview_explanation_and_dependents_know_select(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, level=StatValueType.INT, bonus=StatValueType.INT, spare=StatValueType.INT
    )
    hero = await _entity(tenant_id, "Hero", stats={sheet["level"]: 6, sheet["spare"]: 8})
    url = sheet.formula_url(hero, "bonus")
    formula = _select(
        sheet["level"],
        "threshold",
        _from(1, number=2),
        _from(5, number=3),
        _from(9, stat_definition_id=str(sheet["spare"])),
        otherwise={"number": 0},
    )

    preview = await client.post(f"{url}/preview", json={"formula": formula})
    await _put(client, url, formula)
    chose = await client.get(
        f"/tenants/{tenant_id}/entities/{hero}/stats/{sheet['bonus']}/explanation"
    )
    lower = await client.get(f"/tenants/{tenant_id}/stat-definitions/{sheet['spare']}/dependents")
    source = await client.get(f"/tenants/{tenant_id}/stat-definitions/{sheet['level']}/dependents")
    async with admin_session_factory() as session:
        await session.execute(
            update(EntityStat)
            .where(EntityStat.entity_id == hero, EntityStat.stat_definition_id == sheet["level"])
            .values(value_int=0)
        )
        await session.commit()
    fell = await client.get(
        f"/tenants/{tenant_id}/entities/{hero}/stats/{sheet['bonus']}/explanation"
    )

    assert preview.status_code == 200, preview.text
    assert preview.json()["value"] == 3
    assert [(i["name"], i["value"]) for i in preview.json()["inputs"]] == [
        ("level", 6),
        ("spare", 8),
    ]
    assert chose.json()["chosen"] == {"position": 1, "otherwise": False, "key": 5}
    expected = [
        {"entity_id": str(hero), "stat_definition_id": str(sheet["bonus"]), "kind": "select"}
    ]
    assert lower.json() == expected and source.json() == expected
    assert fell.json()["chosen"] == {"position": None, "otherwise": True, "key": None}
    await delete_tenant(tenant_id)


# --- enum values: rename, removal, order ----------------------------------------------------------


async def test_renaming_an_enum_value_rewrites_the_selects_that_match_or_return_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, level=StatValueType.INT, label=StatValueType.TEXT)
    armour = await _add_enum(tenant_id, "armour", {"light": 1, "heavy": 2})
    rank = await _add_enum(tenant_id, "rank", {"novice": 1, "master": 2})
    hero = await _entity(tenant_id, "Hero", stats={sheet["level"]: 12})
    await _hold(tenant_id, hero, armour, text_value="light")
    await _put(
        client,
        sheet.formula_url(hero, "label"),
        _select(armour, "match", _is("light", text="agile"), _is("heavy", text="slow")),
    )
    rank_url = f"/tenants/{tenant_id}/entities/{hero}/computed-stats/{rank}"
    await _put(
        client,
        rank_url,
        _select(sheet["level"], "threshold", _from(1, text="novice"), _from(10, text="master")),
    )
    async with admin_session_factory() as session:
        ids = {
            value: row_id
            for row_id, value in (
                await session.execute(
                    select(StatDefinitionEnumValue.id, StatDefinitionEnumValue.value).where(
                        StatDefinitionEnumValue.tenant_id == tenant_id
                    )
                )
            ).tuples()
        }
    base = f"/tenants/{tenant_id}/stat-definitions"

    removed_key = await client.delete(f"{base}/{armour}/enum-values/{ids['heavy']}")
    removed_result = await client.delete(f"{base}/{rank}/enum-values/{ids['master']}")
    renamed_key = await client.patch(
        f"{base}/{armour}/enum-values/{ids['light']}", json={"value": "nimble"}
    )
    renamed_result = await client.patch(
        f"{base}/{rank}/enum-values/{ids['master']}", json={"value": "expert"}
    )
    stats = await _stats(client, tenant_id, hero)

    assert (removed_key.status_code, removed_result.status_code) == (409, 409)
    assert (renamed_key.status_code, renamed_result.status_code) == (200, 200)
    assert (stats["label"], stats["rank"]) == ("agile", "expert")
    await delete_tenant(tenant_id)


async def test_a_threshold_select_over_an_enum_holds_its_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, bonus=StatValueType.INT, spare=StatValueType.INT)
    tier = await _add_enum(tenant_id, "tier", {"common": 1, "rare": 2})
    hero = await _entity(tenant_id, "Hero")
    await _put(
        client, sheet.formula_url(hero, "bonus"), _select(tier, "threshold", _from(1, number=1))
    )
    async with admin_session_factory() as session:
        rare = await session.scalar(
            select(StatDefinitionEnumValue.id).where(
                StatDefinitionEnumValue.tenant_id == tenant_id,
                StatDefinitionEnumValue.value == "rare",
            )
        )

    moved = await client.patch(
        f"/tenants/{tenant_id}/stat-definitions/{tier}/enum-values/{rare}",
        json={"sort_order": 9},
    )

    assert moved.status_code == 409
    assert moved.json()["type"].endswith("stat-enum-order-read-by-formula")
    await delete_tenant(tenant_id)


# --- RLS ---------------------------------------------------------------------------------------


async def test_select_tables_are_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_ids = []
    for _ in range(2):
        tenant_id = await make_tenant(test_user_id)
        sheet = await _sheet(tenant_id, level=StatValueType.INT, bonus=StatValueType.INT)
        entity = await _entity(tenant_id, "Hero")
        await _put(
            client,
            sheet.formula_url(entity, "bonus"),
            _select(sheet["level"], "threshold", _from(1, number=1)),
        )
        tenant_ids.append(tenant_id)

    try:
        for tenant_id in tenant_ids:
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                for table in ("computed_stat_select", "computed_stat_select_step"):
                    tenants = (
                        (await conn.execute(text(f"SELECT tenant_id FROM {table}"))).scalars().all()
                    )
                    assert set(tenants) == {tenant_id}
    finally:
        for tenant_id in tenant_ids:
            await delete_tenant(tenant_id)
