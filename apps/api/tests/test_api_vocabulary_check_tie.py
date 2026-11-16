"""ADR 0460: the `tie` finding, read for one entry - the parent order that broke it, a higher group
priority that did, what is not a tie, and the 422 without an entry.
"""

import uuid

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from sqlalchemy import update
from test_api_computed_stats import _sheet
from test_api_vocabulary_check import _entry
from test_item_read_statements import _statements

from lorenzo_api.models import (
    EntityPrototype,
    EntityStatGroup,
    StatGroup,
    StatValueType,
)


async def _parents(client: AsyncClient, tenant: uuid.UUID, entry: uuid.UUID, *parents: uuid.UUID):  # type: ignore[no-untyped-def]
    response = await client.put(
        f"/tenants/{tenant}/entities/{entry}/parents",
        json={"parent_ids": [str(p) for p in parents]},
    )
    assert response.status_code == 200, response.text


async def _ties(client: AsyncClient, tenant: uuid.UUID, entry: uuid.UUID, **params: str):  # type: ignore[no-untyped-def]
    response = await client.get(
        f"/tenants/{tenant}/vocabulary-check",
        params={"entry_id": str(entry), "code": "tie", **params},
    )
    assert response.status_code == 200, response.text
    return response.json()["items"]


async def test_two_parents_at_the_same_distance_are_a_tie_the_parent_order_broke(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, bonus=StatValueType.INT)
    base = await _entry(tenant, "Base", bonus=(sheet["bonus"], 0))
    race = await _entry(tenant, "Race", bonus=(sheet["bonus"], 2))
    being = await _entry(tenant, "Being")
    await _parents(client, tenant, being, base, race)

    (finding,) = await _ties(client, tenant, being)
    assert (finding["code"], finding["severity"]) == ("tie", "warning")
    assert finding["entry_id"] == str(being)
    assert finding["stat_definition_id"] == str(sheet["bonus"])
    assert finding["details"]["reason"] == "parent order"
    assert finding["details"]["winner"] == {
        "entry_id": str(base),
        "distance": 1,
        "computed": False,
    }
    assert finding["details"]["others"] == [
        {"entry_id": str(race), "distance": 1, "computed": False}
    ]
    assert "bonus" in finding["message"] and "parent order" in finding["message"]

    # Put the race first: it wins, and says so.
    await _parents(client, tenant, being, race, base)
    (swapped,) = await _ties(client, tenant, being)
    assert swapped["details"]["winner"]["entry_id"] == str(race)
    await delete_tenant(tenant)


async def test_a_higher_group_priority_is_the_reason_when_it_decided(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, bonus=StatValueType.INT)
    first = await _entry(tenant, "First", bonus=(sheet["bonus"], 0))
    second = await _entry(tenant, "Second", bonus=(sheet["bonus"], 2))
    being = await _entry(tenant, "Being")
    await _parents(client, tenant, being, first, second)
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=tenant, name="Race", priority=9)
        session.add(group)
        await session.flush()
        session.add(EntityStatGroup(entity_id=second, stat_group_id=group.id, tenant_id=tenant))
        await session.commit()

    (finding,) = await _ties(client, tenant, being)
    assert finding["details"]["reason"] == "group priority"
    assert finding["details"]["winner"]["entry_id"] == str(second)
    await delete_tenant(tenant)


async def test_what_is_not_a_tie_is_not_reported(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, bonus=StatValueType.INT, other=StatValueType.INT)
    grand = await _entry(tenant, "Grand", bonus=(sheet["bonus"], 1))
    near = await _entry(tenant, "Near", bonus=(sheet["bonus"], 2))
    middle = await _entry(tenant, "Middle")
    other_parent = await _entry(tenant, "Other parent")
    being = await _entry(tenant, "Being")
    async with admin_session_factory() as session:
        session.add(EntityPrototype(entity_id=middle, prototype_id=grand, tenant_id=tenant))
        await session.commit()
    # `Near` is a parent, `Grand` a grandparent through `Middle`: different distances.
    await _parents(client, tenant, being, near, middle)
    assert await _ties(client, tenant, being) == []
    # An own value is nearest of all.
    async with admin_session_factory() as session:
        from lorenzo_api.models import EntityStat

        session.add(
            EntityStat(
                entity_id=being, stat_definition_id=sheet["bonus"], tenant_id=tenant, value_int=5
            )
        )
        await session.commit()
    assert await _ties(client, tenant, being) == []
    assert other_parent
    await delete_tenant(tenant)


async def test_a_tie_is_read_for_one_entry_and_a_stat_can_narrow_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, bonus=StatValueType.INT, speed=StatValueType.INT)
    a = await _entry(tenant, "A", bonus=(sheet["bonus"], 1), speed=(sheet["speed"], 30))
    b = await _entry(tenant, "B", bonus=(sheet["bonus"], 2), speed=(sheet["speed"], 25))
    being = await _entry(tenant, "Being")
    await _parents(client, tenant, being, a, b)

    url = f"/tenants/{tenant}/vocabulary-check"
    assert (await client.get(url, params={"code": "tie"})).status_code == 422
    assert (await client.get(url, params={"code": ["tie", "above-hint"]})).status_code == 422
    # Left out of the default set without an entry, and in it with one.
    default = await client.get(url)
    assert all(f["code"] != "tie" for f in default.json()["items"])
    with_entry = await client.get(url, params={"entry_id": str(being)})
    assert sorted(f["code"] for f in with_entry.json()["items"]) == ["tie", "tie"]
    narrowed = await _ties(client, tenant, being, stat_definition_id=str(sheet["speed"]))
    assert [f["stat_definition_id"] for f in narrowed] == [str(sheet["speed"])]
    await delete_tenant(tenant)


async def test_a_tie_costs_the_same_statements_for_more_stats(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    names = {f"s{i}": StatValueType.INT for i in range(12)}
    sheet = await _sheet(tenant, **names)
    first = await _entry(tenant, "First", s0=(sheet["s0"], 1))
    second = await _entry(tenant, "Second", s0=(sheet["s0"], 2))
    being = await _entry(tenant, "Being")
    await _parents(client, tenant, being, first, second)
    await _ties(client, tenant, being)
    with _statements() as few:
        await _ties(client, tenant, being)
    async with admin_session_factory() as session:
        await session.execute(
            update(StatGroup).where(StatGroup.tenant_id == tenant).values(priority=0)
        )
        from lorenzo_api.models import EntityStat

        for i in range(1, 12):
            for holder, value in ((first, 1), (second, 2)):
                session.add(
                    EntityStat(
                        entity_id=holder,
                        stat_definition_id=sheet[f"s{i}"],
                        tenant_id=tenant,
                        value_int=value,
                    )
                )
        await session.commit()
    with _statements() as many:
        items = await _ties(client, tenant, being)
    assert len(items) == 12
    assert len(many) <= len(few) + 1, (len(few), len(many))
    await delete_tenant(tenant)
