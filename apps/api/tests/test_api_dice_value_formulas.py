"""ADR 0463: the `dice_value` formula - the minimum, the maximum or the exact average of a dice stat
of the same entry, rounded as any result is; what it refuses; and how it is read, explained,
previewed, listed as a dependent and kept from deletion.
"""

import uuid
from fractions import Fraction
from typing import Any

import pytest
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_api_computed_stats import _sheet
from test_api_dice_values import _read, _url
from test_api_vocabulary_check import _entry

from lorenzo_api.models import StatValueType


def _formula(source: uuid.UUID, read_as: str, round_mode: str = "none") -> dict[str, Any]:
    return {
        "kind": "dice_value",
        "source_stat_definition_id": str(source),
        "as": read_as,
        "round_mode": round_mode,
    }


async def _world(test_user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant,
        damage=StatValueType.DICE,
        low=StatValueType.INT,
        high=StatValueType.INT,
        mean_whole=StatValueType.INT,
        mean=StatValueType.FLOAT,
        label=StatValueType.TEXT,
        strength=StatValueType.INT,
        other_dice=StatValueType.DICE,
    )
    return tenant, sheet


async def _set_dice(client: AsyncClient, tenant, entry, sheet, written: str) -> None:  # type: ignore[no-untyped-def]
    put = await client.put(_url(tenant, entry, sheet["damage"]), json={"value": written})
    assert put.status_code == 200, put.text


async def _value(client: AsyncClient, tenant, entry, name: str):  # type: ignore[no-untyped-def]
    stats = await _read(client, tenant, entry)
    return stats[name]["value"] if name in stats else None


@pytest.mark.parametrize(
    ("written", "low", "high", "mean"),
    [
        ("d20", 1, 20, Fraction(21, 2)),
        ("W20", 1, 20, Fraction(21, 2)),
        ("2d6", 2, 12, Fraction(7)),
        ("4d6dl1", 3, 18, Fraction(15869, 1296)),
        # 14 minus the expected highest of four dice, 6 - 979/1296.
        ("4d6dh1", 3, 18, Fraction(11347, 1296)),
    ],
)
async def test_the_minimum_the_maximum_and_the_exact_average_of_the_dice(
    client: AsyncClient, test_user_id: uuid.UUID, written: str, low: int, high: int, mean: Fraction
) -> None:
    tenant, sheet = await _world(test_user_id)
    prototype = await _entry(tenant, "Longsword")
    for name, read_as in (("low", "min"), ("high", "max"), ("mean", "average")):
        put = await client.put(
            sheet.formula_url(prototype, name), json=_formula(sheet["damage"], read_as)
        )
        assert put.status_code == 200, put.text
    entry = await _entry(tenant, "My longsword")
    await client.put(
        f"/tenants/{tenant}/entities/{entry}/parents", json={"parent_ids": [str(prototype)]}
    )
    await _set_dice(client, tenant, entry, sheet, written)

    stats = await _read(client, tenant, entry)
    assert (stats["low"]["value"], stats["high"]["value"]) == (low, high)
    assert stats["low"]["computed"] and stats["low"]["from_entity"]["id"] == str(prototype)
    assert stats["mean"]["value"] == pytest.approx(float(mean), rel=1e-12)
    await delete_tenant(tenant)


