"""ADR 0464: the `dice` formula - a dice value built from a count and a number of sides, each a stat
or a constant; what it refuses; how it is read, explained and kept; that `dice_value` reads what it
builds; and that the link preview of an item prints a dice stat's notation.
"""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_api_computed_stats import _sheet
from test_api_dice_value_formulas import _formula as _dice_value
from test_api_dice_values import _read, _url
from test_api_vocabulary_check import _entry

from lorenzo_api.models import Item, StatValueType


def _dice(**parts: Any) -> dict[str, Any]:
    return {"kind": "dice", **parts}


async def _world(test_user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant,
        damage=StatValueType.DICE,
        level=StatValueType.INT,
        die=StatValueType.INT,
        ratio=StatValueType.FLOAT,
        label=StatValueType.TEXT,
        most=StatValueType.INT,
        mean=StatValueType.FLOAT,
        other_dice=StatValueType.DICE,
    )
    return tenant, sheet


async def _damage(client: AsyncClient, tenant, entry):  # type: ignore[no-untyped-def]
    stats = await _read(client, tenant, entry)
    return stats.get("damage")


async def _set(client: AsyncClient, tenant, entry, sheet, name: str, value: int) -> None:  # type: ignore[no-untyped-def]
    put = await client.put(_url(tenant, entry, sheet[name]), json={"value": value})
    assert put.status_code == 200, put.text


