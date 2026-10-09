"""Making an entry with kinds, adding and removing a kind, and the guarded delete (ADR 0217, slice
K2 of RFC 0041), through the real HTTP API."""

import uuid
from datetime import datetime
from typing import Any

from _admin_db import admin_session_factory
from conftest import (
    delete_tenant,
    make_being,
    make_campaign,
    make_character,
    make_plain_participant,
    make_tenant,
)
from httpx import AsyncClient, Response
from sqlalchemy import select

from lorenzo_api.etag import etag_for
from lorenzo_api.models import (
    AuditLog,
    Being,
    Entity,
    EntityPrototype,
    EntitySlug,
    Item,
    ItemInstance,
)


def _url(tenant_id: uuid.UUID, *rest: object) -> str:
    return "/".join([f"/tenants/{tenant_id}/entities", *(str(r) for r in rest)])


async def _create(client: AsyncClient, tenant_id: uuid.UUID, **body: Any) -> Response:
    return await client.post(_url(tenant_id), json={"name": "Entry", **body})


async def _made(client: AsyncClient, tenant_id: uuid.UUID, **body: Any) -> uuid.UUID:
    response = await _create(client, tenant_id, **body)
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["id"])


async def _rows(model: Any, entity_id: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return len((await session.scalars(select(model).where(model.entity_id == entity_id))).all())


async def _activity(tenant_id: uuid.UUID, prefix: str = "entity.") -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like(f"{prefix}%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(action, detail) for action, detail in rows]


async def _inventory_item(tenant_id: uuid.UUID, catalog: uuid.UUID) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=tenant_id, name="My Thing")
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        session.add(EntityPrototype(entity_id=entity.id, prototype_id=catalog, tenant_id=tenant_id))
        await session.commit()
        return entity.id


# --- POST /entities --------------------------------------------------------------------------


async def test_a_bare_entry_is_made_with_a_link_name_and_says_what_it_is(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    response = await _create(client, tenant_id, name="Weapons", slug="weapons")

    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["name"], body["slug"], body["kinds"], body["prototypes"]) == (
        "Weapons",
        "weapons",
        [],
        [],
    )
    assert response.headers["location"].endswith(_url(tenant_id, body["id"]))
    assert response.headers["etag"] == etag_for(datetime.fromisoformat(body["updated_at"]))
    resolved = await client.get(_url(tenant_id, "resolve"), params={"slug": "weapons"})
    assert [(r["entity_id"], r["kinds"]) for r in resolved.json()] == [(body["id"], [])]
    assert await _activity(tenant_id) == [("entity.created", "kinds=none,parents=0")]
    await delete_tenant(tenant_id)


async def test_an_entry_can_be_an_item_a_being_or_both(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    item = await _made(client, tenant_id, name="Sword", kinds=["item"])
    being = await _made(client, tenant_id, name="Orc", kinds=["being"])
    sentient = await _made(client, tenant_id, name="Ashfang", kinds=["being", "item", "item"])

    for entity_id, kinds in ((item, ["item"]), (being, ["being"]), (sentient, ["item", "being"])):
        detail = await client.get(_url(tenant_id, entity_id))
        assert detail.json()["kinds"] == kinds
    items = [
        row["entity_id"]
        for row in (await client.get(f"/tenants/{tenant_id}/items")).json()["items"]
    ]
    beings = [
        row["entity_id"]
        for row in (await client.get(f"/tenants/{tenant_id}/beings")).json()["items"]
    ]
    assert sorted(items) == sorted([str(item), str(sentient)])
    assert sorted(beings) == sorted([str(being), str(sentient)])
    assert await _activity(tenant_id, "entity.created") == [
        ("entity.created", "kinds=item,parents=0"),
        ("entity.created", "kinds=being,parents=0"),
        ("entity.created", "kinds=being+item,parents=0"),
    ]
    await delete_tenant(tenant_id)


async def test_an_entry_is_made_with_its_parents(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    race = await _made(client, tenant_id, name="Orc", kinds=["being"])
    category = await _made(client, tenant_id, name="Monsters")

    grunt = await _create(
        client, tenant_id, name="Grunt", kinds=["being"], parents=[str(race), str(category)]
    )
    assert grunt.status_code == 201
    assert {p["id"] for p in grunt.json()["prototypes"]} == {str(race), str(category)}
    group = await _create(client, tenant_id, name="Warband", parents=[str(category)])
    assert [p["id"] for p in group.json()["prototypes"]] == [str(category)]
    await delete_tenant(tenant_id)


async def test_a_parent_that_is_not_an_entry_of_the_library_is_a_422_and_makes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    elsewhere = await _made(client, tenant_b, name="Elsewhere")

    for parent in (uuid.uuid4(), elsewhere):
        response = await _create(client, tenant_a, name="Child", parents=[str(parent)])
        assert response.status_code == 422
    assert (await client.get(_url(tenant_a))).json()["total"] == 0
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_a_taken_link_name_is_a_409_and_makes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    await _made(client, tenant_id, name="One", slug="taken", kinds=["item"])

    response = await _create(client, tenant_id, name="Two", slug="taken", kinds=["being"])
    assert response.status_code == 409
    assert (await client.get(_url(tenant_id))).json()["total"] == 1
    await delete_tenant(tenant_id)


async def test_in_public_catalog_is_only_for_an_item(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    assert (
        await _create(client, tenant_id, kinds=["being"], in_public_catalog=True)
    ).status_code == 422
    assert (await _create(client, tenant_id, in_public_catalog=False)).status_code == 422

    public = await _made(client, tenant_id, name="Torch", kinds=["item"], in_public_catalog=True)
    private = await _made(client, tenant_id, name="Secret", kinds=["item"])
    async with admin_session_factory() as session:
        assert (await session.get_one(Item, public)).in_public_catalog is True
        assert (await session.get_one(Item, private)).in_public_catalog is False
    await delete_tenant(tenant_id)


async def test_an_inventory_item_or_a_character_is_not_made_here(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    for kind in ("character", "item_instance", "place"):
        assert (await _create(client, tenant_id, kinds=[kind])).status_code == 422
    await delete_tenant(tenant_id)


async def test_only_a_member_makes_an_entry(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    await make_plain_participant(tenant_id, test_user_id)

    assert (await _create(client, tenant_id)).status_code in (403, 404)
    async with admin_session_factory() as session:
        assert (await session.scalars(select(Entity.id).where(Entity.tenant_id == tenant_id))).all()
    await delete_tenant(tenant_id)


async def test_what_is_made_in_one_library_is_not_in_another(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    await _made(client, tenant_a, name="Only Here", kinds=["being"])

    assert (await client.get(_url(tenant_b))).json()["total"] == 0
    assert (await client.get(f"/tenants/{tenant_b}/beings")).json()["total"] == 0
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_an_entry_says_its_kinds_whatever_made_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id, name="Hero")
        npc = await make_being(session, tenant_id=tenant_id, name="Hound")
        await session.commit()
    catalog = await _made(client, tenant_id, name="Dagger", kinds=["item"])
    mine = await _inventory_item(tenant_id, catalog)

    for entity_id, kinds in (
        (character.entity_id, ["being", "character"]),
        (npc.entity_id, ["being"]),
        (mine, ["item_instance"]),
    ):
        assert (await client.get(_url(tenant_id, entity_id))).json()["kinds"] == kinds
    await delete_tenant(tenant_id)


# --- PUT and DELETE /entities/{id}/kinds/{kind} ----------------------------------------------


async def test_a_kind_is_added_once_and_the_second_time_changes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sword = await _made(client, tenant_id, name="Sword", kinds=["item"])
    before = (await client.get(_url(tenant_id, sword))).headers["etag"]

    first = await client.put(_url(tenant_id, sword, "kinds", "being"))
    assert first.status_code == 201, first.text
    assert first.json()["kinds"] == ["item", "being"]
    assert first.headers["etag"] != before
    second = await client.put(_url(tenant_id, sword, "kinds", "being"))
    assert second.status_code == 200
    assert second.headers["etag"] == first.headers["etag"]
    assert await _rows(Being, sword) == 1
    assert await _activity(tenant_id, "entity.kind") == [("entity.kind_added", "kind=being")]
    async with admin_session_factory() as session:
        assert (await session.get_one(Entity, sword)).updated_by == test_user_id
    beings = (await client.get(f"/tenants/{tenant_id}/beings")).json()["items"]
    assert [row["entity_id"] for row in beings] == [str(sword)]
    await delete_tenant(tenant_id)


async def test_a_bare_entry_takes_item_with_its_own_column(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    node = await _made(client, tenant_id, name="Node")

    made = await client.put(
        _url(tenant_id, node, "kinds", "item"), json={"in_public_catalog": True}
    )
    assert made.status_code == 201
    async with admin_session_factory() as session:
        assert (await session.get_one(Item, node)).in_public_catalog is True
    # The same kind again with another value for its column sets it: a PUT says what it is.
    again = await client.put(
        _url(tenant_id, node, "kinds", "item"), json={"in_public_catalog": False}
    )
    assert again.status_code == 200
    async with admin_session_factory() as session:
        assert (await session.get_one(Item, node)).in_public_catalog is False
    assert [a for a, _ in await _activity(tenant_id, "entity.kind")] == [
        "entity.kind_added",
        "entity.kind_added",
    ]
    await delete_tenant(tenant_id)


async def test_a_column_the_kind_does_not_have_is_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    node = await _made(client, tenant_id, name="Node")

    refused = await client.put(
        _url(tenant_id, node, "kinds", "being"), json={"in_public_catalog": True}
    )
    assert refused.status_code == 422
    assert await _rows(Being, node) == 0
    await delete_tenant(tenant_id)


async def test_only_item_and_being_are_kinds_a_route_changes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    node = await _made(client, tenant_id, name="Node")
    for kind in ("character", "item_instance", "place"):
        assert (await client.put(_url(tenant_id, node, "kinds", kind))).status_code == 422
        assert (await client.delete(_url(tenant_id, node, "kinds", kind))).status_code == 422
    await delete_tenant(tenant_id)


async def test_an_inventory_item_may_take_being_and_never_item(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    catalog = await _made(client, tenant_id, name="Summoning Stone", kinds=["item"])
    mine = await _inventory_item(tenant_id, catalog)

    refused = await client.put(_url(tenant_id, mine, "kinds", "item"))
    assert refused.status_code == 409
    assert await _rows(Item, mine) == 0
    taken = await client.put(_url(tenant_id, mine, "kinds", "being"))
    assert taken.status_code == 201
    assert taken.json()["kinds"] == ["item_instance", "being"]
    await delete_tenant(tenant_id)


async def test_if_match_guards_a_kind_change(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    node = await _made(client, tenant_id, name="Node")
    etag = (await client.get(_url(tenant_id, node))).headers["etag"]

    stale = await client.put(
        _url(tenant_id, node, "kinds", "being"), headers={"If-Match": 'W/"stale"'}
    )
    assert stale.status_code == 412
    assert await _rows(Being, node) == 0
    added = await client.put(_url(tenant_id, node, "kinds", "being"), headers={"If-Match": etag})
    assert added.status_code == 201
    # The old token no longer matches, for the removal either.
    assert (
        await client.delete(_url(tenant_id, node, "kinds", "being"), headers={"If-Match": etag})
    ).status_code == 412
    removed = await client.delete(
        _url(tenant_id, node, "kinds", "being"), headers={"If-Match": added.headers["etag"]}
    )
    assert removed.status_code == 200
    await delete_tenant(tenant_id)


async def test_a_kind_change_of_an_unknown_entry_or_another_librarys_is_a_404(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    elsewhere = await _made(client, tenant_b, name="Elsewhere")

    for entity_id in (uuid.uuid4(), elsewhere):
        assert (await client.put(_url(tenant_a, entity_id, "kinds", "being"))).status_code == 404
        assert (await client.delete(_url(tenant_a, entity_id, "kinds", "being"))).status_code == 404
    assert await _rows(Being, elsewhere) == 0
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_a_kind_is_removed_and_the_entry_survives(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sentient = await _made(client, tenant_id, name="Ashfang", kinds=["item", "being"])

    removed = await client.delete(_url(tenant_id, sentient, "kinds", "being"))
    assert removed.status_code == 200
    assert removed.json()["kinds"] == ["item"]
    assert await _rows(Being, sentient) == 0 and await _rows(Item, sentient) == 1
    # Not having it is nothing to do, and nothing to log.
    again = await client.delete(_url(tenant_id, sentient, "kinds", "being"))
    assert again.status_code == 200
    assert again.headers["etag"] == removed.headers["etag"]
    assert await _activity(tenant_id, "entity.kind") == [("entity.kind_removed", "kind=being")]
    last = await client.delete(_url(tenant_id, sentient, "kinds", "item"))
    assert last.json()["kinds"] == []
    assert (await client.get(_url(tenant_id, sentient))).status_code == 200
    await delete_tenant(tenant_id)


async def test_item_stays_while_an_inventory_item_inherits_from_the_entry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    catalog = await _made(client, tenant_id, name="Dagger", kinds=["item"])
    mine = await _inventory_item(tenant_id, catalog)

    refused = await client.delete(_url(tenant_id, catalog, "kinds", "item"))
    assert refused.status_code == 409
    assert await _rows(Item, catalog) == 1
    assert (await client.delete(f"/tenants/{tenant_id}/item-instances/{mine}")).status_code == 204
    assert (await client.delete(_url(tenant_id, catalog, "kinds", "item"))).status_code == 200
    assert await _rows(Item, catalog) == 0
    await delete_tenant(tenant_id)


async def test_being_stays_while_the_entry_is_a_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id, name="Hero")
        await session.commit()
    hero = character.entity_id

    refused = await client.delete(_url(tenant_id, hero, "kinds", "being"))
    assert refused.status_code == 409
    assert "demote" in refused.json()["detail"]
    assert await _rows(Being, hero) == 1
    assert (await client.delete(f"/tenants/{tenant_id}/characters/{hero}")).status_code == 204
    assert (await client.delete(_url(tenant_id, hero, "kinds", "being"))).status_code == 200
    assert await _rows(Being, hero) == 0
    await delete_tenant(tenant_id)


async def test_only_a_member_changes_a_kind(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    node = await _made(client, tenant_id, name="Node", kinds=["item"])
    await make_plain_participant(tenant_id, test_user_id)

    assert (await client.put(_url(tenant_id, node, "kinds", "being"))).status_code in (403, 404)
    assert (await client.delete(_url(tenant_id, node, "kinds", "item"))).status_code in (403, 404)
    assert await _rows(Being, node) == 0 and await _rows(Item, node) == 1
    await delete_tenant(tenant_id)


# --- DELETE /entities/{id} -------------------------------------------------------------------


async def test_every_kind_of_entry_that_may_go_goes(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    entries = {
        kinds: await _made(
            client, tenant_id, name="-".join(kinds) or "bare", kinds=list(kinds), slug=f"s-{i}"
        )
        for i, kinds in enumerate([(), ("item",), ("being",), ("item", "being")])
    }
    for kinds, entity_id in entries.items():
        assert (await client.delete(_url(tenant_id, entity_id))).status_code == 204, kinds
        assert (await client.get(_url(tenant_id, entity_id))).status_code == 404
        for model in (Item, Being, EntitySlug):
            assert await _rows(model, entity_id) == 0
    assert (await client.get(_url(tenant_id))).json()["total"] == 0
    assert [d for _, d in await _activity(tenant_id, "entity.deleted")] == [
        "kinds=none",
        "kinds=item",
        "kinds=being",
        "kinds=being+item",
    ]
    await delete_tenant(tenant_id)


async def test_deleting_an_entry_leaves_its_parents_and_children(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    race = await _made(client, tenant_id, name="Orc", kinds=["being"])
    grunt = await _made(client, tenant_id, name="Grunt", kinds=["being"], parents=[str(race)])

    assert (await client.delete(_url(tenant_id, race))).status_code == 204
    detail = (await client.get(_url(tenant_id, grunt))).json()
    assert detail["prototypes"] == [] and detail["kinds"] == ["being"]
    await delete_tenant(tenant_id)


async def test_an_inventory_item_a_character_and_a_campaigns_entry_are_not_deleted_here(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        character = await make_character(session, tenant_id=tenant_id, name="Hero")
        campaign = await make_campaign(session, tenant_id=tenant_id)
        await session.commit()
        campaign_entity = campaign.entity_id
    catalog = await _made(client, tenant_id, name="Dagger", kinds=["item"])
    mine = await _inventory_item(tenant_id, catalog)

    for entity_id in (mine, character.entity_id, campaign_entity, catalog):
        response = await client.delete(_url(tenant_id, entity_id))
        assert response.status_code == 409, (entity_id, response.text)
        assert (await client.get(_url(tenant_id, entity_id))).status_code == 200
    assert (await client.delete(f"/tenants/{tenant_id}/item-instances/{mine}")).status_code == 204
    assert (await client.delete(_url(tenant_id, catalog))).status_code == 204
    await delete_tenant(tenant_id)


async def test_the_kind_specific_deletes_still_delete_the_whole_entry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    sentient = await _made(client, tenant_id, name="Ashfang", kinds=["item", "being"])

    assert (await client.delete(f"/tenants/{tenant_id}/items/{sentient}")).status_code == 204
    assert (await client.get(_url(tenant_id, sentient))).status_code == 404
    assert await _rows(Being, sentient) == 0
    await delete_tenant(tenant_id)


async def test_a_delete_honours_if_match_and_stays_inside_its_library(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    other = await make_tenant(test_user_id)
    node = await _made(client, tenant_id, name="Node")
    etag = (await client.get(_url(tenant_id, node))).headers["etag"]

    stale = await client.delete(_url(tenant_id, node), headers={"If-Match": 'W/"x"'})
    assert stale.status_code == 412
    assert (await client.delete(_url(other, node))).status_code == 404
    assert (await client.delete(_url(tenant_id, uuid.uuid4()))).status_code == 404
    assert await _rows_entity(node) == 1
    assert (
        await client.delete(_url(tenant_id, node), headers={"If-Match": etag})
    ).status_code == 204
    assert await _rows_entity(node) == 0
    await delete_tenant(tenant_id)
    await delete_tenant(other)


async def test_only_a_member_deletes_an_entry(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    tenant_id = await make_tenant(test_user_id)
    node = await _made(client, tenant_id, name="Node")
    await make_plain_participant(tenant_id, test_user_id)

    assert (await client.delete(_url(tenant_id, node))).status_code in (403, 404)
    assert await _rows_entity(node) == 1
    await delete_tenant(tenant_id)


async def _rows_entity(entity_id: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return len((await session.scalars(select(Entity.id).where(Entity.id == entity_id))).all())
