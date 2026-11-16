"""ADR 0459: the findings about a computed stat that has no value for want of an input, and an own
value that wins over a formula an ancestor holds.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_api_computed_stats import _put, _sheet
from test_api_vocabulary_check import _check, _codes, _entry
from test_item_read_statements import _statements

from lorenzo_api.models import EntityPrototype, StatValueType


async def _under(tenant: uuid.UUID, entry: uuid.UUID, prototype: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        session.add(EntityPrototype(entity_id=entry, prototype_id=prototype, tenant_id=tenant))
        await session.commit()


def _linear(source: uuid.UUID) -> dict[str, Any]:
    return {
        "kind": "linear",
        "source_stat_definition_id": str(source),
        "multiplier": 1,
        "offset": 0,
        "round_mode": "none",
    }


async def test_a_computed_stat_with_no_value_names_the_inputs_that_have_none(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, strength=StatValueType.INT, modifier=StatValueType.INT)
    prototype = await _entry(tenant, "Fighter")
    await _put(client, sheet.formula_url(prototype, "modifier"), _linear(sheet["strength"]))
    with_input = await _entry(tenant, "Strong", strength=(sheet["strength"], 16))
    without = await _entry(tenant, "Blank")
    for entry in (with_input, without):
        await _under(tenant, entry, prototype)

    page = await _check(client, tenant, code="unset-input")
    found = {f["entry_id"]: f for f in page["items"]}
    # The prototype has the formula and no strength either, so it has no modifier.
    assert set(found) == {str(prototype), str(without)}
    finding = found[str(without)]
    assert (finding["code"], finding["severity"]) == ("unset-input", "warning")
    assert finding["stat_definition_id"] == str(sheet["modifier"])
    assert finding["details"] == {
        "formula_entry_id": str(prototype),
        "kind": "linear",
        "inputs_without_value": [str(sheet["strength"])],
    }
    assert "modifier" in finding["message"] and "strength" in finding["message"]
    assert _codes(await _check(client, tenant, entry_id=str(with_input), code="unset-input")) == []
    await delete_tenant(tenant)


async def test_an_own_value_that_wins_over_a_formula_an_ancestor_holds_is_a_warning(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, strength=StatValueType.INT, modifier=StatValueType.INT)
    prototype = await _entry(tenant, "Fighter", strength=(sheet["strength"], 14))
    await _put(client, sheet.formula_url(prototype, "modifier"), _linear(sheet["strength"]))
    shadowed = await _entry(tenant, "Shadowed", modifier=(sheet["modifier"], 7))
    plain = await _entry(tenant, "Plain")
    owner = await _entry(tenant, "Own formula", strength=(sheet["strength"], 3))
    for entry in (shadowed, plain, owner):
        await _under(tenant, entry, prototype)
    await _put(client, sheet.formula_url(owner, "modifier"), _linear(sheet["strength"]))

    page = await _check(client, tenant, code="own-value-shadows-formula")
    (finding,) = page["items"]
    assert (finding["code"], finding["severity"]) == ("own-value-shadows-formula", "warning")
    assert finding["entry_id"] == str(shadowed)
    assert finding["stat_definition_id"] == str(sheet["modifier"])
    assert finding["details"] == {"own_value": 7, "formula_entry_id": str(prototype)}
    # The prototype holds the formula itself: nothing is shadowed there.
    assert _codes(await _check(client, tenant, entry_id=str(prototype))) == []
    await delete_tenant(tenant)


async def test_the_new_findings_cost_no_statement_for_each_entry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, strength=StatValueType.INT, modifier=StatValueType.INT)
    prototype = await _entry(tenant, "Fighter")
    await _put(client, sheet.formula_url(prototype, "modifier"), _linear(sheet["strength"]))
    first = await _entry(tenant, "First", modifier=(sheet["modifier"], 1))
    await _under(tenant, first, prototype)
    await client.get(f"/tenants/{tenant}/vocabulary-check")
    with _statements() as few:
        await client.get(f"/tenants/{tenant}/vocabulary-check")
    for number in range(15):
        entry = await _entry(tenant, f"More {number}", modifier=(sheet["modifier"], number))
        await _under(tenant, entry, prototype)
    with _statements() as many:
        page = await client.get(f"/tenants/{tenant}/vocabulary-check", params={"size": 100})
    assert len(page.json()["items"]) >= 16
    assert len(many) <= len(few) + 2, (len(few), len(many))
    await delete_tenant(tenant)
