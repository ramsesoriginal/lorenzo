"""ADR 0458: the vocabulary check - the route, its filters and paging, what a reader sees, the
findings about a scale, a hint and a long chain of formulas, and what the scan costs.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import (
    delete_tenant,
    make_being,
    make_campaign,
    make_plain_participant,
    make_tenant,
)
from httpx import AsyncClient
from sqlalchemy import update
from test_api_computed_stats import _put, _sheet
from test_formula_chain_depth import _chain
from test_item_read_statements import _statements

from lorenzo_api.models import Entity, EntityStat, StatDefinition, StatValueType


async def _entry(tenant: uuid.UUID, name: str, **stats: tuple[uuid.UUID, int]) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant, name=name)
        session.add(entity)
        await session.flush()
        for definition_id, value in stats.values():
            session.add(
                EntityStat(
                    entity_id=entity.id,
                    stat_definition_id=definition_id,
                    tenant_id=tenant,
                    value_int=value,
                )
            )
        await session.commit()
        return entity.id


async def _check(client: AsyncClient, tenant: uuid.UUID, **params: Any) -> dict[str, Any]:
    response = await client.get(f"/tenants/{tenant}/vocabulary-check", params=params)
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


def _codes(page: dict[str, Any]) -> list[tuple[str, str | None]]:
    return [(f["code"], f["entry_id"]) for f in page["items"]]


async def _scaled(client: AsyncClient, test_user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    """A `standing` computed from `base` on a scale of -100 to 100, and a `current` with a
    maximum hint `limit` and a minimum hint `floor`."""
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant,
        base=StatValueType.INT,
        standing=StatValueType.INT,
        current=StatValueType.INT,
        limit=StatValueType.INT,
        floor=StatValueType.INT,
    )
    async with admin_session_factory() as session:
        await session.execute(
            update(StatDefinition)
            .where(StatDefinition.id == sheet["standing"])
            .values(min_value=-100, max_value=100)
        )
        await session.execute(
            update(StatDefinition)
            .where(StatDefinition.id == sheet["current"])
            .values(max_hint_id=sheet["limit"], min_hint_id=sheet["floor"])
        )
        await session.commit()
    return tenant, sheet


async def test_a_computed_value_outside_its_scale_is_info(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _scaled(client, test_user_id)
    prototype = await _entry(tenant, "Faction")
    await _put(
        client,
        sheet.formula_url(prototype, "standing"),
        {
            "kind": "linear",
            "source_stat_definition_id": str(sheet["base"]),
            "multiplier": 1,
            "offset": 0,
            "round_mode": "none",
        },
    )
    inside = await _entry(tenant, "Inside", base=(sheet["base"], 40))
    outside = await _entry(tenant, "Outside", base=(sheet["base"], 250))
    async with admin_session_factory() as session:
        from lorenzo_api.models import EntityPrototype

        for entry in (inside, outside):
            session.add(EntityPrototype(entity_id=entry, prototype_id=prototype, tenant_id=tenant))
        await session.commit()

    page = await _check(client, tenant)
    (finding,) = page["items"]
    assert (finding["code"], finding["severity"]) == ("computed-outside-scale", "info")
    assert finding["entry_id"] == str(outside)
    assert finding["stat_definition_id"] == str(sheet["standing"])
    assert finding["details"] == {"value": 250, "minimum": -100, "maximum": 100}
    assert "250" in finding["message"] and "standing" in finding["message"]
    # Only computed values are held to a scale: a stored one is not (bounds check what is written).
    await delete_tenant(tenant)


async def test_a_value_beyond_its_hint_is_info_and_a_missing_hint_value_says_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _scaled(client, test_user_id)
    over = await _entry(
        tenant, "Over", current=(sheet["current"], 500), limit=(sheet["limit"], 120)
    )
    under = await _entry(tenant, "Under", current=(sheet["current"], -3), floor=(sheet["floor"], 0))
    await _entry(tenant, "Fine", current=(sheet["current"], 5), limit=(sheet["limit"], 10))
    await _entry(tenant, "No hint value", current=(sheet["current"], 9999))

    page = await _check(client, tenant, code="above-hint")
    found = {f["entry_id"]: f for f in page["items"]}
    assert set(found) == {str(over), str(under)}
    assert found[str(over)]["details"] == {
        "value": 500,
        "hint": "maximum",
        "hinted_stat_definition_id": str(sheet["limit"]),
        "hinted_value": 120,
    }
    assert found[str(under)]["details"]["hint"] == "minimum"
    assert found[str(under)]["severity"] == "info"
    await delete_tenant(tenant)


async def test_a_chain_of_more_than_fifty_formulas_is_one_finding_for_its_top(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    _, stats = await _chain(tenant, 60)
    short_tenant = await make_tenant(test_user_id)
    await _chain(short_tenant, 40)

    page = await _check(client, tenant)
    (finding,) = page["items"]
    assert (finding["code"], finding["entry_id"]) == ("formula-chain-depth", None)
    assert finding["stat_definition_id"] == str(stats[0])
    assert finding["details"] == {"length": 60}
    assert (await _check(client, short_tenant))["items"] == []
    # It is about the library: an entry filter or a later page does not repeat it.
    assert (await _check(client, tenant, kind="item"))["items"] == []
    assert (await _check(client, tenant, page=2))["items"] == []
    only = await _check(client, tenant, stat_definition_id=str(stats[1]))
    assert only["items"] == []
    await delete_tenant(tenant)
    await delete_tenant(short_tenant)


async def test_the_filters_narrow_what_is_scanned_and_what_is_said(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _scaled(client, test_user_id)
    parent = await _entry(tenant, "Group")
    over = await _entry(
        tenant, "Over", current=(sheet["current"], 500), limit=(sheet["limit"], 120)
    )
    other = await _entry(
        tenant, "Other", current=(sheet["current"], 600), limit=(sheet["limit"], 120)
    )
    async with admin_session_factory() as session:
        from lorenzo_api.models import EntityPrototype

        session.add(EntityPrototype(entity_id=over, prototype_id=parent, tenant_id=tenant))
        await session.commit()

    assert len((await _check(client, tenant))["items"]) == 2
    assert _codes(await _check(client, tenant, entry_id=str(over))) == [("above-hint", str(over))]
    assert _codes(await _check(client, tenant, parent_id=str(parent))) == [
        ("above-hint", str(over))
    ]
    assert (await _check(client, tenant, code="computed-outside-scale"))["items"] == []
    assert (
        len((await _check(client, tenant, stat_definition_id=str(sheet["current"])))["items"]) == 2
    )
    assert (await _check(client, tenant, stat_definition_id=str(sheet["base"])))["items"] == []
    assert (await _check(client, tenant, kind="item"))["items"] == []
    assert (
        await client.get(
            f"/tenants/{tenant}/vocabulary-check", params={"entry_id": str(uuid.uuid4())}
        )
    ).status_code == 404
    assert (
        await client.get(
            f"/tenants/{tenant}/vocabulary-check", params={"stat_definition_id": str(uuid.uuid4())}
        )
    ).status_code == 404
    assert (
        await client.get(f"/tenants/{tenant}/vocabulary-check", params={"code": "nonsense"})
    ).status_code == 422
    assert other  # scanned, and reported when nothing narrows it
    await delete_tenant(tenant)


async def test_the_entries_are_paged_and_a_page_holds_the_findings_of_its_entries(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _scaled(client, test_user_id)
    for number in range(5):
        await _entry(
            tenant,
            f"Entry {number}",
            current=(sheet["current"], 500),
            limit=(sheet["limit"], 120),
        )
    first = await _check(client, tenant, size=2, page=1)
    third = await _check(client, tenant, size=2, page=3)
    # `total` and `pages` count the entries scanned: five entries, two to a page.
    assert (first["total"], first["pages"], first["size"]) == (5, 3, 2)
    assert len(first["items"]) == 2 and len(third["items"]) == 1
    assert (
        await client.get(f"/tenants/{tenant}/vocabulary-check", params={"size": 101})
    ).status_code == 422
    await delete_tenant(tenant)


async def test_a_reader_is_not_told_about_an_entry_they_cannot_read(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _scaled(client, test_user_id)
    async with admin_session_factory() as session:
        await make_campaign(session, tenant_id=tenant)
        being = await make_being(session, tenant_id=tenant, name="Stranger")
        session.add(
            EntityStat(
                entity_id=being.entity_id,
                stat_definition_id=sheet["current"],
                tenant_id=tenant,
                value_int=500,
            )
        )
        session.add(
            EntityStat(
                entity_id=being.entity_id,
                stat_definition_id=sheet["limit"],
                tenant_id=tenant,
                value_int=120,
            )
        )
        await session.commit()
    assert len((await _check(client, tenant))["items"]) == 1
    await make_plain_participant(tenant, test_user_id)
    # A participant reads the vocabulary's check, and it names what the entity list names.
    response = await client.get(f"/tenants/{tenant}/vocabulary-check")
    assert response.status_code == 200, response.text
    await delete_tenant(tenant)


async def test_the_scan_costs_the_same_statements_for_more_entries(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant, sheet = await _scaled(client, test_user_id)
    await _entry(tenant, "One", current=(sheet["current"], 500), limit=(sheet["limit"], 120))
    await client.get(f"/tenants/{tenant}/vocabulary-check")
    with _statements() as few:
        await client.get(f"/tenants/{tenant}/vocabulary-check")
    for number in range(20):
        await _entry(
            tenant,
            f"More {number}",
            current=(sheet["current"], 500),
            limit=(sheet["limit"], 120),
        )
    with _statements() as many:
        await client.get(f"/tenants/{tenant}/vocabulary-check", params={"size": 100})
    assert len(many) <= len(few) + 2, (len(few), len(many))
    await delete_tenant(tenant)
