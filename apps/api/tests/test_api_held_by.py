"""GET .../item-instances/held-by/{entity_id} - ADR 0123."""

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_campaign, make_character, make_tenant
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import (
    CharacterPlayer,
    Containment,
    Entity,
    ItemInstance,
    Membership,
    MembershipRole,
    Ownership,
    Player,
    User,
)


async def _instance(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    name: str,
    *,
    owner: uuid.UUID | None = None,
    container: uuid.UUID | None = None,
) -> uuid.UUID:
    entity = Entity(tenant_id=tenant_id, name=name)
    session.add(entity)
    await session.flush()
    session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
    if owner is not None:
        session.add(
            Ownership(owned_entity_id=entity.id, owner_character_id=owner, tenant_id=tenant_id)
        )
    if container is not None:
        session.add(
            Containment(child_entity_id=entity.id, parent_entity_id=container, tenant_id=tenant_id)
        )
    await session.flush()
    return entity.id


async def _character(
    session: AsyncSession,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    user_id: uuid.UUID,
    name: str,
) -> uuid.UUID:
    player = Player(user_id=user_id, campaign_id=campaign_id, tenant_id=tenant_id)
    session.add(player)
    await session.flush()
    character = await make_character(
        session, tenant_id=tenant_id, name=name, owner_player_id=player.id
    )
    session.add(
        CharacterPlayer(
            character_entity_id=character.entity_id, player_id=player.id, tenant_id=tenant_id
        )
    )
    await session.flush()
    return character.entity_id


@dataclass
class _Scene:
    tenant_id: uuid.UUID
    other_user_ids: list[uuid.UUID]
    ids: dict[str, uuid.UUID]


