"""The player-facing change feed - see ADR 0099.

Alice and Bob are plain players (no tenant membership, no GM grant), each
controlling one character; Gary is their campaign's GM with no tenant
membership. All three act and read with genuine verified tokens
(`raw_client`), since the feed's reads rely on `app.user_id` and its writes on
per-request tenant context.
"""

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from conftest import delete_tenant, make_campaign, make_character
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.db import async_session_factory
from lorenzo_api.models import (
    CampaignGm,
    CharacterPlayer,
    Containment,
    Entity,
    EntityChange,
    Item,
    ItemInstance,
    Ownership,
    Player,
    Tenant,
    User,
)


@dataclass
class World:
    tenant_id: uuid.UUID
    alice: dict[str, str]
    bob: dict[str, str]
    gary: dict[str, str]
    alice_id: uuid.UUID
    bob_id: uuid.UUID
    gary_id: uuid.UUID
    alice_char: uuid.UUID
    bob_char: uuid.UUID
    prototype_id: uuid.UUID
    user_ids: list[uuid.UUID] = field(default_factory=list)

    @property
    def base(self) -> str:
        return f"/tenants/{self.tenant_id}/item-instances"


async def _user(raw_client: AsyncClient, jwks: FakeJwksServer) -> tuple[dict[str, str], uuid.UUID]:
    token = jwks.issue_token(f"authgear|feed-{uuid.uuid4()}")
    headers = {"Authorization": f"Bearer {token}"}
    me = await raw_client.get("/me", headers=headers)
    assert me.status_code == 200
    return headers, uuid.UUID(me.json()["id"])


@pytest.fixture
async def world(raw_client: AsyncClient, fake_jwks_server: FakeJwksServer) -> AsyncGenerator[World]:
    alice, alice_id = await _user(raw_client, fake_jwks_server)
    bob, bob_id = await _user(raw_client, fake_jwks_server)
    gary, gary_id = await _user(raw_client, fake_jwks_server)
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        await session.flush()
        tenant_id = tenant.id
        campaign = await make_campaign(session, tenant_id=tenant_id)
        characters = []
        for user_id in (alice_id, bob_id):
            player = Player(user_id=user_id, campaign_id=campaign.id, tenant_id=tenant_id)
            session.add(player)
            await session.flush()
            character = await make_character(
                session, tenant_id=tenant_id, owner_player_id=player.id
            )
            session.add(
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player.id,
                    tenant_id=tenant_id,
                )
            )
            characters.append(character.entity_id)
        session.add(CampaignGm(user_id=gary_id, campaign_id=campaign.id, tenant_id=tenant_id))
        proto = Entity(tenant_id=tenant_id, name="Sword")
        session.add(proto)
        await session.flush()
        session.add(Item(entity_id=proto.id, tenant_id=tenant_id))
        await session.commit()
        prototype_id = proto.id
    w = World(
        tenant_id=tenant_id,
        alice=alice,
        bob=bob,
        gary=gary,
        alice_id=alice_id,
        bob_id=bob_id,
        gary_id=gary_id,
        alice_char=characters[0],
        bob_char=characters[1],
        prototype_id=prototype_id,
        user_ids=[alice_id, bob_id, gary_id],
    )
    yield w
    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        for user_id in w.user_ids:
            user = await session.get(User, user_id)
            if user is not None:
                await session.delete(user)
        await session.commit()


async def _instance(
    w: World,
    *,
    name: str = "Ashfang",
    owner: uuid.UUID | None = None,
    container: uuid.UUID | None = None,
    quantity: int = 1,
) -> uuid.UUID:
    """Seeded directly, so seeding itself records nothing."""
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=w.tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=w.tenant_id))
        if owner is not None:
            session.add(
                Ownership(
                    owned_entity_id=entity.id, owner_character_id=owner, tenant_id=w.tenant_id
                )
            )
        if container is not None:
            session.add(
                Containment(
                    child_entity_id=entity.id,
                    parent_entity_id=container,
                    tenant_id=w.tenant_id,
                    quantity=quantity,
                )
            )
        await session.commit()
        return entity.id


async def _room(w: World, name: str = "Room") -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=w.tenant_id, name=name)
        session.add(entity)
        await session.commit()
        return entity.id


async def _feed(raw_client: AsyncClient, headers: dict[str, str], **params: str) -> list[dict]:
    response = await raw_client.get("/me/changes", headers=headers, params={"size": 100, **params})
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


def _summary(rows: list[dict]) -> list[tuple[str, str]]:
    return sorted((row["kind"], row["entity_name"]) for row in rows)


# --- holders, kinds, and who sees the actor ----------------------------------


