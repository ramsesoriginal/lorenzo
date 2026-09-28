"""ADR 0126: sum formulas through the real API - evaluation against the
entity being read, the write-time checks (including the loosened rounding
rule, for linear too), kind changes, preview, dependents, and RLS on the
new tables.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text
from test_api_computed_stats import _entity, _put, _sheet, _stats

from lorenzo_api.db import engine
from lorenzo_api.models import AuditLog, ComputedStatSum, ComputedStatSumTerm, StatValueType


def _sum(*terms: tuple[uuid.UUID, float], offset: float = 0, round_mode: str = "none") -> dict:
    return {
        "kind": "sum",
        "terms": [
            {"stat_definition_id": str(stat), "coefficient": coefficient}
            for stat, coefficient in terms
        ],
        "offset": offset,
        "round_mode": round_mode,
    }


async def test_a_sum_adds_up_each_instances_own_stats(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Armour class on the prototype, 10 + dex modifier + worn bonus, read
    against each instance; hit points subtract with a negative coefficient.
    Every input is an int and every number whole, so no rounding mode."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        dex_modifier=StatValueType.INT,
        worn_ac_bonus=StatValueType.INT,
        armour_class=StatValueType.INT,
        max_hp=StatValueType.INT,
        damage=StatValueType.INT,
        current_hp=StatValueType.INT,
    )
    adventurer = await _entity(tenant_id, "Adventurer")
    saved = await _put(
        client,
        sheet.formula_url(adventurer, "armour_class"),
        _sum((sheet["dex_modifier"], 1), (sheet["worn_ac_bonus"], 1), offset=10),
    )
    await _put(
        client,
        sheet.formula_url(adventurer, "current_hp"),
        _sum((sheet["max_hp"], 1), (sheet["damage"], -1)),
    )
    brisk = await _entity(
        tenant_id,
        "Brisk",
        prototype=adventurer,
        stats={
            sheet["dex_modifier"]: 2,
            sheet["worn_ac_bonus"]: 3,
            sheet["max_hp"]: 30,
            sheet["damage"]: 7,
        },
    )
    pia = await _entity(
        tenant_id,
        "Pia",
        prototype=adventurer,
        stats={sheet["dex_modifier"]: -1, sheet["worn_ac_bonus"]: 0},
    )

    assert saved["formula"]["kind"] == "sum"
    assert [t["stat_definition_id"] for t in saved["formula"]["terms"]] == [
        str(sheet["dex_modifier"]),
        str(sheet["worn_ac_bonus"]),
    ]
    brisks = await _stats(client, tenant_id, brisk)
    assert (brisks["armour_class"], brisks["current_hp"]) == (15, 23)
    pias = await _stats(client, tenant_id, pia)
    assert pias["armour_class"] == 9
    # Pia has no hit points recorded: a sum with an unset term has no value.
    assert "current_hp" not in pias

    listed = await client.get(f"/tenants/{tenant_id}/entities/{adventurer}/computed-stats")
    assert {f["formula"]["kind"] for f in listed.json()} == {"sum"}
    await delete_tenant(tenant_id)


async def test_a_sum_reads_other_formulas_and_rounds(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """attack = strength modifier (a linear formula) + half the level,
    rounded down; a float target keeps the fraction."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        strength=StatValueType.INT,
        strength_modifier=StatValueType.INT,
        level=StatValueType.INT,
        attack=StatValueType.INT,
        reach=StatValueType.FLOAT,
    )
    hero = await _entity(tenant_id, "Hero", stats={sheet["strength"]: 15, sheet["level"]: 5})
    await _put(
        client,
        sheet.formula_url(hero, "strength_modifier"),
        {
            "kind": "linear",
            "source_stat_definition_id": str(sheet["strength"]),
            "multiplier": 0.5,
            "offset": -5,
            "round_mode": "floor",
        },
    )
    await _put(
        client,
        sheet.formula_url(hero, "attack"),
        _sum((sheet["strength_modifier"], 1), (sheet["level"], 0.5), round_mode="floor"),
    )
    await _put(client, sheet.formula_url(hero, "reach"), _sum((sheet["level"], 0.5), offset=1))

    stats = await _stats(client, tenant_id, hero)
    # floor(15 * 0.5 - 5) = 2; floor(2 + 2.5) = 4; 5 * 0.5 + 1 = 3.5.
    assert (stats["strength_modifier"], stats["attack"], stats["reach"]) == (2, 4, 3.5)
    await delete_tenant(tenant_id)


async def test_sum_type_checks(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        strength=StatValueType.INT,
        dexterity=StatValueType.INT,
        speed=StatValueType.FLOAT,
        total=StatValueType.INT,
        name=StatValueType.TEXT,
    )
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "total")
    strength, dexterity = sheet["strength"], sheet["dexterity"]

    cases = {
        "no terms": (url, _sum()),
        "too many terms": (url, _sum(*[(strength, 1)] * 21)),
        "the same stat twice": (url, _sum((strength, 1), (strength, 2))),
        "a text term": (url, _sum((strength, 1), (sheet["name"], 1))),
        "reads itself": (url, _sum((strength, 1), (sheet["total"], 1))),
        "a text target": (sheet.formula_url(entity, "name"), _sum((strength, 1))),
        "int target, fractional coefficient": (url, _sum((strength, 0.5))),
        "int target, fractional offset": (url, _sum((strength, 1), offset=0.5)),
        "int target, float term": (url, _sum((strength, 1), (sheet["speed"], 1))),
    }
    statuses = {label: (await client.put(u, json=b)).status_code for label, (u, b) in cases.items()}
    twice = await client.put(url, json=_sum((strength, 1), (strength, 2)))
    unrounded = await client.put(url, json=_sum((strength, 0.5)))
    # The same fractional coefficient is fine with a rounding mode.
    rounded = await client.put(url, json=_sum((strength, 0.5), (dexterity, 1), round_mode="round"))

    assert statuses == dict.fromkeys(cases, 422)
    assert "more than once" in twice.json()["detail"]
    assert "rounding mode" in unrounded.json()["detail"]
    assert rounded.status_code == 200, rounded.text
    await delete_tenant(tenant_id)


