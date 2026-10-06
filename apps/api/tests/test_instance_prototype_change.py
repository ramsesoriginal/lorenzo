"""A GM changes what an instance is (RFC 0035, ADR 0192): its prototype link
is replaced, the name stays, the holders are told on the change feed, and
once by a summary notification that collapses over a short window.
"""

import uuid

from _admin_db import admin_session_factory
from httpx import AsyncClient, Response
from sqlalchemy import select
from test_change_feed import World, _feed, _instance, world  # noqa: F401

from lorenzo_api.models import Entity, EntityPrototype, Item


async def _item(w: World, name: str) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=w.tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=w.tenant_id))
        await session.commit()
        return entity.id


async def _unsorted(w: World, name: str) -> tuple[uuid.UUID, uuid.UUID]:
    """An instance of a placeholder item, owned by Bob, and that item."""
    placeholder = await _item(w, f"Unsorted item {uuid.uuid4().hex[:6]}")
    instance = await _instance(w, name=name, owner=w.bob_char)
    async with admin_session_factory() as session:
        session.add(
            EntityPrototype(entity_id=instance, prototype_id=placeholder, tenant_id=w.tenant_id)
        )
        await session.commit()
    return instance, placeholder


async def _sorted_notifications(raw_client: AsyncClient, headers: dict[str, str]) -> list[dict]:
    response = await raw_client.get("/me/notifications", headers=headers, params={"size": 100})
    assert response.status_code == 200, response.text
    return [n for n in response.json()["items"] if n["type"] == "items_sorted"]


async def test_a_gm_sorts_an_instance_and_the_name_stays(
    raw_client: AsyncClient,
    world: World,  # noqa: F811
) -> None:
    instance, placeholder = await _unsorted(world, "Hydra Zahn")
    tooth = await _item(world, "Hydra Tooth")

    response = await raw_client.patch(
        f"{world.base}/{instance}", headers=world.gary, json={"prototype_id": str(tooth)}
    )

    assert response.status_code == 200, response.text
    made = response.json()
    assert made["prototype_ids"] == [str(tooth)]
    assert made["title"] == "Hydra Zahn"
    assert placeholder != tooth
    async with admin_session_factory() as session:
        links = (
            await session.scalars(
                select(EntityPrototype.prototype_id).where(EntityPrototype.entity_id == instance)
            )
        ).all()
    assert links == [tooth]


async def test_the_holder_is_told_on_the_feed_and_once_by_a_notification(
    raw_client: AsyncClient,
    world: World,  # noqa: F811
) -> None:
    tooth = await _item(world, "Hydra Tooth")
    sorted_ones = [(await _unsorted(world, name))[0] for name in ("Hydra Zahn", "Kugel", "Amulett")]

    await raw_client.patch(
        f"{world.base}/{sorted_ones[0]}", headers=world.gary, json={"prototype_id": str(tooth)}
    )
    first = await _sorted_notifications(raw_client, world.bob)
    assert [n["title"] for n in first] == ["1 of your items has been sorted"]

    for instance in sorted_ones[1:]:
        done = await raw_client.patch(
            f"{world.base}/{instance}", headers=world.gary, json={"prototype_id": str(tooth)}
        )
        assert done.status_code == 200, done.text

    feed = [row for row in await _feed(raw_client, world.bob) if row["kind"] == "sorted"]
    assert sorted((row["entity_name"], row["detail"]) for row in feed) == [
        ("Amulett", "prototype=Hydra Tooth"),
        ("Hydra Zahn", "prototype=Hydra Tooth"),
        ("Kugel", "prototype=Hydra Tooth"),
    ]
    summary = await _sorted_notifications(raw_client, world.bob)
    assert [n["title"] for n in summary] == ["3 of your items have been sorted"]
    assert [n["id"] for n in summary] == [n["id"] for n in first]
    assert await _sorted_notifications(raw_client, world.alice) == []


async def test_only_a_gm_may_change_what_an_instance_is(
    raw_client: AsyncClient,
    world: World,  # noqa: F811
) -> None:
    instance, _ = await _unsorted(world, "Hydra Zahn")
    tooth = await _item(world, "Hydra Tooth")

    own = await raw_client.patch(
        f"{world.base}/{instance}", headers=world.bob, json={"prototype_id": str(tooth)}
    )
    other = await raw_client.patch(
        f"{world.base}/{instance}", headers=world.alice, json={"prototype_id": str(tooth)}
    )

    assert own.status_code == 403, own.text
    assert other.status_code in (403, 404), other.text
    assert await _sorted_notifications(raw_client, world.bob) == []


async def test_the_new_prototype_must_be_a_base_item_and_the_same_one_changes_nothing(
    raw_client: AsyncClient,
    world: World,  # noqa: F811
) -> None:
    instance, placeholder = await _unsorted(world, "Hydra Zahn")

    unknown = await raw_client.patch(
        f"{world.base}/{instance}", headers=world.gary, json={"prototype_id": str(uuid.uuid4())}
    )
    null = await raw_client.patch(
        f"{world.base}/{instance}", headers=world.gary, json={"prototype_id": None}
    )
    same = await raw_client.patch(
        f"{world.base}/{instance}", headers=world.gary, json={"prototype_id": str(placeholder)}
    )

    assert unknown.status_code == null.status_code == 422
    assert unknown.json()["type"] == "invalid-item-prototype"
    assert same.status_code == 200
    assert [row for row in await _feed(raw_client, world.bob) if row["kind"] == "sorted"] == []


async def test_instances_are_listed_by_their_prototype(
    raw_client: AsyncClient,
    world: World,  # noqa: F811
) -> None:
    first, placeholder = await _unsorted(world, "Hydra Zahn")
    second = await _instance(world, name="Kugel", owner=world.bob_char)
    async with admin_session_factory() as session:
        session.add(
            EntityPrototype(entity_id=second, prototype_id=placeholder, tenant_id=world.tenant_id)
        )
        await session.commit()
    other, _ = await _unsorted(world, "Amulett")

    response = await raw_client.get(
        world.base, headers=world.gary, params={"prototype_id": str(placeholder), "size": 100}
    )

    assert response.status_code == 200, response.text
    ids = {row["entity_id"] for row in response.json()["items"]}
    assert ids == {str(first), str(second)}
    assert str(other) not in ids


async def test_a_player_reads_a_note_they_wrote_once_they_tell_their_character(
    raw_client: AsyncClient,
    world: World,  # noqa: F811
) -> None:
    """No API change is needed for a placeholder's note (ADR 0192): a new
    note is private to the GM's reach, and its author may tell their own
    character about it (ADR 0101's edit gate), which is what clients do."""
    instance = await _instance(world, name="Hydra Zahn", owner=world.bob_char)
    url = f"/tenants/{world.tenant_id}/entities/{instance}/information"
    made = await raw_client.post(
        url,
        headers=world.bob,
        json={"title": "Details", "type": "note", "content": "Weight: 1 lb", "locale": "en-US"},
    )
    assert made.status_code == 201, made.text

    def titles(response: Response) -> list[str]:
        return [row["title"] for row in response.json()["items"]]

    assert titles(await raw_client.get(url, headers=world.bob)) == []
    assert titles(await raw_client.get(url, headers=world.gary)) == ["Details"]

    told = await raw_client.put(
        f"/tenants/{world.tenant_id}/information/{made.json()['id']}/knowers/{world.bob_char}",
        headers=world.bob,
    )

    assert told.status_code == 200, told.text
    assert titles(await raw_client.get(url, headers=world.bob)) == ["Details"]
    assert titles(await raw_client.get(url, headers=world.alice)) == []
