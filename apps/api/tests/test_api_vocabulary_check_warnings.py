"""ADR 0461: a write of a stat or of a formula answers with `warnings` when asked, refuses nothing,
and costs nothing when not asked.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import update
from test_api_computed_stats import _sheet
from test_api_vocabulary_check import _entry
from test_item_read_statements import _statements

from lorenzo_api.models import EntityPrototype, StatDefinition, StatValueType


def _linear(source: uuid.UUID) -> dict[str, Any]:
    return {
        "kind": "linear",
        "source_stat_definition_id": str(source),
        "multiplier": 1,
        "offset": 0,
        "round_mode": "none",
    }


async def _world(test_user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant,
        current=StatValueType.INT,
        limit=StatValueType.INT,
        base=StatValueType.INT,
        standing=StatValueType.INT,
        flag=StatValueType.BOOL,
    )
    async with admin_session_factory() as session:
        await session.execute(
            update(StatDefinition)
            .where(StatDefinition.id == sheet["current"])
            .values(max_hint_id=sheet["limit"])
        )
        await session.execute(
            update(StatDefinition)
            .where(StatDefinition.id == sheet["standing"])
            .values(min_value=-100, max_value=100)
        )
        await session.commit()
    return tenant, sheet


async def test_a_stat_write_answers_with_warnings_only_when_asked(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero", limit=(sheet["limit"], 120))
    url = f"/tenants/{tenant}/entities/{entry}/stats/{sheet['current']}"

    plain = await client.put(url, json={"value": 500})
    assert plain.status_code == 200, plain.text
    assert "warnings" not in plain.json()

    asked = await client.put(url, json={"value": 500}, params={"warnings": "true"})
    assert asked.status_code == 200, asked.text
    (warning,) = asked.json()["warnings"]
    assert (warning["code"], warning["severity"]) == ("above-hint", "info")
    assert warning["entry_id"] == str(entry)
    assert warning["stat_definition_id"] == str(sheet["current"])
    assert warning["details"]["hinted_value"] == 120
    # Nothing was refused: the value is held.
    assert {s["name"]: s["value"] for s in asked.json()["stats"]}["current"] == 500

    # A value within the hint says nothing, and the list is there, empty.
    fine = await client.put(url, json={"value": 5}, params={"warnings": "true"})
    assert fine.json()["warnings"] == []
    await delete_tenant(tenant)


async def test_a_tag_write_can_ask_for_warnings_too(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero")
    url = f"/tenants/{tenant}/entities/{entry}/tags/{sheet['flag']}"
    asked = await client.put(url, params={"warnings": "true"})
    assert asked.status_code == 200, asked.text
    assert asked.json()["warnings"] == []
    cleared = await client.patch(url, params={"warnings": "true"})
    assert cleared.json()["warnings"] == []
    assert "warnings" not in (await client.put(url)).json()
    await delete_tenant(tenant)


async def test_a_formula_write_says_what_it_leaves_unset_and_what_it_shadows(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    prototype = await _entry(tenant, "Faction")
    entry = await _entry(tenant, "Hero", standing=(sheet["standing"], 7))
    async with admin_session_factory() as session:
        session.add(EntityPrototype(entity_id=entry, prototype_id=prototype, tenant_id=tenant))
        await session.commit()
    url = f"/tenants/{tenant}/entities/{prototype}/computed-stats/{sheet['standing']}"

    plain = await client.put(url, json=_linear(sheet["base"]))
    assert plain.status_code == 200, plain.text
    assert "warnings" not in plain.json()

    asked = await client.put(url, json=_linear(sheet["base"]), params={"warnings": "true"})
    assert asked.status_code == 200, asked.text
    (warning,) = asked.json()["warnings"]
    # The prototype now has a formula and no base to read: no value, and it says so.
    assert (warning["code"], warning["entry_id"]) == ("unset-input", str(prototype))
    assert warning["details"]["inputs_without_value"] == [str(sheet["base"])]
    # Hero's own value is not touched by a formula on the prototype, and a formula of its own is
    # refused as it always was (a check says nothing of a write that did not happen).
    on_hero = await client.put(
        f"/tenants/{tenant}/entities/{entry}/computed-stats/{sheet['standing']}",
        json=_linear(sheet["base"]),
        params={"warnings": "true"},
    )
    assert on_hero.status_code == 409
    await delete_tenant(tenant)


async def test_a_value_that_shadows_a_formula_is_told_on_its_own_write(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    prototype = await _entry(tenant, "Faction", base=(sheet["base"], 400))
    put = await client.put(
        f"/tenants/{tenant}/entities/{prototype}/computed-stats/{sheet['standing']}",
        json=_linear(sheet["base"]),
        params={"warnings": "true"},
    )
    # 400 is beyond the scale of -100 to 100: said, not refused.
    assert [w["code"] for w in put.json()["warnings"]] == ["computed-outside-scale"]
    entry = await _entry(tenant, "Hero")
    async with admin_session_factory() as session:
        session.add(EntityPrototype(entity_id=entry, prototype_id=prototype, tenant_id=tenant))
        await session.commit()
    own = await client.put(
        f"/tenants/{tenant}/entities/{entry}/stats/{sheet['standing']}",
        json={"value": 7},
        params={"warnings": "true"},
    )
    assert own.status_code == 200, own.text
    (warning,) = own.json()["warnings"]
    assert warning["code"] == "own-value-shadows-formula"
    assert warning["details"] == {"own_value": 7, "formula_entry_id": str(prototype)}
    await delete_tenant(tenant)


async def test_asking_costs_a_bounded_number_of_statements_and_not_asking_costs_none(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _world(test_user_id)
    entry = await _entry(tenant, "Hero", limit=(sheet["limit"], 120))
    url = f"/tenants/{tenant}/entities/{entry}/stats/{sheet['current']}"
    await client.put(url, json={"value": 5})
    with _statements() as without:
        await client.put(url, json={"value": 6})
    with _statements() as asked:
        await client.put(url, json={"value": 7}, params={"warnings": "true"})
    # Without it no check ran: none of the check's queries (the prototype walk of a tie) is there.
    assert not [s for s in without if "ancestor_id, hops, path" in s]
    assert [s for s in asked if "ancestor_id, hops, path" in s]
    # A fixed number, whatever the entry holds (the loading of one entry, its walk, its candidates,
    # the visibility of the caller): a bound with a little room over what it measured.
    assert len(asked) - len(without) <= 30, (len(without), len(asked))
    await delete_tenant(tenant)