async def _make_scene(test_user_id: uuid.UUID) -> _Scene:
    """Alice (the caller's character) and Pia (another player's, same
    campaign). Alice has a Sword in hand, a Rope that's in no container, and
    a Backpack holding Pia's Potion and a Belt pouch with a Coin in it. Her
    Satchel, with a Letter in it, is in no container either, so it's with
    her too. Pia has Alice's Spellbook in hand, and Alice's Ring is in Pia's
    Case, which is in no container. Alice's Carriage stands in the Stable,
    with an unowned Chest in it and an unowned Map in the Chest.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        pia_user = User(authgear_subject_id=f"pia-{uuid.uuid4()}")
        session.add(pia_user)
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        pia = await _character(session, tenant_id, campaign.id, pia_user.id, "Pia")

        stable = Entity(tenant_id=tenant_id, name="Stable")
        session.add(stable)
        await session.flush()

        ids = {"alice": alice, "pia": pia, "stable": stable.id}
        ids["sword"] = await _instance(session, tenant_id, "Sword", owner=alice, container=alice)
        ids["rope"] = await _instance(session, tenant_id, "Rope", owner=alice)
        ids["backpack"] = await _instance(
            session, tenant_id, "Backpack", owner=alice, container=alice
        )
        ids["potion"] = await _instance(
            session, tenant_id, "Potion", owner=pia, container=ids["backpack"]
        )
        ids["pouch"] = await _instance(
            session, tenant_id, "Belt pouch", owner=alice, container=ids["backpack"]
        )
        ids["coin"] = await _instance(
            session, tenant_id, "Coin", owner=alice, container=ids["pouch"]
        )
        ids["spellbook"] = await _instance(
            session, tenant_id, "Spellbook", owner=alice, container=pia
        )
        ids["satchel"] = await _instance(session, tenant_id, "Satchel", owner=alice)
        ids["letter"] = await _instance(
            session, tenant_id, "Letter", owner=alice, container=ids["satchel"]
        )
        ids["case"] = await _instance(session, tenant_id, "Case", owner=pia)
        ids["ring"] = await _instance(
            session, tenant_id, "Ring", owner=alice, container=ids["case"]
        )
        ids["carriage"] = await _instance(
            session, tenant_id, "Carriage", owner=alice, container=stable.id
        )
        ids["chest"] = await _instance(session, tenant_id, "Chest", container=ids["carriage"])
        ids["map"] = await _instance(session, tenant_id, "Map", container=ids["chest"])
        await session.commit()
    return _Scene(tenant_id=tenant_id, other_user_ids=[pia_user.id], ids=ids)


async def _tear_down(scene: _Scene) -> None:
    await delete_tenant(scene.tenant_id)
    async with admin_session_factory() as session:
        for user_id in scene.other_user_ids:
            await session.delete(await session.get_one(User, user_id))
        await session.commit()


def _group_shape(group: dict[str, object], names: dict[str, str]) -> tuple[object, ...]:
    """A group as (container, kind, path, carried, items), by fixture name."""
    container = group["container"]
    path = group["path"]
    items = group["item_instances"]
    assert isinstance(container, dict)
    assert isinstance(path, list)
    assert isinstance(items, list)
    return (
        names[container["id"]],
        group["container_kind"],
        [names[p["id"]] for p in path],
        group["carried"],
        sorted(names[i["entity_id"]] for i in items),
    )


async def test_held_by_groups_what_a_being_holds(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _make_scene(test_user_id)
    names = {str(v): k for k, v in scene.ids.items()}

    response = await client.get(
        f"/tenants/{scene.tenant_id}/item-instances/held-by/{scene.ids['alice']}"
    )

    assert response.status_code == 200
    body = response.json()
    assert [_group_shape(g, names) for g in body["groups"]] == [
        # Equipped: what Alice has in hand, and what she owns in no container.
        ("alice", "being", [], True, ["backpack", "rope", "satchel", "sword"]),
        # Carried, in tree order: the pouch right after the backpack it's in.
        # The satchel is in no container, so it's with Alice.
        ("backpack", "item_instance", [], True, ["potion", "pouch"]),
        ("pouch", "item_instance", ["backpack"], True, ["coin"]),
        ("satchel", "item_instance", [], True, ["letter"]),
        # Held elsewhere: in another being's hands, in what's with her, and
        # through what Alice owns.
        ("pia", "being", [], False, ["spellbook"]),
        ("case", "item_instance", ["pia"], False, ["ring"]),
        ("stable", "other", [], False, ["carriage"]),
        ("carriage", "item_instance", ["stable"], False, ["chest"]),
        ("chest", "item_instance", ["carriage", "stable"], False, ["map"]),
    ]
    assert [names[o["id"]] for o in body["owners"]] == ["alice", "pia"]

    await _tear_down(scene)


async def test_held_by_equipped_is_there_even_when_empty(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/item-instances/held-by/{alice}")

    assert response.status_code == 200
    assert response.json() == {
        "groups": [
            {
                "container": {"id": str(alice), "name": "Alice", "quantity": None},
                "container_kind": "being",
                "path": [],
                "carried": True,
                "item_instances": [],
            }
        ],
        "owners": [],
    }

    await delete_tenant(tenant_id)


async def test_held_by_404_for_a_holder_out_of_reach_or_unknown(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0123: an unreachable holder answers like one that doesn't exist.
    Bob plays in another campaign the caller has no standing in."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Bob's campaign")
        await session.flush()
        bob_user = User(authgear_subject_id=f"bob-{uuid.uuid4()}")
        session.add(bob_user)
        await session.flush()
        bob = await _character(session, tenant_id, campaign.id, bob_user.id, "Bob")
        await session.commit()

    unreachable = await client.get(f"/tenants/{tenant_id}/item-instances/held-by/{bob}")
    unknown = await client.get(f"/tenants/{tenant_id}/item-instances/held-by/{uuid.uuid4()}")

    assert unreachable.status_code == 404
    assert unknown.status_code == 404

    # ORGA reaches everyone (ADR 0040).
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        membership.role = MembershipRole.ORGA
        await session.commit()
    as_orga = await client.get(f"/tenants/{tenant_id}/item-instances/held-by/{bob}")
    assert as_orga.status_code == 200

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user.id))
        await session.commit()


async def test_held_by_hides_what_belongs_to_someone_out_of_reach(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0040's filter applies. Alice carries a Familiar in her Backpack,
    so the caller reaches it; the Acorn it owns, in no container, isn't
    anything the caller reaches."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        backpack = await _instance(session, tenant_id, "Backpack", owner=alice, container=alice)
        familiar = (await make_being(session, tenant_id=tenant_id, name="Familiar")).entity_id
        session.add(
            Containment(child_entity_id=familiar, parent_entity_id=backpack, tenant_id=tenant_id)
        )
        await _instance(session, tenant_id, "Acorn", owner=familiar)
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/item-instances/held-by/{familiar}")

    assert response.status_code == 200
    body = response.json()
    assert [g["container"]["id"] for g in body["groups"]] == [str(familiar)]
    assert body["groups"][0]["item_instances"] == []
    assert body["owners"] == []

    await delete_tenant(tenant_id)


async def test_held_by_survives_a_containment_cycle(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0016 allows cycles: Alice's Box is inside a Crate that's inside
    the Box. Each path stops before repeating itself."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        box = await _instance(session, tenant_id, "Box", owner=alice)
        crate = await _instance(session, tenant_id, "Crate", container=box)
        session.add(Containment(child_entity_id=box, parent_entity_id=crate, tenant_id=tenant_id))
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/item-instances/held-by/{alice}")

    assert response.status_code == 200
    groups = {g["container"]["name"]: g for g in response.json()["groups"]}
    assert set(groups) == {"Alice", "Box", "Crate"}
    assert [p["name"] for p in groups["Box"]["path"]] == ["Crate"]
    assert [p["name"] for p in groups["Crate"]["path"]] == ["Box"]
    assert not groups["Box"]["carried"]

    await delete_tenant(tenant_id)