async def test_a_count_and_sides_from_stats_or_constants_make_dice(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    prototype = await _entry(tenant, "Fighter")
    entry = await _entry(tenant, "Hero", level=(sheet["level"], 3), die=(sheet["die"], 8))
    await client.put(
        f"/tenants/{tenant}/entities/{entry}/parents", json={"parent_ids": [str(prototype)]}
    )
    both = _dice(
        count_stat_definition_id=str(sheet["level"]), sides_stat_definition_id=str(sheet["die"])
    )
    put = await client.put(sheet.formula_url(prototype, "damage"), json=both)
    assert put.status_code == 200, put.text
    assert put.json()["formula"] == {
        "kind": "dice",
        "count_stat_definition_id": str(sheet["level"]),
        "count_constant": None,
        "sides_stat_definition_id": str(sheet["die"]),
        "sides_constant": None,
    }

    damage = await _damage(client, tenant, entry)
    assert damage["value"] == "3d8"
    assert damage["dice"] == {"count": 3, "sides": 8, "drop": None}
    assert (damage["computed"], damage["own"]) == (True, False)
    assert damage["from_entity"]["id"] == str(prototype)

    # A count from a stat and constant sides; and a constant count, one die is `d20`.
    only_count = _dice(count_stat_definition_id=str(sheet["level"]), sides_constant=6)
    assert (
        await client.put(sheet.formula_url(prototype, "damage"), json=only_count)
    ).status_code == 200
    assert (await _damage(client, tenant, entry))["value"] == "3d6"
    one = _dice(count_constant=1, sides_constant=20)
    assert (await client.put(sheet.formula_url(prototype, "damage"), json=one)).status_code == 200
    assert (await _damage(client, tenant, entry))["value"] == "d20"
    # It follows the stats.
    await _set(client, tenant, entry, sheet, "level", 5)
    assert (
        await client.put(sheet.formula_url(prototype, "damage"), json=only_count)
    ).status_code == 200
    assert (await _damage(client, tenant, entry))["value"] == "5d6"
    await delete_tenant(tenant)


@pytest.mark.parametrize(("count", "sides"), [(0, 8), (101, 8), (3, 1), (3, 1001), (-2, 6)])
async def test_a_number_the_dice_cannot_have_gives_no_value_and_no_failure(
    client: AsyncClient, test_user_id: uuid.UUID, count: int, sides: int
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero")
    # The limits are the table's, and a stat can hold what a dice cannot (its scale is open).
    await _set(client, tenant, entry, sheet, "level", count)
    await _set(client, tenant, entry, sheet, "die", sides)
    both = _dice(
        count_stat_definition_id=str(sheet["level"]), sides_stat_definition_id=str(sheet["die"])
    )
    assert (await client.put(sheet.formula_url(entry, "damage"), json=both)).status_code == 200
    assert await _damage(client, tenant, entry) is None
    await delete_tenant(tenant)


async def test_a_stat_with_no_value_gives_the_dice_no_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero", die=(sheet["die"], 6))
    body = _dice(
        count_stat_definition_id=str(sheet["level"]), sides_stat_definition_id=str(sheet["die"])
    )
    assert (await client.put(sheet.formula_url(entry, "damage"), json=body)).status_code == 200
    assert await _damage(client, tenant, entry) is None
    await _set(client, tenant, entry, sheet, "level", 2)
    assert (await _damage(client, tenant, entry))["value"] == "2d6"
    await delete_tenant(tenant)


async def test_dice_value_reads_the_dice_a_formula_built(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero", level=(sheet["level"], 2))
    built = _dice(count_stat_definition_id=str(sheet["level"]), sides_constant=6)
    assert (await client.put(sheet.formula_url(entry, "damage"), json=built)).status_code == 200
    for name, read_as in (("most", "max"), ("mean", "average")):
        put = await client.put(
            sheet.formula_url(entry, name), json=_dice_value(sheet["damage"], read_as)
        )
        assert put.status_code == 200, put.text
    stats = await _read(client, tenant, entry)
    assert (stats["damage"]["value"], stats["most"]["value"], stats["mean"]["value"]) == (
        "2d6",
        12,
        7.0,
    )
    await _set(client, tenant, entry, sheet, "level", 4)
    stats = await _read(client, tenant, entry)
    assert (stats["damage"]["value"], stats["most"]["value"], stats["mean"]["value"]) == (
        "4d6",
        24,
        14.0,
    )
    await delete_tenant(tenant)


async def test_it_is_explained_and_previewed_and_its_stats_are_dependents(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero", level=(sheet["level"], 3))
    body = _dice(count_stat_definition_id=str(sheet["level"]), sides_constant=10)

    preview = await client.post(
        f"{sheet.formula_url(entry, 'damage')}/preview", json={"formula": body}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["value"] == "3d10"
    assert await _damage(client, tenant, entry) is None

    assert (await client.put(sheet.formula_url(entry, "damage"), json=body)).status_code == 200
    explained = await client.get(f"{_url(tenant, entry, sheet['damage'])}/explanation")
    assert explained.status_code == 200, explained.text
    assert explained.json()["value"] == "3d10"
    assert explained.json()["dice"] == {"count": 3, "sides": 10, "drop": None}
    assert explained.json()["formula"]["kind"] == "dice"
    assert [(i["name"], i["value"]) for i in explained.json()["inputs"]] == [("level", 3)]

    dependents = await client.get(f"/tenants/{tenant}/stat-definitions/{sheet['level']}/dependents")
    assert [(d["entity_id"], d["kind"]) for d in dependents.json()] == [(str(entry), "dice")]
    blocked = await client.delete(f"/tenants/{tenant}/stat-definitions/{sheet['level']}")
    assert blocked.status_code == 409, blocked.text
    assert "formula" in blocked.json()["detail"]
    await delete_tenant(tenant)


async def test_what_a_dice_formula_cannot_read_or_become_is_a_422(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero")

    async def put(target: str, body: dict[str, Any]) -> Any:
        return await client.put(sheet.formula_url(entry, target), json=body)

    fine = _dice(count_constant=2, sides_constant=6)
    # Only dice come out of it.
    for target in ("level", "ratio", "label"):
        refused = await put(target, fine)
        assert refused.status_code == 422, (target, refused.text)
        assert "dice stat" in refused.json()["detail"]
    # Only whole numbers go in: an int stat.
    for source in ("ratio", "label", "other_dice"):
        refused = await put(
            "damage", _dice(count_stat_definition_id=str(sheet[source]), sides_constant=6)
        )
        assert refused.status_code == 422, (source, refused.text)
        assert "int stat" in refused.json()["detail"]
    # Exactly one of a stat or a constant for each, within the limits.
    for body in (
        _dice(sides_constant=6),
        _dice(count_constant=2),
        _dice(count_constant=2, count_stat_definition_id=str(sheet["level"]), sides_constant=6),
        _dice(count_constant=2, sides_constant=6, sides_stat_definition_id=str(sheet["die"])),
        _dice(count_constant=0, sides_constant=6),
        _dice(count_constant=101, sides_constant=6),
        _dice(count_constant=2, sides_constant=1),
        _dice(count_constant=2, sides_constant=1001),
        _dice(count_constant=2.5, sides_constant=6),
    ):
        refused = await put("damage", body)
        assert refused.status_code == 422, (body, refused.text)
    assert (await put("damage", fine)).status_code == 200
    await delete_tenant(tenant)


async def test_a_dice_formula_and_an_own_dice_value_cannot_be_held_together(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero")
    put = await client.put(
        sheet.formula_url(entry, "damage"), json=_dice(count_constant=2, sides_constant=6)
    )
    assert put.status_code == 200, put.text
    own = await client.put(_url(tenant, entry, sheet["damage"]), json={"value": "1d4"})
    assert own.status_code == 409, own.text
    await delete_tenant(tenant)


async def test_the_link_preview_of_an_item_prints_a_dice_stat_as_its_damage(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    prototype = await _entry(tenant, "Longsword")
    renamed = await client.patch(
        f"/tenants/{tenant}/stat-definitions/{sheet['damage']}", json={"name": "Damage"}
    )
    assert renamed.status_code == 200, renamed.text
    assert (
        await client.put(_url(tenant, prototype, sheet["damage"]), json={"value": "W8"})
    ).status_code == 200
    async with admin_session_factory() as session:
        session.add(Item(entity_id=prototype, tenant_id=tenant))
        await session.commit()

    card = await client.get(f"/tenants/{tenant}/entities/{prototype}/preview")
    assert card.status_code == 200, card.text
    assert [(s["name"], s["value"]) for s in card.json()["stats"]] == [("Damage", "d8")]
    await delete_tenant(tenant)
