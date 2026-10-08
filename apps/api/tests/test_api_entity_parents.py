"""PUT /entities/{id}/parents: any entry's own parents, replaced as a set (ADR 0216, slice K3 of
RFC 0041)."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup, make_actor
from conftest import delete_tenant, make_being, make_character, make_plain_participant, make_tenant
from httpx import AsyncClient, Response
from sqlalchemy import select

from lorenzo_api.etag import etag_for
from lorenzo_api.models import (
    AuditLog,
    Entity,
    EntityPrototype,
    Item,
    ItemInstance,
    StatDefinition,
    StatGroup,
    StatValueType,
)


async def _entry(tenant_id: uuid.UUID, name: str, kind: str | None = None) -> uuid.UUID:
    """A bare entry, or one with the marker row of `kind` (item, being, character, instance)."""
    async with admin_session_factory() as session:
        if kind == "being":
            being = await make_being(session, tenant_id=tenant_id, name=name)
            await session.commit()
            return being.entity_id
        if kind == "character":
            character = await make_character(session, tenant_id=tenant_id, name=name)
            await session.commit()
            return character.entity_id
        entity = Entity(tenant_id=tenant_id, name=name)
        session.add(entity)
        await session.flush()
        if kind == "item":
            session.add(Item(entity_id=entity.id, tenant_id=tenant_id))
        if kind == "instance":
            session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
        await session.commit()
        return entity.id


async def _parents_in_db(tenant_id: uuid.UUID, entity_id: uuid.UUID) -> set[uuid.UUID]:
    async with admin_session_factory() as session:
        return set(
            (
                await session.scalars(
                    select(EntityPrototype.prototype_id).where(
                        EntityPrototype.entity_id == entity_id,
                        EntityPrototype.tenant_id == tenant_id,
                    )
                )
            ).all()
        )


async def _put(
    client: AsyncClient,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    parents: Sequence[uuid.UUID],
    **headers: str,
) -> Response:
    return await client.put(
        f"/tenants/{tenant_id}/entities/{entity_id}/parents",
        json={"parent_ids": [str(p) for p in parents]},
        headers=headers,
    )


async def test_any_kind_of_entry_can_be_given_parents(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    race = await _entry(tenant_id, "Orc", "being")
    category = await _entry(tenant_id, "Weapons")

    for kind in (None, "item", "being", "character"):
        entry = await _entry(tenant_id, f"Entry {kind}", kind)
        response = await _put(client, tenant_id, entry, [race, category])
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["id"] == str(entry)
        assert {parent["id"] for parent in body["prototypes"]} == {str(race), str(category)}
        assert await _parents_in_db(tenant_id, entry) == {race, category}
    await delete_tenant(tenant_id)


async def test_a_put_replaces_the_set_and_an_empty_list_clears_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    one = await _entry(tenant_id, "One")
    two = await _entry(tenant_id, "Two")
    three = await _entry(tenant_id, "Three")
    being = await _entry(tenant_id, "Hound", "being")

    await _put(client, tenant_id, being, [one, two])
    response = await _put(client, tenant_id, being, [two, three])
    assert {p["id"] for p in response.json()["prototypes"]} == {str(two), str(three)}
    assert await _parents_in_db(tenant_id, being) == {two, three}

    response = await _put(client, tenant_id, being, [])
    assert response.status_code == 200
    assert response.json()["prototypes"] == []
    assert await _parents_in_db(tenant_id, being) == set()
    await delete_tenant(tenant_id)


async def test_a_duplicate_id_in_the_list_is_one_parent(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    parent = await _entry(tenant_id, "Parent")
    child = await _entry(tenant_id, "Child", "being")

    response = await _put(client, tenant_id, child, [parent, parent])
    assert response.status_code == 200
    assert await _parents_in_db(tenant_id, child) == {parent}
    await delete_tenant(tenant_id)


async def test_the_item_route_and_the_generic_one_write_the_same_parents(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    weapon = await _entry(tenant_id, "Weapon")
    sword = await _entry(tenant_id, "Sword", "item")

    via_item = await client.put(
        f"/tenants/{tenant_id}/items/{sword}/prototypes", json={"prototype_ids": [str(weapon)]}
    )
    assert via_item.status_code == 200
    detail = await client.get(f"/tenants/{tenant_id}/entities/{sword}")
    assert [p["id"] for p in detail.json()["prototypes"]] == [str(weapon)]

    cleared = await _put(client, tenant_id, sword, [])
    assert cleared.status_code == 200
    assert (await client.get(f"/tenants/{tenant_id}/items/{sword}")).json()["prototype_ids"] == []
    await delete_tenant(tenant_id)


async def test_an_unknown_entry_is_a_404_and_so_is_one_of_another_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    parent = await _entry(tenant_a, "Parent")
    elsewhere = await _entry(tenant_b, "Elsewhere", "being")

    assert (await _put(client, tenant_a, uuid.uuid4(), [parent])).status_code == 404
    assert (await _put(client, tenant_a, elsewhere, [parent])).status_code == 404
    assert await _parents_in_db(tenant_b, elsewhere) == set()
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_a_parent_that_is_unknown_or_in_another_tenant_is_a_422_and_changes_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_a = await make_tenant(test_user_id)
    tenant_b = await make_tenant(test_user_id)
    keep = await _entry(tenant_a, "Keep")
    elsewhere = await _entry(tenant_b, "Elsewhere")
    being = await _entry(tenant_a, "Hound", "being")
    await _put(client, tenant_a, being, [keep])

    for bad in (uuid.uuid4(), elsewhere):
        response = await _put(client, tenant_a, being, [keep, bad])
        assert response.status_code == 422
    assert await _parents_in_db(tenant_a, being) == {keep}
    await delete_tenant(tenant_a)
    await delete_tenant(tenant_b)


async def test_an_entry_cannot_be_its_own_parent_or_close_a_loop(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    race = await _entry(tenant_id, "Orc", "being")
    grunt = await _entry(tenant_id, "Grunt", "being")
    chief = await _entry(tenant_id, "Chief")
    assert (await _put(client, tenant_id, grunt, [race])).status_code == 200
    assert (await _put(client, tenant_id, chief, [grunt])).status_code == 200

    assert (await _put(client, tenant_id, race, [race])).status_code == 422
    # race -> chief -> grunt -> race
    assert (await _put(client, tenant_id, race, [chief])).status_code == 422
    assert await _parents_in_db(tenant_id, race) == set()
    # The refused write did not leave the others half-changed either.
    assert await _parents_in_db(tenant_id, grunt) == {race}
    await delete_tenant(tenant_id)


async def test_an_inventory_item_keeps_its_own_parent_route(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    catalog = await _entry(tenant_id, "Dagger", "item")
    other = await _entry(tenant_id, "Other")
    mine = await _entry(tenant_id, "My Dagger", "instance")
    async with admin_session_factory() as session:
        session.add(EntityPrototype(entity_id=mine, prototype_id=catalog, tenant_id=tenant_id))
        await session.commit()

    response = await _put(client, tenant_id, mine, [other])
    assert response.status_code == 409
    assert "inventory item" in response.json()["detail"]
    assert await _parents_in_db(tenant_id, mine) == {catalog}
    await delete_tenant(tenant_id)


async def test_a_being_inherits_stats_through_its_new_parents(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=tenant_id, name="body")
        session.add(group)
        await session.flush()
        stat = StatDefinition(
            tenant_id=tenant_id, stat_group_id=group.id, name="hp", value_type=StatValueType.INT
        )
        session.add(stat)
        await session.commit()
        stat_id = stat.id
    race = await _entry(tenant_id, "Orc", "being")
    other_race = await _entry(tenant_id, "Elf", "being")
    grunt = await _entry(tenant_id, "Grunt", "being")
    for parent, hp in ((race, 30), (other_race, 12)):
        response = await client.put(
            f"/tenants/{tenant_id}/entities/{parent}/stats/{stat_id}", json={"value": hp}
        )
        assert response.status_code == 200, response.text

    async def stats() -> list[dict[str, object]]:
        detail = await client.get(f"/tenants/{tenant_id}/entities/{grunt}")
        return detail.json()["stats"]  # type: ignore[no-any-return]

    assert await stats() == []
    await _put(client, tenant_id, grunt, [race])
    assert await stats() == [{"name": "hp", "value": 30, "own": False}]
    await _put(client, tenant_id, grunt, [other_race])
    assert await stats() == [{"name": "hp", "value": 12, "own": False}]
    await _put(client, tenant_id, grunt, [])
    assert await stats() == []
    await delete_tenant(tenant_id)


async def test_a_value_the_entry_holds_itself_stays_when_parents_change(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        group = StatGroup(tenant_id=tenant_id, name="body")
        session.add(group)
        await session.flush()
        stat = StatDefinition(
            tenant_id=tenant_id, stat_group_id=group.id, name="hp", value_type=StatValueType.INT
        )
        session.add(stat)
        await session.commit()
        stat_id = stat.id
    race = await _entry(tenant_id, "Orc", "being")
    grunt = await _entry(tenant_id, "Grunt", "being")
    await client.put(f"/tenants/{tenant_id}/entities/{race}/stats/{stat_id}", json={"value": 30})
    await client.put(f"/tenants/{tenant_id}/entities/{grunt}/stats/{stat_id}", json={"value": 99})

    await _put(client, tenant_id, grunt, [race])
    await _put(client, tenant_id, grunt, [])
    detail = await client.get(f"/tenants/{tenant_id}/entities/{grunt}")
    assert detail.json()["stats"] == [{"name": "hp", "value": 99, "own": True}]
    await delete_tenant(tenant_id)


async def test_if_match_guards_the_write_and_the_response_carries_the_new_etag(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    parent = await _entry(tenant_id, "Parent")
    being = await _entry(tenant_id, "Hound", "being")

    read = await client.get(f"/tenants/{tenant_id}/entities/{being}")
    etag = read.headers["etag"]
    assert etag == etag_for(datetime.fromisoformat(read.json()["updated_at"]))

    stale = await _put(client, tenant_id, being, [parent], **{"If-Match": 'W/"stale"'})
    assert stale.status_code == 412
    assert await _parents_in_db(tenant_id, being) == set()

    written = await _put(client, tenant_id, being, [parent], **{"If-Match": etag})
    assert written.status_code == 200
    assert written.headers["etag"] != etag
    reread = await client.get(f"/tenants/{tenant_id}/entities/{being}")
    assert reread.headers["etag"] == written.headers["etag"]
    # The old token no longer matches.
    again = await _put(client, tenant_id, being, [], **{"If-Match": etag})
    assert again.status_code == 412
    await delete_tenant(tenant_id)


async def test_a_change_touches_the_entry_and_is_one_activity_entry(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    one = await _entry(tenant_id, "One")
    two = await _entry(tenant_id, "Two")
    being = await _entry(tenant_id, "Hound", "being")
    before = (await client.get(f"/tenants/{tenant_id}/entities/{being}")).headers["etag"]

    response = await _put(client, tenant_id, being, [one, two])
    assert response.status_code == 200

    async with admin_session_factory() as session:
        entity = await session.get_one(Entity, being)
        assert entity.updated_by == test_user_id
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.target_type, AuditLog.target_id, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action.like("entity.%"))
                .order_by(AuditLog.created_at)
            )
        ).all()
    assert response.headers["etag"] != before
    assert [tuple(row) for row in rows] == [
        ("entity.parents_replaced", "entity", being, "parents=2")
    ]
    await delete_tenant(tenant_id)


async def test_putting_the_same_set_again_changes_and_logs_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    one = await _entry(tenant_id, "One")
    being = await _entry(tenant_id, "Hound", "being")
    first = await _put(client, tenant_id, being, [one])

    second = await _put(client, tenant_id, being, [one])
    assert second.status_code == 200
    assert second.headers["etag"] == first.headers["etag"]
    async with admin_session_factory() as session:
        count = len(
            (
                await session.scalars(
                    select(AuditLog.id).where(
                        AuditLog.tenant_id == tenant_id,
                        AuditLog.action == "entity.parents_replaced",
                    )
                )
            ).all()
        )
    assert count == 1
    await delete_tenant(tenant_id)


async def test_only_a_member_of_the_library_may_write_parents(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    parent = await _entry(tenant_id, "Parent")
    being = await _entry(tenant_id, "Hound", "being")
    await make_plain_participant(tenant_id, test_user_id)

    response = await _put(client, tenant_id, being, [parent])
    assert response.status_code in (403, 404)
    assert await _parents_in_db(tenant_id, being) == set()
    await delete_tenant(tenant_id)


async def test_a_new_parent_on_a_being_reaches_a_library_as_an_update(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The copy engine carries parents for every entry (RFC 0041 §3): nothing beyond the route."""
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    repository = await author.create_tenant("Bestiary", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        race = await _entry(repository, "Orc", "being")
        grunt = await _entry(repository, "Grunt", "being")
        assert (await author.put(f"/tenants/{repository}/subscribers/{table}")).status_code == 201
        assert (await author.put(f"/tenants/{repository}/published")).status_code == 200
        copied = await gm.post(f"/tenants/{table}/repositories/{repository}/copy")
        assert copied.status_code == 201, copied.text
        url = f"/tenants/{table}/repositories/{repository}/updates"
        assert (await gm.get(url)).json()["changed"] == []

        written = await author.put(
            f"/tenants/{repository}/entities/{grunt}/parents", json={"parent_ids": [str(race)]}
        )
        assert written.status_code == 200, written.text

        changed = (await gm.get(url)).json()["changed"]
        assert [row["name"] for row in changed] == ["Grunt"]
        (field,) = [f for f in changed[0]["fields"] if f["field"] == "prototypes"]
        assert field["added"] == [str(race)]
    finally:
        await cleanup([table, repository], [author, gm])