async def test_a_player_giving_an_item_names_them_and_skips_their_own_feed(
    raw_client: AsyncClient, world: World
) -> None:
    sword = await _instance(world, owner=world.alice_char)

    response = await raw_client.put(
        f"{world.base}/{sword}/owner",
        headers=world.alice,
        json={"owner_character_id": str(world.bob_char)},
    )
    assert response.status_code == 200, response.text

    (row,) = await _feed(raw_client, world.bob)
    assert (row["kind"], row["entity_name"]) == ("received", "Ashfang")
    assert row["character_entity_id"] == str(world.bob_char)
    assert row["actor_user_id"] == str(world.alice_id)  # another player: named
    assert await _feed(raw_client, world.alice) == []  # nobody is told what they just did


async def test_a_gm_confiscation_says_what_happened_but_not_who(
    raw_client: AsyncClient, world: World
) -> None:
    sword = await _instance(world, owner=world.bob_char)

    response = await raw_client.delete(f"{world.base}/{sword}/owner", headers=world.gary)
    assert response.status_code == 200, response.text

    (row,) = await _feed(raw_client, world.bob)
    assert row["kind"] == "given_away"
    assert row["actor_user_id"] is None  # a GM is never named


async def test_carried_items_count_including_inside_an_owned_container(
    raw_client: AsyncClient, world: World
) -> None:
    """A sword with no owner, put in a bag Alice owns that is lying in a
    room, is still Alice's - and taking it out again is "given_away"."""
    room = await _room(world)
    bag = await _instance(world, name="Bag", owner=world.alice_char, container=room)
    sword = await _instance(world, container=room)

    into = await raw_client.put(
        f"{world.base}/{sword}/container",
        headers=world.gary,
        json={"container_entity_id": str(bag)},
    )
    assert into.status_code == 200, into.text
    out = await raw_client.put(
        f"{world.base}/{sword}/container",
        headers=world.gary,
        json={"container_entity_id": str(room)},
    )
    assert out.status_code == 200, out.text

    assert _summary(await _feed(raw_client, world.alice)) == [
        ("given_away", "Ashfang"),
        ("received", "Ashfang"),
    ]


async def test_moving_within_your_own_stuff_is_moved_and_moving_a_bag_lists_only_the_bag(
    raw_client: AsyncClient, world: World
) -> None:
    pack = await _instance(world, name="Pack", owner=world.alice_char)
    bag = await _instance(world, name="Bag", owner=world.alice_char)
    await _instance(world, name="Coin", container=bag, quantity=20)

    response = await raw_client.put(
        f"{world.base}/{bag}/container",
        headers=world.gary,
        json={"container_entity_id": str(pack)},
    )
    assert response.status_code == 200, response.text

    # Only the bag - not the 20 coins inside it - and "moved", since Alice
    # held it before and after.
    assert _summary(await _feed(raw_client, world.alice)) == [("moved", "Bag")]


async def test_rename_split_merge_and_delete_are_told_to_the_holder(
    raw_client: AsyncClient, world: World
) -> None:
    room = await _room(world)
    stack = await _instance(world, name="Arrows", owner=world.bob_char, container=room, quantity=10)

    rename = await raw_client.patch(
        f"{world.base}/{stack}", headers=world.gary, json={"name": "Silver Arrows"}
    )
    assert rename.status_code == 200, rename.text
    same_name = await raw_client.patch(
        f"{world.base}/{stack}", headers=world.gary, json={"name": "Silver Arrows"}
    )
    assert same_name.status_code == 200  # no change, no row

    split = await raw_client.post(
        f"{world.base}/{stack}/split", headers=world.gary, json={"quantity": 3}
    )
    assert split.status_code == 201, split.text
    piece = split.json()["entity_id"]

    merge = await raw_client.post(
        f"{world.base}/{piece}/merge", headers=world.gary, json={"into_entity_id": str(stack)}
    )
    assert merge.status_code == 200, merge.text

    delete = await raw_client.delete(f"{world.base}/{stack}", headers=world.gary)
    assert delete.status_code == 204, delete.text

    rows = await _feed(raw_client, world.bob)
    assert _summary(rows) == [
        ("deleted", "Silver Arrows"),
        ("merged", "Silver Arrows"),
        ("renamed", "Silver Arrows"),
        ("split", "Silver Arrows"),
    ]
    assert {row["detail"] for row in rows if row["kind"] in ("split", "merged")} == {"quantity=3"}


async def test_splitting_to_another_character_is_given_away_and_received(
    raw_client: AsyncClient, world: World
) -> None:
    room = await _room(world)
    stack = await _instance(
        world, name="Potions", owner=world.alice_char, container=room, quantity=4
    )

    response = await raw_client.post(
        f"{world.base}/{stack}/split",
        headers=world.gary,
        json={"quantity": 1, "owner_character_id": str(world.bob_char)},
    )
    assert response.status_code == 201, response.text

    assert _summary(await _feed(raw_client, world.alice)) == [("given_away", "Potions")]
    assert _summary(await _feed(raw_client, world.bob)) == [("received", "Potions")]