@pytest.mark.parametrize(
    ("round_mode", "expected"),
    [("floor", 10), ("ceil", 11), ("round", 11), ("truncate", 10)],
)
async def test_an_int_stat_takes_the_average_by_a_rounding_mode(
    client: AsyncClient, test_user_id: uuid.UUID, round_mode: str, expected: int
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    await _set_dice(client, tenant, entry, sheet, "d20")
    put = await client.put(
        sheet.formula_url(entry, "mean_whole"),
        json=_formula(sheet["damage"], "average", round_mode),
    )
    assert put.status_code == 200, put.text
    assert await _value(client, tenant, entry, "mean_whole") == expected
    await delete_tenant(tenant)


async def test_a_dice_stat_with_no_value_gives_no_value(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    put = await client.put(sheet.formula_url(entry, "low"), json=_formula(sheet["damage"], "min"))
    assert put.status_code == 200, put.text
    assert await _value(client, tenant, entry, "low") is None
    await _set_dice(client, tenant, entry, sheet, "3d8")
    assert await _value(client, tenant, entry, "low") == 3
    # And it follows the dice when they change.
    await _set_dice(client, tenant, entry, sheet, "5d8dl2")
    assert await _value(client, tenant, entry, "low") == 3
    await _set_dice(client, tenant, entry, sheet, "6d8dl2")
    assert await _value(client, tenant, entry, "low") == 4
    await delete_tenant(tenant)


async def test_the_formula_reads_back_with_its_as_and_is_explained(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    await _set_dice(client, tenant, entry, sheet, "4W6DL1")
    body = _formula(sheet["damage"], "average", "round")
    put = await client.put(sheet.formula_url(entry, "mean_whole"), json=body)
    assert put.status_code == 200, put.text
    assert put.json()["formula"] == body

    listed = await client.get(f"/tenants/{tenant}/entities/{entry}/computed-stats")
    assert [f["formula"] for f in listed.json()] == [body]

    explained = await client.get(f"{_url(tenant, entry, sheet['mean_whole'])}/explanation")
    assert explained.status_code == 200, explained.text
    assert explained.json()["value"] == 12
    assert explained.json()["formula"] == body
    (source,) = explained.json()["inputs"]
    assert (source["name"], source["value"]) == ("damage", "4d6dl1")
    await delete_tenant(tenant)


async def test_a_preview_reads_the_dice_without_writing_anything(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    await _set_dice(client, tenant, entry, sheet, "2d6")
    preview = await client.post(
        f"{sheet.formula_url(entry, 'high')}/preview",
        json={"formula": _formula(sheet["damage"], "max")},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["value"] == 12
    assert [(i["name"], i["value"]) for i in preview.json()["inputs"]] == [("damage", "2d6")]
    assert await _value(client, tenant, entry, "high") is None
    await delete_tenant(tenant)


async def test_what_a_dice_value_cannot_read_or_become_is_a_422(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")

    async def put(target: str, body: dict[str, Any]) -> Any:
        return await client.put(sheet.formula_url(entry, target), json=body)

    # A source that is not dice.
    for source in ("strength", "label"):
        refused = await put("low", _formula(sheet[source], "min"))
        assert refused.status_code == 422, (source, refused.text)
        assert "reads dice" in refused.json()["detail"]
    # A target that is not a number.
    for target in ("label", "other_dice"):
        refused = await put(target, _formula(sheet["damage"], "min"))
        assert refused.status_code == 422, (target, refused.text)
        assert "int or float" in refused.json()["detail"]
    # An average is rarely whole: an int stat needs a rounding mode for it, a min and a max do not.
    refused = await put("mean_whole", _formula(sheet["damage"], "average"))
    assert refused.status_code == 422
    assert "rounding mode" in refused.json()["detail"]
    for read_as in ("min", "max"):
        assert (await put("mean_whole", _formula(sheet["damage"], read_as))).status_code == 200
    assert (await put("mean", _formula(sheet["damage"], "average"))).status_code == 200
    # What can be read is min, max or average.
    unknown = await put("low", _formula(sheet["damage"], "median"))
    assert unknown.status_code == 422
    missing = await put(
        "low", {"kind": "dice_value", "source_stat_definition_id": str(sheet["damage"])}
    )
    assert missing.status_code == 422
    await delete_tenant(tenant)


async def test_the_dice_stat_is_read_by_a_dependent_and_cannot_be_deleted_while_it_is(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    put = await client.put(sheet.formula_url(entry, "high"), json=_formula(sheet["damage"], "max"))
    assert put.status_code == 200, put.text

    dependents = await client.get(
        f"/tenants/{tenant}/stat-definitions/{sheet['damage']}/dependents"
    )
    assert [(d["entity_id"], d["stat_definition_id"], d["kind"]) for d in dependents.json()] == [
        (str(entry), str(sheet["high"]), "dice_value")
    ]

    blocked = await client.delete(f"/tenants/{tenant}/stat-definitions/{sheet['damage']}")
    assert blocked.status_code == 409, blocked.text
    assert "formula" in blocked.json()["detail"]
    await client.delete(sheet.formula_url(entry, "high"))
    freed = await client.delete(f"/tenants/{tenant}/stat-definitions/{sheet['damage']}")
    assert freed.status_code == 204, freed.text
    await delete_tenant(tenant)


async def test_replacing_a_dice_value_by_another_kind_and_back_leaves_one_formula(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword", strength=(sheet["strength"], 9))
    url = sheet.formula_url(entry, "high")
    await _set_dice(client, tenant, entry, sheet, "d8")
    assert (await client.put(url, json=_formula(sheet["damage"], "max"))).status_code == 200
    linear = {
        "kind": "linear",
        "source_stat_definition_id": str(sheet["strength"]),
        "multiplier": 2,
        "offset": 0,
        "round_mode": "none",
    }
    assert (await client.put(url, json=linear)).status_code == 200
    assert await _value(client, tenant, entry, "high") == 18
    assert (await client.put(url, json=_formula(sheet["damage"], "min"))).status_code == 200
    assert await _value(client, tenant, entry, "high") == 1
    (only,) = (await client.get(f"/tenants/{tenant}/entities/{entry}/computed-stats")).json()
    assert only["formula"]["kind"] == "dice_value"
    await delete_tenant(tenant)