async def test_a_linear_int_formula_needs_no_rounding_when_always_whole(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0126 loosens ADR 0104's rule for linear too: strength × 15 can't
    be a fraction."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, strength=StatValueType.INT, carry_capacity=StatValueType.INT)
    hero = await _entity(tenant_id, "Hero", stats={sheet["strength"]: 12})

    await _put(
        client,
        sheet.formula_url(hero, "carry_capacity"),
        {"kind": "linear", "source_stat_definition_id": str(sheet["strength"]), "multiplier": 15},
    )

    assert (await _stats(client, tenant_id, hero))["carry_capacity"] == 180
    await delete_tenant(tenant_id)


async def test_sum_cycles_are_rejected(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(tenant_id, a=StatValueType.INT, b=StatValueType.INT, c=StatValueType.INT)
    entity = await _entity(tenant_id, "Hero")
    await _put(client, sheet.formula_url(entity, "a"), _sum((sheet["b"], 1), (sheet["c"], 1)))

    looped = await client.put(sheet.formula_url(entity, "b"), json=_sum((sheet["a"], 1)))

    assert looped.status_code == 422
    assert "b -> a -> b" in looped.json()["detail"]
    await delete_tenant(tenant_id)


async def test_changing_to_and_from_a_sum_replaces_its_rows(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, strength=StatValueType.INT, dexterity=StatValueType.INT, total=StatValueType.INT
    )
    entity = await _entity(tenant_id, "Hero")
    url = sheet.formula_url(entity, "total")
    linear = await client.put(
        url,
        json={
            "kind": "linear",
            "source_stat_definition_id": str(sheet["strength"]),
            "multiplier": 2,
        },
    )

    summed = await client.put(
        url,
        json=_sum((sheet["dexterity"], 1), (sheet["strength"], 1)),
        headers={"If-Match": linear.headers["ETag"]},
    )
    fewer = await client.put(
        url, json=_sum((sheet["strength"], 3)), headers={"If-Match": summed.headers["ETag"]}
    )
    async with admin_session_factory() as session:
        terms = (
            await session.execute(
                select(ComputedStatSumTerm.source_stat_definition_id).where(
                    ComputedStatSumTerm.tenant_id == tenant_id
                )
            )
        ).scalars()
        assert list(terms) == [sheet["strength"]]
        logged = (
            await session.scalars(
                select(AuditLog.detail).where(
                    AuditLog.tenant_id == tenant_id, AuditLog.action == "computed_stat.set"
                )
            )
        ).all()
    deleted = await client.delete(url, headers={"If-Match": fewer.headers["ETag"]})

    assert summed.status_code == 200, summed.text
    assert fewer.status_code == 200, fewer.text
    assert any(detail.endswith("kind=sum") for detail in logged)
    assert deleted.status_code == 204
    async with admin_session_factory() as session:
        for model in (ComputedStatSum, ComputedStatSumTerm):
            left = await session.scalar(select(model.entity_id).where(model.tenant_id == tenant_id))
            assert left is None, model
    await delete_tenant(tenant_id)


async def test_preview_and_dependents_know_sums(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id, strength=StatValueType.INT, dexterity=StatValueType.INT, total=StatValueType.INT
    )
    hero = await _entity(tenant_id, "Hero", stats={sheet["strength"]: 12, sheet["dexterity"]: 14})
    url = sheet.formula_url(hero, "total")

    preview = await client.post(
        f"{url}/preview",
        json={"formula": _sum((sheet["strength"], 1), (sheet["dexterity"], 2), offset=1)},
    )
    await _put(client, url, _sum((sheet["strength"], 1), (sheet["dexterity"], 2)))
    dependents = await client.get(
        f"/tenants/{tenant_id}/stat-definitions/{sheet['dexterity']}/dependents"
    )

    assert preview.status_code == 200, preview.text
    assert preview.json()["value"] == 41
    assert [(i["name"], i["value"]) for i in preview.json()["inputs"]] == [
        ("strength", 12),
        ("dexterity", 14),
    ]
    assert dependents.json() == [
        {"entity_id": str(hero), "stat_definition_id": str(sheet["total"]), "kind": "sum"}
    ]
    await delete_tenant(tenant_id)


async def test_sum_tables_are_tenant_isolated(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_ids = []
    for _ in range(2):
        tenant_id = await make_tenant(test_user_id)
        sheet = await _sheet(tenant_id, strength=StatValueType.INT, total=StatValueType.INT)
        entity = await _entity(tenant_id, "Hero")
        await _put(client, sheet.formula_url(entity, "total"), _sum((sheet["strength"], 2)))
        tenant_ids.append(tenant_id)

    try:
        for tenant_id in tenant_ids:
            async with engine.begin() as conn:
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)}
                )
                for table in ("computed_stat_sum", "computed_stat_sum_term"):
                    tenants = (
                        (await conn.execute(text(f"SELECT tenant_id FROM {table}"))).scalars().all()
                    )
                    assert tenants == [tenant_id]
    finally:
        for tenant_id in tenant_ids:
            await delete_tenant(tenant_id)
