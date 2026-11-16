"""ADR 0466: the card of a feature, and of one a holder has, shows the stats a template of the
library names; any other kind has the card its kind has.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from test_api_computed_stats import _sheet
from test_api_features import _award, _feature, _stat_on

from lorenzo_api.models import StatGroup, StatValueType


async def _template(client: AsyncClient, tenant: uuid.UUID, name: str, **body: Any) -> dict:
    made = await client.post(f"/tenants/{tenant}/templates", json={"name": name, **body})
    assert made.status_code == 201, made.text
    return made.json()  # type: ignore[no-any-return]


async def _card(client: AsyncClient, tenant: uuid.UUID, entry: uuid.UUID) -> list[tuple[str, Any]]:
    response = await client.get(f"/tenants/{tenant}/entities/{entry}/preview")
    assert response.status_code == 200, response.text
    return [(s["name"], s["value"]) for s in response.json()["stats"]]


def _listed(*stats: tuple[uuid.UUID, str | None]) -> dict[str, Any]:
    return {
        "kind": "stats",
        "stats": [
            {"stat_definition_id": str(stat), **({"label": label} if label else {})}
            for stat, label in stats
        ],
    }


async def test_a_feature_shows_no_stat_until_a_template_names_them(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, damage=StatValueType.INT, range_=StatValueType.INT)
    fireball = await _feature(client, tenant, "Fireball")
    await _stat_on(tenant, fireball, sheet["damage"], 8)
    assert await _card(client, tenant, fireball) == []

    await _template(
        client,
        tenant,
        "Spell card",
        required_kind="feature",
        slots=[_listed((sheet["damage"], "Dmg"), (sheet["range_"], None))],
    )
    # In the slot's order, as the template labels them, the ones the entry has a value for.
    assert await _card(client, tenant, fireball) == [("Dmg", 8)]
    await _stat_on(tenant, fireball, sheet["range_"], 150)
    assert await _card(client, tenant, fireball) == [("Dmg", 8), ("range_", 150)]
    await delete_tenant(tenant)


async def test_an_instance_a_holder_has_shows_what_its_feature_gives_and_its_own_by_its_template(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, damage=StatValueType.INT, uses=StatValueType.INT)
    fireball = await _feature(client, tenant, "Fireball")
    await _stat_on(tenant, fireball, sheet["damage"], 8)
    async with admin_session_factory() as session:
        hero = (await make_being(session, tenant_id=tenant, name="Hero")).entity_id
        await session.commit()
    instance = uuid.UUID((await _award(client, tenant, hero, fireball)).json()["id"])
    await _stat_on(tenant, instance, sheet["uses"], 2)
    stats = [(sheet["uses"], None), (sheet["damage"], None)]

    # A template for features does not cover an instance, and the other way round.
    await _template(
        client, tenant, "Feature card", required_kind="feature", slots=[_listed(*stats[1:])]
    )
    assert await _card(client, tenant, instance) == []
    await _template(
        client, tenant, "Held card", required_kind="feature_instance", slots=[_listed(*stats)]
    )
    assert await _card(client, tenant, instance) == [("uses", 2), ("damage", 8)]
    assert await _card(client, tenant, fireball) == [("damage", 8)]
    await delete_tenant(tenant)


async def test_a_group_a_slot_shows_comes_in_the_entrys_order_without_what_it_leaves_out(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant,
        damage=StatValueType.INT,
        range_=StatValueType.INT,
        cost=StatValueType.INT,
        flashy=StatValueType.BOOL,
        school=StatValueType.TEXT,
    )
    fireball = await _feature(client, tenant, "Fireball")
    for name, value in (("damage", 8), ("range_", 150), ("cost", 3)):
        await _stat_on(tenant, fireball, sheet[name], value)
    await _stat_on(tenant, fireball, sheet["flashy"], True)
    async with admin_session_factory() as session:
        group = await session.scalar(select(StatGroup.id).where(StatGroup.tenant_id == tenant))
    await _template(
        client,
        tenant,
        "Group card",
        required_kind="feature",
        slots=[
            {
                "kind": "stats",
                "stat_group_id": str(group),
                "exclude": [str(sheet["cost"])],
            }
        ],
    )
    card = await _card(client, tenant, fireball)
    # A tag is not on a card, and what the slot leaves out is not either.
    assert sorted(card) == [("damage", 8), ("range_", 150)]
    await delete_tenant(tenant)


async def test_the_first_template_by_name_that_says_stats_decides_and_four_show_at_most(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    names = {f"s{i}": StatValueType.INT for i in range(6)}
    sheet = await _sheet(tenant, **names)
    fireball = await _feature(client, tenant, "Fireball")
    for i in range(6):
        await _stat_on(tenant, fireball, sheet[f"s{i}"], i)
    every = [(sheet[f"s{i}"], None) for i in range(6)]
    # "A" has no stats slot, "B" and "C" do, and "B" is first by name; one for another kind is not.
    await _template(
        client,
        tenant,
        "A",
        required_kind="feature",
        slots=[{"kind": "information", "information_type": "note"}],
    )
    await _template(client, tenant, "C", required_kind="feature", slots=[_listed(every[0])])
    await _template(client, tenant, "B", required_kind="feature", slots=[_listed(*every)])
    await _template(client, tenant, "0 being", required_kind="being", slots=[_listed(every[1])])
    card = await _card(client, tenant, fireball)
    assert card == [("s0", 0), ("s1", 1), ("s2", 2), ("s3", 3)]
    await delete_tenant(tenant)


async def test_the_card_of_any_other_kind_is_what_it_was(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant = await make_tenant(test_user_id)
    sheet = await _sheet(tenant, weight=StatValueType.INT, damage=StatValueType.INT)
    made = await client.post(
        f"/tenants/{tenant}/entities", json={"name": "Longsword", "kinds": ["item"]}
    )
    assert made.status_code == 201, made.text
    sword = uuid.UUID(made.json()["id"])
    await _stat_on(tenant, sword, sheet["weight"], 3)
    await _stat_on(tenant, sword, sheet["damage"], 8)
    before = await _card(client, tenant, sword)
    assert before == [("damage", 8), ("weight", 3)]
    # A template for items does not change what an item's card is.
    await _template(
        client, tenant, "Item card", required_kind="item", slots=[_listed((sheet["weight"], None))]
    )
    assert await _card(client, tenant, sword) == before
    await delete_tenant(tenant)
