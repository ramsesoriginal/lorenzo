"""ADR 0462: a stat of the value type `dice` - how a value is written (the notation or its parts),
how every read shows it, what is refused, and what stays as it was for every other type.
"""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from test_api_computed_stats import _sheet
from test_api_setting_down import _named, _scene
from test_api_vocabulary_check import _entry

from lorenzo_api import identical
from lorenzo_api.models import EntityPrototype, EntityStat, StatDefinition, StatValueType


async def _world(test_user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant, damage=StatValueType.DICE, strength=StatValueType.INT, note=StatValueType.TEXT
    )
    return tenant, sheet


def _url(tenant: uuid.UUID, entry: uuid.UUID, stat: uuid.UUID) -> str:
    return f"/tenants/{tenant}/entities/{entry}/stats/{stat}"


async def _read(client: AsyncClient, tenant: uuid.UUID, entry: uuid.UUID) -> dict[str, Any]:
    response = await client.get(f"/tenants/{tenant}/entities/{entry}")
    assert response.status_code == 200, response.text
    return {stat["name"]: stat for stat in response.json()["stats"]}


@pytest.mark.parametrize(
    "written",
    [
        "4W6DL1",
        "4d6dl1",
        "4d6d1",
        " 4D6DL1 ",
        {"count": 4, "sides": 6, "drop": {"mode": "lowest", "count": 1}},
    ],
)
async def test_a_value_written_in_any_form_is_read_back_as_the_canonical_notation_and_parts(
    client: AsyncClient, test_user_id: uuid.UUID, written: Any
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    put = await client.put(_url(tenant, entry, sheet["damage"]), json={"value": written})
    assert put.status_code == 200, put.text
    damage = {s["name"]: s for s in put.json()["stats"]}["damage"]
    assert damage["value"] == "4d6dl1"
    assert damage["dice"] == {"count": 4, "sides": 6, "drop": {"mode": "lowest", "count": 1}}
    assert (damage["own"], damage["computed"]) == (True, False)
    assert put.json()["previous"] == {"had_own_value": False, "value": None}
    # And every other read.
    assert (await _read(client, tenant, entry))["damage"]["dice"]["sides"] == 6
    await delete_tenant(tenant)


async def test_one_die_is_d20_and_a_german_table_reads_its_w_back_as_d(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    url = _url(tenant, entry, sheet["damage"])
    first = await client.put(url, json={"value": "1W20"})
    assert first.status_code == 200, first.text
    stats = {s["name"]: s for s in first.json()["stats"]}
    assert stats["damage"]["value"] == "d20"
    assert stats["damage"]["dice"] == {"count": 1, "sides": 20, "drop": None}
    # A write that replaces it says what it replaced, in the canonical form too.
    second = await client.put(url, json={"value": "2W6"})
    assert second.json()["previous"] == {"had_own_value": True, "value": "d20"}
    third = await client.put(url, json={"value": "4d6dh2"})
    assert {s["name"]: s for s in third.json()["stats"]}["damage"]["dice"]["drop"] == {
        "mode": "highest",
        "count": 2,
    }
    # The row holds the parts of the last value and nothing of the earlier ones.
    async with admin_session_factory() as session:
        row = await session.get_one(EntityStat, (entry, sheet["damage"]))
        assert (row.dice_count, row.dice_sides, row.dice_drop_mode, row.dice_drop_count) == (
            4,
            6,
            "highest",
            2,
        )
        assert (row.value_int, row.value_text, row.value_float, row.value_bool) == (
            None,
            None,
            None,
            None,
        )
    await delete_tenant(tenant)


async def test_a_value_the_entry_inherits_is_shown_with_its_parts(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    prototype = await _entry(tenant, "Longsword")
    entry = await _entry(tenant, "My longsword")
    async with admin_session_factory() as session:
        session.add(EntityPrototype(entity_id=entry, prototype_id=prototype, tenant_id=tenant))
        await session.commit()
    assert (
        await client.put(_url(tenant, prototype, sheet["damage"]), json={"value": "1d8"})
    ).status_code == 200

    damage = (await _read(client, tenant, entry))["damage"]
    assert (damage["value"], damage["own"]) == ("d8", False)
    assert damage["dice"] == {"count": 1, "sides": 8, "drop": None}

    grid = await client.get(
        f"/tenants/{tenant}/entities/effective-stats",
        params={"stat_definition_id": [str(sheet["damage"]), str(sheet["strength"])]},
    )
    rows = {row["name"]: row["stats"] for row in grid.json()["items"]}
    (cell,) = rows["My longsword"]
    assert (cell["value"], cell["dice"]["sides"], cell["own"]) == ("d8", 8, False)

    explained = await client.get(f"{_url(tenant, entry, sheet['damage'])}/explanation")
    assert explained.status_code == 200, explained.text
    assert explained.json()["value"] == "d8"
    assert explained.json()["dice"] == {"count": 1, "sides": 8, "drop": None}
    await delete_tenant(tenant)


async def test_a_stat_of_any_other_type_has_no_dice_in_its_row(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword", strength=(sheet["strength"], 5))
    await client.put(_url(tenant, entry, sheet["note"]), json={"value": "2d6"})
    stats = await _read(client, tenant, entry)
    assert "dice" not in stats["strength"]
    # A text that happens to read like dice is text, as it always was.
    assert (stats["note"]["value"], "dice" in stats["note"]) == ("2d6", False)
    await delete_tenant(tenant)


@pytest.mark.parametrize(
    ("value", "part"),
    [
        ("lots", "notation"),
        ("2d6+3", "notation"),
        ("", "notation"),
        ({"count": 0, "sides": 6}, "count"),
        ({"count": 101, "sides": 6}, "count"),
        ({"count": 2, "sides": 1}, "sides"),
        ({"count": 2, "sides": 1001}, "sides"),
        ("2d1", "sides"),
        ({"count": 4, "sides": 6, "drop": {"mode": "lowest", "count": 4}}, "drop"),
        ({"count": 4, "sides": 6, "drop": {"mode": "lowest", "count": 0}}, "drop"),
        ({"count": 4, "sides": 6, "drop": {"mode": "middle", "count": 1}}, "drop"),
        ("1d6dl1", "drop"),
    ],
)
async def test_what_is_not_dice_is_a_422_naming_the_part_and_nothing_is_written(
    client: AsyncClient, test_user_id: uuid.UUID, value: Any, part: str
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    put = await client.put(_url(tenant, entry, sheet["damage"]), json={"value": value})
    assert put.status_code == 422, put.text
    assert put.json()["type"].endswith("invalid-dice")
    assert put.json()["detail"].startswith(f"{part}:")
    async with admin_session_factory() as session:
        assert await session.get(EntityStat, (entry, sheet["damage"])) is None
    await delete_tenant(tenant)


async def test_a_dice_stat_takes_dice_and_nothing_else_and_dice_go_to_no_other_stat(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    for wrong in (6, 2.5, True):
        put = await client.put(_url(tenant, entry, sheet["damage"]), json={"value": wrong})
        assert put.status_code == 422, (wrong, put.text)
        assert put.json()["type"].endswith("invalid-stat-value-type")
    for stat in ("strength", "note"):
        put = await client.put(
            _url(tenant, entry, sheet[stat]),
            json={"value": {"count": 2, "sides": 6}},
        )
        assert put.status_code == 422, (stat, put.text)
        assert put.json()["type"].endswith("invalid-stat-value-type")
    # A string for a number is what it was: a mismatch.
    text_for_int = await client.put(_url(tenant, entry, sheet["strength"]), json={"value": "2d6"})
    assert text_for_int.status_code == 422
    await delete_tenant(tenant)


async def test_a_dice_stat_has_no_unit_scale_or_enum_values(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    group = (await client.post(f"/tenants/{tenant}/stat-groups", json={"name": "Combat"})).json()
    url = f"/tenants/{tenant}/stat-definitions"
    base = {"stat_group_id": group["id"], "value_type": "dice"}

    created = await client.post(url, json={**base, "name": "damage"})
    assert created.status_code == 201, created.text
    assert created.json()["value_type"] == "dice"
    assert created.json()["unit"] is None

    for name, extra in (
        ("with unit", {"unit": "hp"}),
        ("with scale", {"min_value": 1}),
        ("with enum", {"enum_values": ["a"]}),
    ):
        refused = await client.post(url, json={**base, "name": name, **extra})
        assert refused.status_code == 422, (name, refused.text)
    assert (
        (await client.post(url, json={**base, "name": "with unit", "unit": "hp"}))
        .json()["type"]
        .endswith("invalid-dice")
    )

    patched = await client.patch(f"{url}/{created.json()['id']}", json={"unit": "hp"})
    assert patched.status_code == 422, patched.text
    assert patched.json()["type"].endswith("invalid-dice")
    # Clearing a unit, or changing how it is shown otherwise, is as for any stat.
    shown = await client.patch(f"{url}/{created.json()['id']}", json={"unit": None})
    assert shown.status_code == 200, shown.text
    await delete_tenant(tenant)


async def test_a_dice_value_is_not_a_number_to_a_formula(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    prototype = await _entry(tenant, "Longsword")
    linear = {
        "kind": "linear",
        "source_stat_definition_id": str(sheet["damage"]),
        "multiplier": 1,
        "offset": 0,
        "round_mode": "none",
    }
    read = await client.put(sheet.formula_url(prototype, "strength"), json=linear)
    assert read.status_code == 422, read.text
    # Nor is a formula's result ever a dice value, until a kind says so.
    to_dice = await client.put(
        sheet.formula_url(prototype, "damage"),
        json={**linear, "source_stat_definition_id": str(sheet["strength"])},
    )
    assert to_dice.status_code == 422, to_dice.text
    await delete_tenant(tenant)


async def test_the_table_only_holds_a_dice_value_that_is_whole_and_alone(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    for columns in (
        {"dice_count": 2, "dice_sides": 6, "value_int": 1},  # two values
        {"dice_count": 2},  # no sides
        {"dice_count": 2, "dice_sides": 6, "dice_drop_mode": "lowest"},  # a mode, no count
        {"dice_count": 2, "dice_sides": 6, "dice_drop_mode": "lowest", "dice_drop_count": 2},
        {"dice_count": 2, "dice_sides": 6, "dice_drop_mode": "middle", "dice_drop_count": 1},
        {"dice_count": 0, "dice_sides": 6},
        {"dice_count": 2, "dice_sides": 1},
        {"dice_drop_mode": "lowest", "dice_drop_count": 1, "value_int": 1},  # a drop of nothing
    ):
        async with admin_session_factory() as session:
            session.add(
                EntityStat(
                    entity_id=entry,
                    stat_definition_id=sheet["damage"],
                    tenant_id=tenant,
                    **columns,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
    async with admin_session_factory() as session:
        assert (
            await session.scalars(select(EntityStat).where(EntityStat.entity_id == entry))
        ).all() == []
    await delete_tenant(tenant)


async def test_the_export_writes_a_dice_value_as_its_notation_and_a_mirror_can_put_it_back(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Sword")
    await client.put(_url(tenant, entry, sheet["damage"]), json={"value": "4W6DH1"})
    exported = await client.get(f"/tenants/{tenant}/entities/export")
    assert exported.status_code == 200, exported.text
    (row,) = [e for e in exported.json()["items"] if e["id"] == str(entry)]
    (stat,) = row["stats"]
    assert (stat["stat_definition_id"], stat["value"]) == (str(sheet["damage"]), "4d6dh1")
    # What `PUT .../stats/{id}` takes: the exported value, as it is.
    other = await _entry(tenant, "Copy")
    put = await client.put(_url(tenant, other, sheet["damage"]), json={"value": stat["value"]})
    assert put.status_code == 200, put.text
    await delete_tenant(tenant)


async def test_two_instances_are_identical_only_when_their_dice_are(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    prototype = await _entry(tenant, "Dagger")
    pieces = [await _entry(tenant, "Dagger") for _ in range(3)]
    async with admin_session_factory() as session:
        session.add_all(
            EntityPrototype(entity_id=piece, prototype_id=prototype, tenant_id=tenant)
            for piece in pieces
        )
        await session.commit()
    for piece, written in zip(pieces, ("2d6", "2W6", "2d8"), strict=True):
        put = await client.put(_url(tenant, piece, sheet["damage"]), json={"value": written})
        assert put.status_code == 200, put.text
    async with admin_session_factory() as session:
        signatures = await identical.signatures(
            session, tenant_id=tenant, entity_ids=frozenset(pieces)
        )
    first, same, other = (signatures[piece] for piece in pieces)
    assert first is not None and first == same and first != other
    await delete_tenant(tenant)


async def test_the_pieces_of_a_stack_set_down_keep_its_dice(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _scene(test_user_id)
    arrows = scene.ids["arrows"]
    async with admin_session_factory() as session:
        damage = StatDefinition(
            tenant_id=scene.tenant_id,
            stat_group_id=scene.ids["magic"],
            name="damage",
            value_type=StatValueType.DICE,
        )
        session.add(damage)
        await session.flush()
        session.add(
            EntityStat(
                entity_id=arrows,
                stat_definition_id=damage.id,
                tenant_id=scene.tenant_id,
                dice_count=3,
                dice_sides=8,
                dice_drop_mode="highest",
                dice_drop_count=1,
            )
        )
        await session.commit()
        damage_id = damage.id
    set_down = await client.delete(f"{scene.base}/{arrows}/container", params={"split": True})
    assert set_down.status_code == 200, set_down.text
    pieces = await _named(scene.tenant_id, "Arrows")
    assert len(pieces) == 3
    async with admin_session_factory() as session:
        for piece in pieces:
            held = await session.get_one(EntityStat, (piece, damage_id))
            assert (held.dice_count, held.dice_sides, held.dice_drop_mode) == (3, 8, "highest")
            assert held.dice_drop_count == 1
    await delete_tenant(scene.tenant_id)
