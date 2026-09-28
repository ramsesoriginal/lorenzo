"""GET .../item-instances/controlled-by/{entity_id} - ADR 0130, RFC 0031."""

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_being, make_campaign, make_tenant
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_held_by import _character, _instance

from lorenzo_api.models import (
    Containment,
    Entity,
    EntityStat,
    GroupMember,
    Membership,
    MembershipRole,
    StatDefinition,
    StatGroup,
    StatValueType,
    User,
)


async def _mark_container(
    session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> None:
    """ADR 0047's convention: `is_container`, a bool in the tenant's `tags`."""
    tags = StatGroup(tenant_id=tenant_id, name="tags")
    session.add(tags)
    await session.flush()
    definition = StatDefinition(
        tenant_id=tenant_id,
        stat_group_id=tags.id,
        name="is_container",
        value_type=StatValueType.BOOL,
    )
    session.add(definition)
    await session.flush()
    session.add(
        EntityStat(
            entity_id=entity_id,
            stat_definition_id=definition.id,
            tenant_id=tenant_id,
            value_bool=True,
        )
    )


@dataclass
class _Scene:
    tenant_id: uuid.UUID
    other_user_ids: list[uuid.UUID]
    ids: dict[str, uuid.UUID]


async def _make_scene(test_user_id: uuid.UUID) -> _Scene:
    """The caller plays Alice; another player plays Brisk. Both are in the
    Company. Mogg is an NPC nobody reaches.

    Alice has equipped:
    - her Sword;
    - her Backpack, holding Brisk's Potion, Mogg's Idol, and her Pouch with
      her Coin in it;
    - Brisk's Bag, holding only Brisk's Gem;
    - Brisk's Satchel, holding Brisk's Map and her Letter;
    - her Box, empty, marked is_container.

    In no container: her Rope; her Chest, holding Brisk's Purse with Brisk's
    Ring in it; the Company's Crate, holding only Brisk's Book; the
    Company's Cart, holding Brisk's Lamp and the Company's Tent.

    Elsewhere: her Carriage stands in the Stable, with an unowned Trunk in
    it and unowned Hay beside it. Brisk has equipped her Dagger and his
    Case, which holds her Scroll and his Quill.
    """
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        brisk_user = User(authgear_subject_id=f"brisk-{uuid.uuid4()}")
        session.add(brisk_user)
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        brisk = await _character(session, tenant_id, campaign.id, brisk_user.id, "Brisk")
        mogg = (await make_being(session, tenant_id=tenant_id, name="Mogg")).entity_id
        company = Entity(tenant_id=tenant_id, name="The Company")
        stable = Entity(tenant_id=tenant_id, name="Stable")
        session.add_all([company, stable])
        await session.flush()
        session.add_all(
            GroupMember(group_entity_id=company.id, character_entity_id=m, tenant_id=tenant_id)
            for m in (alice, brisk)
        )

        ids = {"alice": alice, "brisk": brisk, "mogg": mogg}
        ids |= {"company": company.id, "stable": stable.id}

        async def instance(name: str, owner: str | None, container: str | None) -> None:
            ids[name.casefold()] = await _instance(
                session,
                tenant_id,
                name,
                owner=ids[owner] if owner else None,
                container=ids[container] if container else None,
            )

        await instance("Sword", "alice", "alice")
        await instance("Backpack", "alice", "alice")
        await instance("Potion", "brisk", "backpack")
        await instance("Idol", "mogg", "backpack")
        await instance("Pouch", "alice", "backpack")
        await instance("Coin", "alice", "pouch")
        await instance("Bag", "brisk", "alice")
        await instance("Gem", "brisk", "bag")
        await instance("Satchel", "brisk", "alice")
        await instance("Map", "brisk", "satchel")
        await instance("Letter", "alice", "satchel")
        await instance("Box", "alice", "alice")
        await _mark_container(session, tenant_id, ids["box"])

        await instance("Rope", "alice", None)
        await instance("Chest", "alice", None)
        await instance("Purse", "brisk", "chest")
        await instance("Ring", "brisk", "purse")
        await instance("Crate", "company", None)
        await instance("Book", "brisk", "crate")
        await instance("Cart", "company", None)
        await instance("Lamp", "brisk", "cart")
        await instance("Tent", "company", "cart")

        await instance("Carriage", "alice", "stable")
        await instance("Trunk", None, "carriage")
        await instance("Hay", None, "stable")
        await instance("Dagger", "alice", "brisk")
        await instance("Case", "brisk", "brisk")
        await instance("Scroll", "alice", "case")
        await instance("Quill", "brisk", "case")
        await session.commit()
    return _Scene(tenant_id=tenant_id, other_user_ids=[brisk_user.id], ids=ids)


async def _tear_down(scene: _Scene) -> None:
    await delete_tenant(scene.tenant_id)
    async with admin_session_factory() as session:
        for user_id in scene.other_user_ids:
            await session.delete(await session.get_one(User, user_id))
        await session.commit()


def _column_shape(column: dict[str, object], names: dict[str, str]) -> tuple[object, ...]:
    """A column as (kind, container, container kind, path, carried, contents
    hidden, items), by fixture name."""
    container = column["container"]
    path = column["path"]
    items = column["item_instances"]
    assert isinstance(path, list)
    assert isinstance(items, list)
    assert all(item["visible_to_characters"] is True for item in items)
    return (
        column["kind"],
        names[container["id"]] if isinstance(container, dict) else None,
        column["container_kind"],
        [names[p["id"]] for p in path],
        column["carried"],
        column["contents_hidden"],
        sorted(names[i["entity_id"]] for i in items),
    )


async def test_controlled_by_lays_out_a_beings_board(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    scene = await _make_scene(test_user_id)
    names = {str(v): k for k, v in scene.ids.items()}

    response = await client.get(
        f"/tenants/{scene.tenant_id}/item-instances/controlled-by/{scene.ids['alice']}"
    )

    assert response.status_code == 200
    body = response.json()
    assert [_column_shape(c, names) for c in body["columns"]] == [
        # What she has in hand, whoever's it is.
        (
            "equipped",
            "alice",
            "being",
            [],
            True,
            False,
            ["backpack", "bag", "box", "satchel", "sword"],
        ),
        # What's hers, or the Company's, in no container.
        ("not_carried", None, None, [], False, False, ["cart", "chest", "crate", "rope"]),
        # Carried, in tree order. Mogg's Idol shows: Controlled, not his reach,
        # decides. Brisk's Bag holds nothing of hers, so its contents don't;
        # his Satchel holds her Letter, so all of it does. The Box is empty.
        ("container", "backpack", "item_instance", [], True, False, ["idol", "potion", "pouch"]),
        ("container", "pouch", "item_instance", ["backpack"], True, False, ["coin"]),
        ("container", "bag", "item_instance", [], True, True, []),
        ("container", "box", "item_instance", [], True, False, []),
        ("container", "satchel", "item_instance", [], True, False, ["letter", "map"]),
        # Not carried. Her Chest shows Brisk's Purse, but not what's in it. The
        # Company's Crate holds nothing of hers or the Company's, so its
        # contents don't show; the Cart holds the Company's Tent, so all of it
        # does.
        ("container", "cart", "item_instance", [], False, False, ["lamp", "tent"]),
        ("container", "chest", "item_instance", [], False, False, ["purse"]),
        ("container", "purse", "item_instance", ["chest"], False, True, []),
        ("container", "crate", "item_instance", [], False, True, []),
        ("container", "carriage", "item_instance", ["stable"], False, False, ["trunk"]),
        # Whatever else holds something of hers, listing only that.
        ("read_only", "brisk", "being", [], False, True, ["dagger"]),
        ("read_only", "case", "item_instance", ["brisk"], False, True, ["scroll"]),
        ("read_only", "stable", "other", [], False, True, ["carriage"]),
    ]
    assert [names[o["id"]] for o in body["owners"]] == ["alice", "brisk", "mogg", "company"]
    # Who carries each container (ADR 0134): the nearest being around it.
    carriers = {
        names[c["container"]["id"]]: c["carried_by"] and names[c["carried_by"]["id"]]
        for c in body["columns"]
        if c["container"] is not None
    }
    assert carriers == {
        "alice": None,
        "backpack": "alice",
        "pouch": "alice",
        "bag": "alice",
        "box": "alice",
        "satchel": "alice",
        "cart": None,
        "chest": None,
        "purse": None,
        "crate": None,
        "carriage": None,
        "brisk": None,
        "case": "brisk",
        "stable": None,
    }

    await _tear_down(scene)


async def test_controlled_by_lays_out_a_groups_board(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A group carries nothing, so it has no Equipped. What it owns is all
    Personal to it, so its containers show everything in them."""
    scene = await _make_scene(test_user_id)
    names = {str(v): k for k, v in scene.ids.items()}

    response = await client.get(
        f"/tenants/{scene.tenant_id}/item-instances/controlled-by/{scene.ids['company']}"
    )

    assert response.status_code == 200
    assert [_column_shape(c, names) for c in response.json()["columns"]] == [
        ("not_carried", None, None, [], False, False, ["cart", "crate"]),
        ("container", "cart", "item_instance", [], False, False, ["lamp", "tent"]),
        ("container", "crate", "item_instance", [], False, False, ["book"]),
    ]

    await _tear_down(scene)


async def test_controlled_by_always_has_equipped_and_not_carried(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/item-instances/controlled-by/{alice}")

    assert response.status_code == 200
    assert response.json() == {
        "columns": [
            {
                "kind": "equipped",
                "container": {"id": str(alice), "name": "Alice", "quantity": None},
                "container_kind": "being",
                "path": [],
                "carried": True,
                "carried_by": None,
                "contents_hidden": False,
                "item_instances": [],
            },
            {
                "kind": "not_carried",
                "container": None,
                "container_kind": None,
                "path": [],
                "carried": False,
                "carried_by": None,
                "contents_hidden": False,
                "item_instances": [],
            },
        ],
        "owners": [],
    }

    await delete_tenant(tenant_id)


async def test_controlled_by_404_for_an_entity_out_of_reach_or_unknown(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0130, as held-by: an unreachable entity answers like one that
    doesn't exist. Bob plays in another campaign the caller has no standing
    in."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Bob's campaign")
        await session.flush()
        bob_user = User(authgear_subject_id=f"bob-{uuid.uuid4()}")
        session.add(bob_user)
        await session.flush()
        bob = await _character(session, tenant_id, campaign.id, bob_user.id, "Bob")
        await session.commit()

    unreachable = await client.get(f"/tenants/{tenant_id}/item-instances/controlled-by/{bob}")
    unknown = await client.get(f"/tenants/{tenant_id}/item-instances/controlled-by/{uuid.uuid4()}")

    assert unreachable.status_code == 404
    assert unknown.status_code == 404

    # ORGA reaches everyone (ADR 0040).
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (tenant_id, test_user_id))
        membership.role = MembershipRole.ORGA
        await session.commit()
    as_orga = await client.get(f"/tenants/{tenant_id}/item-instances/controlled-by/{bob}")
    assert as_orga.status_code == 200

    await delete_tenant(tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, bob_user.id))
        await session.commit()


async def test_controlled_by_survives_a_containment_cycle(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0016 allows cycles: Alice's Box is inside a Crate that's inside
    the Box. Each is the other's column, and nothing loops."""
    tenant_id = await make_tenant(test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Campaign")
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        box = await _instance(session, tenant_id, "Box", owner=alice)
        crate = await _instance(session, tenant_id, "Crate", container=box)
        session.add(Containment(child_entity_id=box, parent_entity_id=crate, tenant_id=tenant_id))
        await session.commit()

    response = await client.get(f"/tenants/{tenant_id}/item-instances/controlled-by/{alice}")

    assert response.status_code == 200
    columns = {
        (c["container"] or {}).get("name"): [i["entity_id"] for i in c["item_instances"]]
        for c in response.json()["columns"]
    }
    assert columns == {"Alice": [], None: [], "Box": [str(crate)], "Crate": [str(box)]}

    await delete_tenant(tenant_id)
