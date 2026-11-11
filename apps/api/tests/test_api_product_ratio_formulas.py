"""ADR 0445: `product` and `ratio` formulas through the real API - evaluation against the entity
being read, the write-time checks, kind changes, preview, explanation, dependents, the guard on an
enum's order for the new kinds, and RLS on the new tables.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text
from test_api_computed_stats import _entity, _put, _sheet, _stats
from test_api_extremum_formulas import _add_enum, _hold

from lorenzo_api.db import engine
from lorenzo_api.models import (
    ComputedStatProduct,
    ComputedStatProductFactor,
    ComputedStatRatio,
    EntityStat,
    StatDefinitionEnumValue,
    StatValueType,
)


def _product(
    *factors: uuid.UUID, multiplier: float = 1, offset: float = 0, round_mode: str = "none"
) -> dict:
    return {
        "kind": "product",
        "factors": [str(f) for f in factors],
        "multiplier": multiplier,
        "offset": offset,
        "round_mode": round_mode,
    }


def _ratio(
    numerator: uuid.UUID,
    *,
    by: uuid.UUID | None = None,
    by_constant: float | None = None,
    multiplier: float = 1,
    offset: float = 0,
    round_mode: str = "none",
) -> dict:
    return {
        "kind": "ratio",
        "numerator_stat_definition_id": str(numerator),
        "denominator_stat_definition_id": None if by is None else str(by),
        "denominator_constant": by_constant,
        "multiplier": multiplier,
        "offset": offset,
        "round_mode": round_mode,
    }


async def _float_stat(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, stat: uuid.UUID, value: float
) -> None:
    async with admin_session_factory() as session:
        session.add(
            EntityStat(
                entity_id=entity_id,
                stat_definition_id=stat,
                tenant_id=tenant_id,
                value_float=value,
            )
        )
        await session.commit()


# --- product ---------------------------------------------------------------------------------


async def test_a_product_multiplies_stats_with_a_constant_and_an_offset(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Hit points from level times the average of the die plus the modifier: each instance reads
    its own level, and a stat with no value gives the product none."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        level=StatValueType.INT,
        average=StatValueType.INT,
        hit_points=StatValueType.INT,
        doubled=StatValueType.INT,
    )
    base = await _entity(tenant_id, "Base")
    saved = await _put(
        client,
        sheet.formula_url(base, "hit_points"),
        _product(sheet["level"], sheet["average"], offset=10),
    )
    await _put(
        client,
        sheet.formula_url(base, "doubled"),
        _product(sheet["level"], sheet["level"], multiplier=2),
    )
    five = await _entity(
        tenant_id, "Five", prototype=base, stats={sheet["level"]: 5, sheet["average"]: 7}
    )
    none = await _entity(tenant_id, "None", prototype=base, stats={sheet["level"]: 2})

    assert saved["formula"]["kind"] == "product"
    assert saved["formula"]["factors"] == [str(sheet["level"]), str(sheet["average"])]
    fives = await _stats(client, tenant_id, five)
    assert (fives["hit_points"], fives["doubled"]) == (45, 50)
    nones = await _stats(client, tenant_id, none)
    assert nones["doubled"] == 8
    assert "hit_points" not in nones
    await delete_tenant(tenant_id)


async def test_a_bool_is_a_product_factor_of_one_or_zero(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A bonus that applies only when a flag is set: no trait entry carrying a formula."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        trained=StatValueType.BOOL,
        proficiency=StatValueType.INT,
        skill_bonus=StatValueType.INT,
    )
    base = await _entity(tenant_id, "Base")
    await _put(
        client,
        sheet.formula_url(base, "skill_bonus"),
        _product(sheet["trained"], sheet["proficiency"]),
    )
    results = {}
    for label, flag in (("trained", True), ("untrained", False)):
        thing = await _entity(tenant_id, label, prototype=base, stats={sheet["proficiency"]: 3})
        await _hold(tenant_id, thing, sheet["trained"], flag=flag)
        results[label] = (await _stats(client, tenant_id, thing))["skill_bonus"]

    assert results == {"trained": 3, "untrained": 0}
    await delete_tenant(tenant_id)


async def test_a_product_rounds_for_an_int_target_unless_it_is_always_whole(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        a=StatValueType.INT,
        speed=StatValueType.FLOAT,
        whole=StatValueType.INT,
        exact=StatValueType.FLOAT,
    )
    hero = await _entity(tenant_id, "Hero", stats={sheet["a"]: 3})
    await _float_stat(tenant_id, hero, sheet["speed"], 2.5)
    url = sheet.formula_url(hero, "whole")

    float_factor = await client.put(url, json=_product(sheet["a"], sheet["speed"]))
    fractional = await client.put(url, json=_product(sheet["a"], sheet["a"], multiplier=0.5))
    whole = await client.put(url, json=_product(sheet["a"], sheet["a"], multiplier=2))
    rounded = await client.put(url, json=_product(sheet["a"], sheet["speed"], round_mode="round"))
    await _put(client, sheet.formula_url(hero, "exact"), _product(sheet["a"], sheet["speed"]))

    assert (float_factor.status_code, fractional.status_code) == (422, 422)
    assert (whole.status_code, rounded.status_code) == (200, 200)
    stats = await _stats(client, tenant_id, hero)
    # 3 x 2.5 = 7.5 rounds half away from zero to 8.
    assert (stats["whole"], stats["exact"]) == (8, 7.5)
    await delete_tenant(tenant_id)


async def test_product_shape_and_type_checks(client: AsyncClient, test_user_id: uuid.UUID) -> None:
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
    a, b = sheet["a"], sheet["b"]

    cases = {
        "one factor": (url, _product(a)),
        "six factors": (url, _product(a, b, a, b, a, b)),
        "a text factor": (url, _product(a, sheet["label"])),
        "reads itself": (url, _product(a, sheet["total"])),
        "a text target": (sheet.formula_url(entity, "label"), _product(a, b)),
    }
    statuses = {
        label: (await client.put(u, json=b_)).status_code for label, (u, b_) in cases.items()
    }

    assert statuses == dict.fromkeys(cases, 422)
    await delete_tenant(tenant_id)


# --- ratio -------------------------------------------------------------------------------------


async def test_a_ratio_divides_a_stat_by_a_stat_or_a_constant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        total=StatValueType.INT,
        count=StatValueType.INT,
        average=StatValueType.FLOAT,
        halved=StatValueType.FLOAT,
        per_hundred=StatValueType.INT,
    )
    base = await _entity(tenant_id, "Base")
    await _put(
        client, sheet.formula_url(base, "average"), _ratio(sheet["total"], by=sheet["count"])
    )
    await _put(
        client,
        sheet.formula_url(base, "halved"),
        _ratio(sheet["total"], by_constant=4, multiplier=2, offset=1),
    )
    await _put(
        client,
        sheet.formula_url(base, "per_hundred"),
        _ratio(sheet["total"], by=sheet["count"], multiplier=100, round_mode="floor"),
    )
    some = await _entity(
        tenant_id, "Some", prototype=base, stats={sheet["total"]: 10, sheet["count"]: 4}
    )
    zero = await _entity(
        tenant_id, "Zero", prototype=base, stats={sheet["total"]: 10, sheet["count"]: 0}
    )

    stats = await _stats(client, tenant_id, some)
    assert (stats["average"], stats["halved"], stats["per_hundred"]) == (2.5, 6, 250)
    zeros = await _stats(client, tenant_id, zero)
    # A zero denominator gives no value, as an unset input does; the constant one still holds.
    assert "average" not in zeros
    assert "per_hundred" not in zeros
    assert zeros["halved"] == 6
    await delete_tenant(tenant_id)


async def test_a_ratio_for_an_int_stat_always_needs_a_rounding_mode(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.INT, b=StatValueType.INT, c=StatValueType.INT)
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "c")

    unrounded = await client.put(url, json=_ratio(sheet["a"], by=sheet["b"]))
    rounded = await client.put(url, json=_ratio(sheet["a"], by=sheet["b"], round_mode="ceil"))

    assert unrounded.status_code == 422
    assert "rounding mode" in unrounded.json()["detail"]
    assert rounded.status_code == 200, rounded.text
    await delete_tenant(tenant_id)


async def test_ratio_shape_and_type_checks(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        a=StatValueType.INT,
        b=StatValueType.INT,
        out=StatValueType.FLOAT,
        label=StatValueType.TEXT,
    )
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "out")
    a, b = sheet["a"], sheet["b"]

    cases = {
        "both denominators": (url, _ratio(a, by=b, by_constant=2)),
        "no denominator": (url, _ratio(a)),
        "a constant zero": (url, _ratio(a, by_constant=0)),
        "a text numerator": (url, _ratio(sheet["label"], by=b)),
        "a text denominator": (url, _ratio(a, by=sheet["label"])),
        "reads itself": (url, _ratio(sheet["out"], by=b)),
        "a text target": (sheet.formula_url(entity, "label"), _ratio(a, by=b)),
    }
    statuses = {
        label: (await client.put(u, json=b_)).status_code for label, (u, b_) in cases.items()
    }

    assert statuses == dict.fromkeys(cases, 422)
    await delete_tenant(tenant_id)


async def test_product_and_ratio_cycles_are_rejected(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.FLOAT, b=StatValueType.FLOAT)
    entity = await _entity(tenant_id, "Hero")
    await _put(
        client, sheet.formula_url(entity, "a"), _product(sheet["b"], sheet["b"], multiplier=2)
    )

    looped = await client.put(
        sheet.formula_url(entity, "b"), json=_ratio(sheet["a"], by_constant=2)
    )

    assert looped.status_code == 422
    assert "b -> a -> b" in looped.json()["detail"]
    await delete_tenant(tenant_id)


# --- changing kind, preview, explanation, dependents -------------------------------------------


async def test_changing_to_and_from_product_and_ratio_replaces_their_rows(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, a=StatValueType.INT, b=StatValueType.INT, out=StatValueType.FLOAT
    )
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "out")
    product = await client.put(url, json=_product(sheet["a"], sheet["b"]))
    ratio = await client.put(
        url,
        json=_ratio(sheet["a"], by=sheet["b"]),
        headers={"If-Match": product.headers["ETag"]},
    )
    linear = await client.put(
        url,
        json={"kind": "linear", "source_stat_definition_id": str(sheet["a"]), "multiplier": 1},
        headers={"If-Match": ratio.headers["ETag"]},
    )

    assert (product.status_code, ratio.status_code, linear.status_code) == (200, 200, 200)
    async with admin_session_factory() as session:
        for model in (ComputedStatProduct, ComputedStatProductFactor, ComputedStatRatio):
            left = await session.scalar(select(model.entity_id).where(model.tenant_id == tenant_id))
            assert left is None, model
    await delete_tenant(tenant_id)


async def test_preview_explanation_and_dependents_know_product_and_ratio(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        a=StatValueType.INT,
        b=StatValueType.INT,
        scaled=StatValueType.INT,
        third=StatValueType.FLOAT,
        half=StatValueType.FLOAT,
    )
    hero = await _entity(tenant_id, "Hero", stats={sheet["a"]: 1, sheet["b"]: 3})
    scaled = sheet.formula_url(hero, "scaled")

    preview = await client.post(
        f"{scaled}/preview", json={"formula": _product(sheet["a"], sheet["b"], multiplier=7)}
    )
    await _put(client, sheet.formula_url(hero, "third"), _ratio(sheet["a"], by=sheet["b"]))
    await _put(client, sheet.formula_url(hero, "half"), _ratio(sheet["b"], by_constant=2))
    await _put(client, scaled, _product(sheet["a"], sheet["b"], multiplier=7))
    thirds = await client.get(
        f"/tenants/{tenant_id}/entities/{hero}/stats/{sheet['third']}/explanation"
    )
    halves = await client.get(
        f"/tenants/{tenant_id}/entities/{hero}/stats/{sheet['half']}/explanation"
    )
    dependents = await client.get(f"/tenants/{tenant_id}/stat-definitions/{sheet['b']}/dependents")

    assert preview.status_code == 200, preview.text
    assert preview.json()["value"] == 21
    assert [(i["name"], i["value"]) for i in preview.json()["inputs"]] == [("a", 1), ("b", 3)]
    # 1 / 3 does not fit in 28 digits, so the explanation says it was rounded; 3 / 2 does.
    assert thirds.json()["division_rounded"] is True
    assert halves.json()["division_rounded"] is False
    kinds = sorted((d["stat_definition_id"], d["kind"]) for d in dependents.json())
    assert kinds == sorted(
        [
            (str(sheet["scaled"]), "product"),
            (str(sheet["third"]), "ratio"),
            (str(sheet["half"]), "ratio"),
        ]
    )
    await delete_tenant(tenant_id)


# --- an enum read as a number, and RLS ----------------------------------------------------------


async def test_a_product_or_a_ratio_that_reads_an_enum_holds_its_order(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, level=StatValueType.INT, cost=StatValueType.INT, share=StatValueType.FLOAT
    )
    tier = await _add_enum(tenant_id, "tier", {"common": 1, "rare": 2})
    size = await _add_enum(tenant_id, "size", {"small": 1, "large": 2})
    hero = await _entity(tenant_id, "Hero", stats={sheet["level"]: 2})
    await _hold(tenant_id, hero, tier, text_value="rare")
    await _hold(tenant_id, hero, size, text_value="large")
    await _put(client, sheet.formula_url(hero, "cost"), _product(sheet["level"], tier))
    await _put(client, sheet.formula_url(hero, "share"), _ratio(sheet["level"], by=size))
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

    tier_moved = await client.patch(
        f"{base}/{tier}/enum-values/{ids['rare']}", json={"sort_order": 9}
    )
    size_removed = await client.delete(f"{base}/{size}/enum-values/{ids['small']}")

    stats = await _stats(client, tenant_id, hero)
    assert (stats["cost"], stats["share"]) == (4, 1.0)
    assert (tier_moved.status_code, size_removed.status_code) == (409, 409)
    await delete_tenant(tenant_id)


async def test_product_and_ratio_tables_are_tenant_isolated(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_ids = []
    for _ in range(2):
        tenant_id = await make_tenant(test_user_id)
        sheet = await _sheet(
            tenant_id,
            a=StatValueType.INT,
            b=StatValueType.INT,
            c=StatValueType.FLOAT,
            d=StatValueType.INT,
        )
        entity = await _entity(tenant_id, "Hero")
        await _put(client, sheet.formula_url(entity, "d"), _product(sheet["a"], sheet["b"]))
        await _put(client, sheet.formula_url(entity, "c"), _ratio(sheet["a"], by=sheet["b"]))
        tenant_ids.append(tenant_id)

    try:
        for tenant_id in tenant_ids:
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                for table in (
                    "computed_stat_product",
                    "computed_stat_product_factor",
                    "computed_stat_ratio",
                ):
                    tenants = (
                        (await conn.execute(text(f"SELECT tenant_id FROM {table}"))).scalars().all()
                    )
                    assert set(tenants) == {tenant_id}
    finally:
        for tenant_id in tenant_ids:
            await delete_tenant(tenant_id)
