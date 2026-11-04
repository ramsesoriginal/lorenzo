"""ADR 0387: the effective value of some stats on a page of entries, in one read."""

import uuid

from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_api_computed_stats import MODIFIER_FORMULA, _entity, _put, _sheet
from test_api_contents_formulas import _packed

from lorenzo_api.models import StatValueType

NAMES = ("strength", "strength_modifier", "speed")


async def _library(client: AsyncClient, test_user_id: uuid.UUID):  # noqa: ANN202
    """Fighter (holds a modifier formula and a speed), under it Weak and Strong, each with a
    strength of its own; and a separate Rock with nothing."""
    tenant_id = await make_tenant(test_user_id)
    sheet = await _sheet(
        tenant_id,
        strength=StatValueType.INT,
        strength_modifier=StatValueType.INT,
        speed=StatValueType.INT,
        reach=StatValueType.INT,
    )
    fighter = await _entity(tenant_id, "Fighter", item=True, stats={sheet["speed"]: 30})
    await _put(
        client,
        sheet.formula_url(fighter, "strength_modifier"),
        {**MODIFIER_FORMULA, "source_stat_definition_id": str(sheet["strength"])},
    )
    weak = await _entity(
        tenant_id, "Weak", prototype=fighter, item=True, stats={sheet["strength"]: 9}
    )
    strong = await _entity(
        tenant_id,
        "Strong",
        prototype=fighter,
        item=True,
        stats={sheet["strength"]: 18, sheet["speed"]: 35},
    )
    rock = await _entity(tenant_id, "Rock")
    return tenant_id, sheet, {"fighter": fighter, "weak": weak, "strong": strong, "rock": rock}


def _params(*stats: uuid.UUID, **query: object) -> list[tuple[str, object]]:
    return [("stat_definition_id", str(s)) for s in stats] + list(query.items())


async def _read(client: AsyncClient, tenant_id: uuid.UUID, *stats: uuid.UUID, **query: object):  # noqa: ANN202
    response = await client.get(
        f"/tenants/{tenant_id}/entities/effective-stats", params=_params(*stats, **query)
    )
    assert response.status_code == 200, response.text
    return response.json()


