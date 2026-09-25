"""Handing an item over on give, and a stack leaving a container into its
owner - see ADR 0115. Alice keeps a backpack with a stack of three arrows and
a book in it; the campaign's GM (the test user) gives them to Bob, and sees
both inventories (ADR 0040).
"""

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_player, make_tenant
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import (
    AuditLog,
    CampaignGm,
    CharacterPlayer,
    Containment,
    Entity,
    EntityPrototype,
    Item,
    ItemInstance,
    Ownership,
    User,
)


@dataclass
class World:
    tenant_id: uuid.UUID
    alice: uuid.UUID
    bob: uuid.UUID
    backpack: uuid.UUID
    arrows: uuid.UUID
    book: uuid.UUID
    user_ids: list[uuid.UUID]

    @property
    def base(self) -> str:
        return f"/tenants/{self.tenant_id}/item-instances"


async def _world(test_user_id: uuid.UUID) -> World:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id)
        session.add(CampaignGm(user_id=test_user_id, campaign_id=campaign.id, tenant_id=tenant_id))
        characters = []
        for name in ("Alice", "Bob"):
            player = await make_player(session, tenant_id=tenant_id, campaign_id=campaign.id)
            character = await make_character(
                session, tenant_id=tenant_id, name=name, owner_player_id=player.id
            )
            session.add(
                CharacterPlayer(
                    character_entity_id=character.entity_id,
                    player_id=player.id,
                    tenant_id=tenant_id,
                )
            )
            characters.append((character.entity_id, player.user_id))
        alice = characters[0][0]

        async def instance(
            name: str, *, container: uuid.UUID | None, quantity: int = 1
        ) -> uuid.UUID:
            prototype = Entity(tenant_id=tenant_id, name=name)
            session.add(prototype)
            await session.flush()
            session.add(Item(entity_id=prototype.id, tenant_id=tenant_id))
            entity = Entity(tenant_id=tenant_id, name=name)
            session.add(entity)
            await session.flush()
            session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
            session.add(
                EntityPrototype(entity_id=entity.id, prototype_id=prototype.id, tenant_id=tenant_id)
            )
            session.add(
                Ownership(owned_entity_id=entity.id, owner_character_id=alice, tenant_id=tenant_id)
            )
            if container is not None:
                session.add(
                    Containment(
                        child_entity_id=entity.id,
                        parent_entity_id=container,
                        tenant_id=tenant_id,
                        quantity=quantity,
                    )
                )
            await session.flush()
            return entity.id

        backpack = await instance("Backpack", container=None)
        arrows = await instance("Arrow", container=backpack, quantity=3)
        book = await instance("Book", container=backpack)
        await session.commit()
    return World(
        tenant_id=tenant_id,
        alice=alice,
        bob=characters[1][0],
        backpack=backpack,
        arrows=arrows,
        book=book,
        user_ids=[user_id for _, user_id in characters],
    )


async def _clean_up(world: World) -> None:
    await delete_tenant(world.tenant_id)
    async with admin_session_factory() as session:
        for user_id in world.user_ids:
            await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def _containment(entity_id: uuid.UUID) -> tuple[uuid.UUID, int] | None:
    async with admin_session_factory() as session:
        row = await session.get(Containment, entity_id)
        return (row.parent_entity_id, row.quantity) if row is not None else None


async def _logged(tenant_id: uuid.UUID) -> list[tuple[str, str | None]]:
    async with admin_session_factory() as session:
        rows = await session.execute(
            select(AuditLog.action, AuditLog.detail)
            .where(AuditLog.tenant_id == tenant_id)
            .order_by(AuditLog.created_at)
        )
    return [(action, detail) for action, detail in rows]


async def _groups(
    client: AsyncClient, world: World, owner: uuid.UUID
) -> dict[str | None, set[str]]:
    response = await client.get(f"{world.base}/owned-by/{owner}")
    assert response.status_code == 200, response.text
    return {
        group["container"]["name"] if group["container"] else None: {
            f"{item['title']} x{item['quantity']}" if item["quantity"] else item["title"]
            for item in group["item_instances"]
        }
        for group in response.json()["groups"]
    }


async def test_giving_leaves_the_container_by_default(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    response = await client.put(
        f"{world.base}/{world.arrows}/owner", json={"owner_character_id": str(world.bob)}
    )
    assert response.status_code == 200, response.text
    # ADR 0051, unchanged: Bob's now, still in Alice's backpack.
    assert response.json()["container_entity_id"] == str(world.backpack)
    assert await _containment(world.arrows) == (world.backpack, 3)
    await _clean_up(world)


async def test_handing_over_moves_a_stack_into_its_new_owner_whole(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    response = await client.put(
        f"{world.base}/{world.arrows}/owner",
        json={"owner_character_id": str(world.bob), "move_to_owner": True},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["owner_entity_id"], body["container_entity_id"], body["quantity"]) == (
        str(world.bob),
        str(world.bob),
        3,
    )
    # Bob carries it, in no container of his; Alice's backpack no longer has it.
    assert await _groups(client, world, world.bob) == {None: {"Arrow x3"}}
    assert await _groups(client, world, world.alice) == {
        None: {"Backpack"},
        "Backpack": {"Book x1"},
    }
    assert await _logged(world.tenant_id) == [
        ("item_instance.owner_set", f"owner={world.bob}"),
        ("item_instance.container_set", f"container={world.bob}"),
    ]
    await _clean_up(world)


async def test_handing_over_part_of_a_stack_moves_the_part(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    response = await client.post(
        f"{world.base}/bulk-assign",
        json=[
            {
                "entity_id": str(world.arrows),
                "owner_character_id": str(world.bob),
                "quantity": 1,
                "move_to_owner": True,
            }
        ],
    )
    assert response.status_code == 200, response.text
    given = response.json()[0]["item_instance"]
    assert (given["container_entity_id"], given["quantity"]) == (str(world.bob), 1)
    assert await _containment(world.arrows) == (world.backpack, 2)
    await _clean_up(world)


async def test_bulk_handing_over_a_whole_item(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    world = await _world(test_user_id)
    response = await client.post(
        f"{world.base}/bulk-assign",
        json=[
            {
                "entity_id": str(world.book),
                "owner_character_id": str(world.bob),
                "move_to_owner": True,
            },
            {"entity_id": str(world.arrows), "owner_character_id": str(world.bob)},
        ],
    )
    assert response.status_code == 200, response.text
    assert await _containment(world.book) == (world.bob, 1)
    # Without the flag, as ever.
    assert await _containment(world.arrows) == (world.backpack, 3)
    await _clean_up(world)


async def test_a_stack_refuses_to_leave_every_container(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    response = await client.delete(f"{world.base}/{world.arrows}/container")
    assert response.status_code == 409, response.text
    assert response.json()["type"].endswith("stack-needs-container")
    assert await _containment(world.arrows) == (world.backpack, 3)

    # Into its owner is the way out, with its count.
    moved = await client.put(
        f"{world.base}/{world.arrows}/container", json={"container_entity_id": str(world.alice)}
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["quantity"] == 3
    assert await _groups(client, world, world.alice) == {
        None: {"Backpack", "Arrow x3"},
        "Backpack": {"Book x1"},
    }
    await _clean_up(world)


async def test_a_single_item_still_leaves_its_container(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    response = await client.delete(f"{world.base}/{world.book}/container")
    assert response.status_code == 200, response.text
    assert response.json()["container_entity_id"] is None
    assert await _containment(world.book) is None
    await _clean_up(world)
