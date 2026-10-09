"""GET /entities finds entries by name, kind and parent and says what kind each is; GET /items and
GET /beings list by name (ADR 0215, slice K5 of RFC 0041)."""

import uuid
from collections.abc import Sequence

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_character, make_plain_participant
from httpx import AsyncClient

from lorenzo_api.models import (
    Being,
    Entity,
    EntityPrototype,
    Item,
    ItemInstance,
    Membership,
    MembershipRole,
    Tenant,
)


async def _tenant(user_id: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        session.add(Membership(tenant_id=tenant.id, user_id=user_id, role=MembershipRole.OWNER))
        await session.commit()
        return tenant.id


async def _entries(tenant_id: uuid.UUID, *specs: tuple[str, Sequence[str]]) -> dict[str, uuid.UUID]:
    """An entry for each (name, kinds), the marker rows made directly: no route makes an entry
    with two kinds yet."""
    ids: dict[str, uuid.UUID] = {}
    async with admin_session_factory() as session:
        for name, kinds in specs:
            entity = Entity(tenant_id=tenant_id, name=name)
            session.add(entity)
            await session.flush()
            ids[name] = entity.id
            if "item" in kinds:
                session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
            if "being" in kinds:
                session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
            if "item_instance" in kinds:
                session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
    return ids


async def _parent(tenant_id: uuid.UUID, child: uuid.UUID, parent: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        session.add(EntityPrototype(tenant_id=tenant_id, entity_id=child, prototype_id=parent))
        await session.commit()


async def _names(client: AsyncClient, tenant_id: uuid.UUID, **params: object) -> list[str]:
    response = await client.get(f"/tenants/{tenant_id}/entities", params={**params, "size": 100})
    assert response.status_code == 200, response.text
    return [row["name"] for row in response.json()["items"]]


async def test_rows_say_which_kinds_an_entry_has(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    await _entries(
        tenant_id,
        ("Bare", []),
        ("Sword", ["item"]),
        ("Orc", ["being"]),
        ("Sentient Sword", ["item", "being"]),
        ("Shovel Of Mine", ["item_instance"]),
    )
    async with admin_session_factory() as session:
        await make_character(session, tenant_id=tenant_id, name="Hero")
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/entities", params={"size": 100})
    assert response.status_code == 200
    kinds = {row["name"]: row["kinds"] for row in response.json()["items"]}
    assert kinds == {
        "Bare": [],
        "Hero": ["being", "character"],
        "Orc": ["being"],
        "Sentient Sword": ["item", "being"],
        "Shovel Of Mine": ["item_instance"],
        "Sword": ["item"],
    }
    await delete_tenant(tenant_id)


async def test_the_list_stays_ordered_by_name_and_keeps_its_shape(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    await _entries(tenant_id, ("Charlie", ["item"]), ("Alpha", []), ("Bravo", ["being"]))

    response = await client.get(f"/tenants/{tenant_id}/entities", params={"page": 1, "size": 2})
    body = response.json()
    assert [row["name"] for row in body["items"]] == ["Alpha", "Bravo"]
    assert body["total"] == 3
    assert set(body["items"][0]) == {"id", "name", "quantity", "kinds", "parent_ids"}
    await delete_tenant(tenant_id)


async def test_q_is_a_case_insensitive_substring_of_the_name(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    await _entries(
        tenant_id,
        ("Silver Dagger", ["item"]),
        ("Dagger Of Speed", []),
        ("Orc", ["being"]),
        ("50% Off Coupon", []),
        ("500 Gold", []),
        ("a_b", []),
        ("axb", []),
    )

    assert await _names(client, tenant_id, q="dagger") == ["Dagger Of Speed", "Silver Dagger"]
    assert await _names(client, tenant_id, q="SILVER") == ["Silver Dagger"]
    assert await _names(client, tenant_id, q="nothing like it") == []
    # A percent sign and an underscore are letters of the name, not wildcards.
    assert await _names(client, tenant_id, q="50%") == ["50% Off Coupon"]
    assert await _names(client, tenant_id, q="a_b") == ["a_b"]
    await delete_tenant(tenant_id)


async def test_kind_matches_any_of_the_kinds_given(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    await _entries(
        tenant_id,
        ("Bare", []),
        ("Sword", ["item"]),
        ("Orc", ["being"]),
        ("Sentient Sword", ["item", "being"]),
        ("Shovel Of Mine", ["item_instance"]),
    )
    async with admin_session_factory() as session:
        await make_character(session, tenant_id=tenant_id, name="Hero")
        await session.commit()

    assert await _names(client, tenant_id, kind="item") == ["Sentient Sword", "Sword"]
    assert await _names(client, tenant_id, kind="being") == ["Hero", "Orc", "Sentient Sword"]
    assert await _names(client, tenant_id, kind="character") == ["Hero"]
    assert await _names(client, tenant_id, kind="item_instance") == ["Shovel Of Mine"]
    # Any of, so an entry that is both is listed once.
    assert await _names(client, tenant_id, kind=["item", "being"]) == [
        "Hero",
        "Orc",
        "Sentient Sword",
        "Sword",
    ]
    response = await client.get(
        f"/tenants/{tenant_id}/entities", params={"kind": ["item", "being"]}
    )
    assert response.json()["total"] == 4
    await delete_tenant(tenant_id)


async def test_an_unknown_kind_is_refused(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await _tenant(test_user_id)
    response = await client.get(f"/tenants/{tenant_id}/entities", params={"kind": "place"})
    assert response.status_code == 422
    await delete_tenant(tenant_id)


async def test_parent_id_lists_direct_children_and_recursive_every_descendant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    ids = await _entries(
        tenant_id,
        ("Weapon", []),
        ("Sword", ["item"]),
        ("Longsword", ["item"]),
        ("Race Orc", ["being"]),
        ("Grunt", ["being"]),
        ("Unrelated", []),
    )
    await _parent(tenant_id, ids["Sword"], ids["Weapon"])
    await _parent(tenant_id, ids["Longsword"], ids["Sword"])
    await _parent(tenant_id, ids["Grunt"], ids["Race Orc"])

    weapon = str(ids["Weapon"])
    assert await _names(client, tenant_id, parent_id=weapon) == ["Sword"]
    assert await _names(client, tenant_id, parent_id=weapon, recursive="true") == [
        "Longsword",
        "Sword",
    ]
    # A being is a parent like any other entry.
    assert await _names(client, tenant_id, parent_id=str(ids["Race Orc"])) == ["Grunt"]
    # recursive on its own changes nothing.
    assert len(await _names(client, tenant_id, recursive="true")) == 6
    await delete_tenant(tenant_id)


async def test_filters_combine(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await _tenant(test_user_id)
    ids = await _entries(
        tenant_id,
        ("Weapon", []),
        ("Silver Sword", ["item"]),
        ("Silver Hound", ["being"]),
        ("Iron Sword", ["item"]),
    )
    for child in ("Silver Sword", "Silver Hound", "Iron Sword"):
        await _parent(tenant_id, ids[child], ids["Weapon"])

    params = {"parent_id": str(ids["Weapon"])}
    assert await _names(client, tenant_id, **params, q="silver", kind="item") == ["Silver Sword"]
    assert await _names(client, tenant_id, **params, kind="item") == ["Iron Sword", "Silver Sword"]
    assert await _names(client, tenant_id, **params, q="hound") == ["Silver Hound"]
    await delete_tenant(tenant_id)


async def test_parent_id_of_another_tenant_or_nowhere_is_a_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await _tenant(test_user_id)
    tenant_b = await _tenant(test_user_id)
    elsewhere = (await _entries(tenant_b, ("Elsewhere", [])))["Elsewhere"]

    for parent in (elsewhere, uuid.uuid4()):
        response = await client.get(
            f"/tenants/{tenant_a}/entities", params={"parent_id": str(parent)}
        )
        assert response.status_code == 404
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_one_tenants_entries_never_appear_in_another_tenants_list(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await _tenant(test_user_id)
    tenant_b = await _tenant(test_user_id)
    await _entries(tenant_a, ("Alpha Blade", ["item"]))
    await _entries(tenant_b, ("Beta Blade", ["item"]))

    assert await _names(client, tenant_a, q="blade", kind="item") == ["Alpha Blade"]
    assert await _names(client, tenant_b, q="blade", kind="item") == ["Beta Blade"]
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_a_player_filters_the_list_as_before(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    await _entries(tenant_id, ("Sword", ["item"]), ("Orc", ["being"]))
    await make_plain_participant(tenant_id, test_user_id)

    assert await _names(client, tenant_id, kind="being") == ["Orc"]
    assert await _names(client, tenant_id, q="sw") == ["Sword"]
    await delete_tenant(tenant_id)


async def test_someone_with_no_part_in_the_tenant_cannot_filter_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.commit()
        tenant_id = tenant.id
    response = await client.get(f"/tenants/{tenant_id}/entities", params={"kind": "item"})
    assert response.status_code in (403, 404)
    await delete_tenant(tenant_id)


async def test_items_are_listed_by_name_then_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    # Made in neither alphabetical nor id order; the two "Dagger"s tie on name.
    first = await _entries(tenant_id, ("Zither", ["item"]), ("Dagger", ["item"]))
    second = await _entries(tenant_id, ("Axe", ["item"]))
    twin = (await _entries(tenant_id, ("Dagger", ["item"])))["Dagger"]

    response = await client.get(f"/tenants/{tenant_id}/items", params={"size": 100})
    assert response.status_code == 200
    rows = response.json()["items"]
    assert [row["title"] for row in rows] == ["Axe", "Dagger", "Dagger", "Zither"]
    daggers = [row["entity_id"] for row in rows if row["title"] == "Dagger"]
    assert daggers == sorted([str(first["Dagger"]), str(twin)])
    assert rows[0]["entity_id"] == str(second["Axe"])
    await delete_tenant(tenant_id)


async def test_items_stay_ordered_by_name_through_the_filters_and_pages(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    await _entries(
        tenant_id,
        ("Silver Zither", ["item"]),
        ("Silver Axe", ["item"]),
        ("Silver Mace", ["item"]),
        ("Iron Axe", ["item"]),
    )
    response = await client.get(
        f"/tenants/{tenant_id}/items", params={"q": "silver", "page": 2, "size": 2}
    )
    assert [row["title"] for row in response.json()["items"]] == ["Silver Zither"]
    response = await client.get(
        f"/tenants/{tenant_id}/items", params={"q": "silver", "page": 1, "size": 2}
    )
    assert [row["title"] for row in response.json()["items"]] == ["Silver Axe", "Silver Mace"]
    await delete_tenant(tenant_id)


async def test_beings_are_listed_by_name_then_id(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    await _entries(tenant_id, ("Zed", ["being"]), ("Orc", ["being"]))
    await _entries(tenant_id, ("Ann", ["being"]))
    twin = (await _entries(tenant_id, ("Orc", ["being"])))["Orc"]

    response = await client.get(f"/tenants/{tenant_id}/beings", params={"size": 100})
    assert response.status_code == 200
    rows = response.json()["items"]
    assert [row["name"] for row in rows] == ["Ann", "Orc", "Orc", "Zed"]
    orcs = [row["entity_id"] for row in rows if row["name"] == "Orc"]
    assert orcs == sorted(orcs)
    assert str(twin) in orcs
    await delete_tenant(tenant_id)


async def test_the_catalog_a_player_reads_is_ordered_by_name_too(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    async with admin_session_factory() as session:
        for name in ("Zither", "Axe", "Mace"):
            entity = Entity(tenant_id=tenant_id, name=name)
            session.add(entity)
            await session.flush()
            session.add(Item(entity_id=entity.id, tenant_id=tenant_id, in_public_catalog=True))
        await session.commit()
    await make_plain_participant(tenant_id, test_user_id)

    response = await client.get(f"/tenants/{tenant_id}/items", params={"size": 100})
    assert [row["title"] for row in response.json()["items"]] == ["Axe", "Mace", "Zither"]
    await delete_tenant(tenant_id)


async def test_rows_name_their_parents_so_the_tree_can_be_drawn_from_the_list(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await _tenant(test_user_id)
    made = await _entries(tenant_id, ("Root", []), ("Left", []), ("Right", []), ("Both", ["item"]))
    async with admin_session_factory() as session:
        for child, parent in (
            ("Left", "Root"),
            ("Right", "Root"),
            ("Both", "Left"),
            ("Both", "Right"),
        ):
            session.add(
                EntityPrototype(
                    entity_id=made[child], prototype_id=made[parent], tenant_id=tenant_id
                )
            )
        await session.commit()

    rows = (await client.get(f"/tenants/{tenant_id}/entities")).json()["items"]
    parents = {row["name"]: row["parent_ids"] for row in rows}
    assert parents == {
        "Root": [],
        "Left": [str(made["Root"])],
        "Right": [str(made["Root"])],
        "Both": sorted([str(made["Left"]), str(made["Right"])]),
    }
    # A filtered list names them too.
    child = (await client.get(f"/tenants/{tenant_id}/entities", params={"q": "left"})).json()
    assert child["items"][0]["parent_ids"] == [str(made["Root"])]
    await delete_tenant(tenant_id)