async def test_a_page_says_value_ownership_source_and_formula_for_each_stat(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, e = await _library(client, test_user_id)
    page = await _read(
        client, tenant_id, sheet["speed"], sheet["strength_modifier"], sheet["reach"]
    )

    rows = {row["name"]: row["stats"] for row in page["items"]}
    assert [row["name"] for row in page["items"]] == ["Fighter", "Rock", "Strong", "Weak"]
    assert (page["total"], page["page"]) == (4, 1)
    speed, modifier = str(sheet["speed"]), str(sheet["strength_modifier"])

    # Strong holds its own speed; Weak inherits Fighter's; Rock has none; nobody has reach.
    strong = {s["stat_definition_id"]: s for s in rows["Strong"]}
    assert (strong[speed]["value"], strong[speed]["own"], strong[speed]["from_entity"]) == (
        35,
        True,
        None,
    )
    weak = {s["stat_definition_id"]: s for s in rows["Weak"]}
    assert (weak[speed]["value"], weak[speed]["own"], weak[speed]["computed"]) == (30, False, False)
    assert weak[speed]["from_entity"]["id"] == str(e["fighter"])
    assert weak[speed]["from_entity"]["name"] == "Fighter"
    assert rows["Rock"] == []
    assert not any(s["stat_definition_id"] == str(sheet["reach"]) for r in rows.values() for s in r)
    # A formula held by Fighter is worked out against each entry's own strength (9 -> -1, 18 -> 4).
    assert (weak[modifier]["value"], weak[modifier]["computed"], weak[modifier]["own"]) == (
        -1,
        True,
        False,
    )
    assert strong[modifier]["value"] == 4
    assert [s["stat_definition_id"] for s in rows["Strong"]] == [speed, modifier]  # as asked
    await delete_tenant(tenant_id)


async def test_a_stat_reads_the_same_here_as_on_the_entrys_own_read(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, _ = await _library(client, test_user_id)
    by_id = {str(sheet[n]): n for n in NAMES}
    page = await _read(client, tenant_id, *[sheet[n] for n in NAMES])

    for row in page["items"]:
        detail = (await client.get(f"/tenants/{tenant_id}/entities/{row['id']}")).json()
        singly = {
            s["name"]: (s["value"], s["own"], s["computed"])
            for s in detail["stats"]
            if s["name"] in NAMES
        }
        here = {
            by_id[s["stat_definition_id"]]: (s["value"], s["own"], s["computed"])
            for s in row["stats"]
        }
        assert here == singly, row["name"]
    await delete_tenant(tenant_id)


async def test_the_filters_and_the_order_are_the_lists(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, e = await _library(client, test_user_id)
    base = f"/tenants/{tenant_id}/entities"

    for query in (
        {"q": "o"},
        {"kind": "item"},
        {"parent_id": str(e["fighter"])},
        {"parent_id": str(e["fighter"]), "recursive": "true"},
        {"q": "ng", "kind": "item"},
    ):
        listed = (await client.get(base, params=query)).json()["items"]
        read = await _read(client, tenant_id, sheet["speed"], **query)
        assert [row["id"] for row in read["items"]] == [row["id"] for row in listed], query
    unknown = await client.get(
        f"{base}/effective-stats",
        params=_params(sheet["speed"], parent_id=str(uuid.uuid4())),
    )
    assert unknown.status_code == 404
    await delete_tenant(tenant_id)


async def test_it_is_paged(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id, sheet, _ = await _library(client, test_user_id)
    url = f"/tenants/{tenant_id}/entities/effective-stats"

    first = await _read(client, tenant_id, sheet["speed"], size=3)
    second = await _read(client, tenant_id, sheet["speed"], size=3, page=2)
    too_big = await client.get(url, params=_params(sheet["speed"], size=101))

    assert [len(first["items"]), len(second["items"]), first["pages"], first["total"]] == [
        3,
        1,
        2,
        4,
    ]
    assert [r["name"] for r in first["items"] + second["items"]] == [
        "Fighter",
        "Rock",
        "Strong",
        "Weak",
    ]
    assert too_big.status_code == 422
    await delete_tenant(tenant_id)


async def test_the_stats_asked_for_are_checked(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id, sheet, _ = await _library(client, test_user_id)
    other = await make_tenant(test_user_id)
    other_sheet = await _sheet(other, speed=StatValueType.INT)
    url = f"/tenants/{tenant_id}/entities/effective-stats"

    none = await client.get(url)
    unknown = await client.get(url, params=_params(uuid.uuid4()))
    foreign = await client.get(url, params=_params(other_sheet["speed"]))
    many = await client.get(url, params=_params(*[uuid.uuid4() for _ in range(51)]))
    twice = await _read(client, tenant_id, sheet["speed"], sheet["speed"])

    assert none.status_code == 422
    assert unknown.status_code == 404 and foreign.status_code == 404
    assert many.status_code == 422
    assert all(len(r["stats"]) <= 1 for r in twice["items"])  # asked twice, answered once
    await delete_tenant(tenant_id)
    await delete_tenant(other)


async def test_a_contents_formula_adds_up_what_is_inside_as_on_the_entrys_own_read(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    packed = await _packed(client, test_user_id)
    t, ids = packed.tenant_id, packed.ids
    weight, carried = ids["stat:weight"], ids["stat:carried_weight"]

    page = await _read(client, t, weight, carried, size=100)

    rows = {
        row["name"]: {s["stat_definition_id"]: s for s in row["stats"]} for row in page["items"]
    }
    # The recipe adds up what is inside (ADR 0127): the Backpack 2 + 25, the Pouch 1 + 3, a
    # catalog Crate 10 + 3, and what Hero carries in hand is the Backpack and all.
    assert rows["Backpack"][str(weight)]["value"] == 27
    assert rows["Pouch"][str(weight)]["value"] == 4
    assert rows["Crate"][str(weight)]["value"] == 13
    assert rows["Hero"][str(carried)]["value"] == 27
    assert rows["Backpack"][str(weight)]["computed"] is True
    assert str(weight) not in rows["Torch"]  # an unweighed torch has no weight of its own
    for row in page["items"]:
        singly = {
            s["name"]: s["value"]
            for s in (await client.get(f"/tenants/{t}/entities/{row['id']}")).json()["stats"]
        }
        here = {s["stat_definition_id"]: s["value"] for s in row["stats"]}
        assert here.get(str(weight)) == singly.get("weight"), row["name"]
        assert here.get(str(carried)) == singly.get("carried_weight"), row["name"]
    await delete_tenant(t)