async def test_bulk_assign_writes_one_row_per_item_and_repeats_write_nothing(
    raw_client: AsyncClient, world: World
) -> None:
    first = await _instance(world, name="Ring")
    second = await _instance(world, name="Amulet")
    body = [
        {"entity_id": str(first), "owner_character_id": str(world.bob_char)},
        {"entity_id": str(second), "owner_character_id": str(world.bob_char)},
        {"entity_id": str(uuid.uuid4()), "owner_character_id": str(world.bob_char)},
    ]

    assert (
        await raw_client.post(f"{world.base}/bulk-assign", headers=world.gary, json=body)
    ).status_code == 200
    assert _summary(await _feed(raw_client, world.bob)) == [
        ("received", "Amulet"),
        ("received", "Ring"),
    ]

    # Same assignment again changes nothing, so records nothing.
    assert (
        await raw_client.post(f"{world.base}/bulk-assign", headers=world.gary, json=body)
    ).status_code == 200
    assert len(await _feed(raw_client, world.bob)) == 2


async def test_bulk_move_records_each_moved_item(raw_client: AsyncClient, world: World) -> None:
    room = await _room(world)
    bag = await _instance(world, name="Bag", owner=world.alice_char)
    first = await _instance(world, name="Gem", container=room)
    second = await _instance(world, name="Key", container=room)

    response = await raw_client.post(
        f"{world.base}/bulk-move",
        headers=world.gary,
        json={"to_container_entity_id": str(bag), "from_container_entity_id": str(room)},
    )
    assert response.status_code == 200, response.text

    assert _summary(await _feed(raw_client, world.alice)) == [
        ("received", "Gem"),
        ("received", "Key"),
    ]
    assert first != second


async def test_creating_an_instance_into_someones_hands_is_received(
    raw_client: AsyncClient, world: World
) -> None:
    response = await raw_client.post(
        world.base,
        headers=world.gary,
        json={"prototype_id": str(world.prototype_id), "owner_character_id": str(world.bob_char)},
    )
    assert response.status_code == 201, response.text

    assert _summary(await _feed(raw_client, world.bob)) == [("received", "Sword")]


# --- reading: since, retention, and who can read ------------------------------


async def test_since_is_inclusive_and_old_rows_are_pruned_on_read(
    raw_client: AsyncClient, world: World
) -> None:
    now = datetime.now(tz=UTC)
    async with admin_session_factory() as session:
        for days_ago, name in ((1, "Recent"), (100, "Ancient")):
            session.add(
                EntityChange(
                    id=uuid.uuid4(),
                    tenant_id=world.tenant_id,
                    user_id=world.bob_id,
                    character_entity_id=world.bob_char,
                    entity_id=uuid.uuid4(),
                    kind="received",
                    entity_name=name,
                    detail=None,
                    actor_user_id=None,
                    actor_visible=False,
                    occurred_at=now - timedelta(days=days_ago),
                )
            )
        await session.commit()
    boundary = (now - timedelta(days=1)).isoformat()

    assert [r["entity_name"] for r in await _feed(raw_client, world.bob, since=boundary)] == [
        "Recent"
    ]
    assert [r["entity_name"] for r in await _feed(raw_client, world.bob)] == ["Recent"]
    async with admin_session_factory() as session:
        names = (
            await session.execute(
                select(EntityChange.entity_name).where(EntityChange.user_id == world.bob_id)
            )
        ).scalars()
        assert set(names) == {"Recent"}  # the 100-day-old row was deleted


async def test_rows_are_readable_only_by_their_recipient(
    raw_client: AsyncClient, world: World
) -> None:
    sword = await _instance(world, owner=world.alice_char)
    await raw_client.put(
        f"{world.base}/{sword}/owner",
        headers=world.alice,
        json={"owner_character_id": str(world.bob_char)},
    )

    async def visible(**settings: str) -> int:
        async with async_session_factory() as session:
            for name, value in settings.items():
                await session.execute(
                    text("SELECT set_config(:n, :v, true)"),
                    {"n": name.replace("__", "."), "v": value},
                )
            return len((await session.execute(select(EntityChange.id))).scalars().all())

    assert await visible(app__user_id=str(world.bob_id)) == 1
    # Holding the tenant context is not enough - stricter than notification.
    assert await visible(app__tenant_id=str(world.tenant_id)) == 0
    assert await visible(app__user_id=str(world.alice_id), app__tenant_id=str(world.tenant_id)) == 0
    assert await visible() == 0
