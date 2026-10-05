"""ADR 0128: capacity on every write that puts something somewhere, refused
only when a load grows past its limit; a GM's override; and a deleted
container's contents kept.
"""

import asyncio
import uuid
from dataclasses import dataclass
from decimal import Decimal

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_held_by import _character

from lorenzo_api.capacity import CapacityCheck
from lorenzo_api.models import (
    AuditLog,
    CampaignGm,
    ComputedStat,
    ComputedStatContents,
    ComputedStatSum,
    ComputedStatSumTerm,
    Containment,
    Entity,
    EntityPrototype,
    EntityStat,
    Item,
    ItemInstance,
    Ownership,
    StatDefinition,
    StatGroup,
    StatValueType,
    User,
)

_STATS = (
    "own_weight",
    "contents_weight",
    "weight",
    "size",
    "carry_capacity",
    "containment_capacity",
    "max_item_size",
)


@dataclass
class _Camp:
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    ids: dict[str, uuid.UUID]


async def _set(session: AsyncSession, t: uuid.UUID, entity: uuid.UUID, stat: uuid.UUID, v: int):
    session.add(EntityStat(entity_id=entity, stat_definition_id=stat, tenant_id=t, value_int=v))


async def _camp(test_user_id: uuid.UUID) -> _Camp:
    """The caller plays Alice (carry_capacity 30), a plain player, not yet
    a GM. Every item is an instance of Gear, whose weight is its own plus
    what's inside it. Alice carries:

    - a Backpack (own 2, carry 20, room 10, nothing larger than 3) holding
      a Rope (1, size 2);
    - a Pouch (own 1, carry 50);
    - a Bag of Holding (weight fixed at 15, carry 1000).

    She owns, in no container: a Boulder (25, size 1), an Anvil (40), a
    Crate (1, size 9), a Sword (1, size 5), a Pebble (1), and a Feather (0).
    Her load is 3 + 1 + 15 = 19.
    """
    tenant_id = await make_tenant(test_user_id)
    await make_plain_participant(tenant_id, test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Table")
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        group = StatGroup(tenant_id=tenant_id, name="physical")
        session.add(group)
        await session.flush()
        stat = {}
        for name in _STATS:
            definition = StatDefinition(
                tenant_id=tenant_id,
                stat_group_id=group.id,
                name=name,
                value_type=StatValueType.INT,
            )
            session.add(definition)
            await session.flush()
            stat[name] = definition.id

        gear = Entity(tenant_id=tenant_id, name="Gear")
        session.add(gear)
        await session.flush()
        session.add(Item(entity_id=gear.id, tenant_id=tenant_id, in_public_catalog=True))
        for target in ("contents_weight", "weight"):
            session.add(
                ComputedStat(
                    entity_id=gear.id, stat_definition_id=stat[target], tenant_id=tenant_id
                )
            )
        await session.flush()
        key = {"entity_id": gear.id, "tenant_id": tenant_id}
        session.add(
            ComputedStatContents(
                **key,
                stat_definition_id=stat["contents_weight"],
                source_stat_definition_id=stat["weight"],
            )
        )
        session.add(
            ComputedStatSum(
                **key, stat_definition_id=stat["weight"], offset=Decimal(0), round_mode="none"
            )
        )
        await session.flush()
        for position, source in enumerate(("own_weight", "contents_weight")):
            session.add(
                ComputedStatSumTerm(
                    **key,
                    stat_definition_id=stat["weight"],
                    source_stat_definition_id=stat[source],
                    coefficient=Decimal(1),
                    position=position,
                )
            )

        ids = {"alice": alice, "gear": gear.id} | {f"stat:{k}": v for k, v in stat.items()}
        await _set(session, tenant_id, alice, stat["carry_capacity"], 30)

        async def thing(name: str, inside: uuid.UUID | None = None, **stats: int) -> uuid.UUID:
            entity = Entity(tenant_id=tenant_id, name=name)
            session.add(entity)
            await session.flush()
            session.add(ItemInstance(entity_id=entity.id, tenant_id=tenant_id))
            session.add(
                EntityPrototype(entity_id=entity.id, prototype_id=gear.id, tenant_id=tenant_id)
            )
            session.add(
                Ownership(owned_entity_id=entity.id, owner_character_id=alice, tenant_id=tenant_id)
            )
            if inside is not None:
                session.add(
                    Containment(
                        child_entity_id=entity.id, parent_entity_id=inside, tenant_id=tenant_id
                    )
                )
            for stat_name, value in stats.items():
                await _set(session, tenant_id, entity.id, stat[stat_name], value)
            await session.flush()
            return entity.id

        ids["backpack"] = await thing(
            "Backpack",
            alice,
            own_weight=2,
            carry_capacity=20,
            containment_capacity=10,
            max_item_size=3,
        )
        ids["rope"] = await thing("Rope", ids["backpack"], own_weight=1, size=2)
        ids["pouch"] = await thing("Pouch", alice, own_weight=1, carry_capacity=50)
        ids["bag"] = await thing("Bag of Holding", alice, weight=15, carry_capacity=1000)
        ids["boulder"] = await thing("Boulder", own_weight=25, size=1)
        ids["anvil"] = await thing("Anvil", own_weight=40)
        ids["crate"] = await thing("Crate", own_weight=1, size=9)
        ids["sword"] = await thing("Sword", own_weight=1, size=5)
        ids["pebble"] = await thing("Pebble", own_weight=1)
        ids["feather"] = await thing("Feather", own_weight=0)
        await session.commit()
    return _Camp(tenant_id, campaign.id, ids)


async def _gm(camp: _Camp, test_user_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        session.add(
            CampaignGm(user_id=test_user_id, campaign_id=camp.campaign_id, tenant_id=camp.tenant_id)
        )
        await session.commit()


def _into(client: AsyncClient, camp: _Camp, item: str, container: str, **extra: object):
    return client.put(
        f"/tenants/{camp.tenant_id}/item-instances/{camp.ids[item]}/container",
        json={"container_entity_id": str(camp.ids[container]), **extra},
    )


async def _parent(camp: _Camp, item: str) -> uuid.UUID | None:
    async with admin_session_factory() as session:
        row = await session.get(Containment, camp.ids[item])
        return row.parent_entity_id if row else None


async def test_each_capacity_refuses_what_would_go_past_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    camp = await _camp(test_user_id)

    heavy = await _into(client, camp, "boulder", "backpack")
    crowded = await _into(client, camp, "crate", "backpack")
    too_big = await _into(client, camp, "sword", "backpack")
    # The Pouch takes the Anvil, but Alice, carrying the Pouch, can't.
    climbed = await _into(client, camp, "anvil", "pouch")

    assert heavy.status_code == 409
    body = heavy.json()
    assert body["type"] == "capacity-exceeded"
    assert body["detail"] == "Backpack can carry 20, and this would make it 26."
    assert (body["stat"], body["limit"], body["load"]) == ("carry_capacity", 20, 26)
    assert body["container"] == {"id": str(camp.ids["backpack"]), "name": "Backpack"}
    assert crowded.json()["detail"] == "Backpack has room for 10, and this would fill it to 11."
    assert too_big.json()["detail"] == "Backpack takes nothing larger than 3, and Sword is 5."
    assert climbed.status_code == 409
    assert climbed.json()["detail"] == "Alice can carry 30, and this would make it 59."
    for item in ("boulder", "crate", "sword", "anvil"):
        assert await _parent(camp, item) is None, item
    await delete_tenant(camp.tenant_id)


async def test_what_doesnt_add_to_a_load_is_never_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Alice's strength drained: she can carry 2, and carries 19. Moving
    within what she carries, taking things out, putting in something
    weightless, and filling her Bag of Holding all go; a Pebble doesn't."""
    camp = await _camp(test_user_id)
    async with admin_session_factory() as session:
        stat = await session.get_one(
            EntityStat, (camp.ids["alice"], camp.ids["stat:carry_capacity"])
        )
        stat.value_int = 2
        await session.commit()
    base = f"/tenants/{camp.tenant_id}/item-instances"

    in_hand = await _into(client, camp, "rope", "alice")
    back = await _into(client, camp, "rope", "pouch")
    out = await client.delete(f"{base}/{camp.ids['rope']}/container")
    weightless = await _into(client, camp, "feather", "alice")
    held = await _into(client, camp, "anvil", "bag")
    pebble = await _into(client, camp, "pebble", "alice")

    for response in (in_hand, back, out, weightless, held):
        assert response.status_code == 200, response.text
    assert pebble.status_code == 409
    assert pebble.json()["detail"] == "Alice can carry 2, and this would make it 19."
    await delete_tenant(camp.tenant_id)


async def test_a_gm_moves_anyway_and_only_a_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    camp = await _camp(test_user_id)

    as_player = await _into(client, camp, "boulder", "backpack", override=True)
    await _gm(camp, test_user_id)
    as_gm = await _into(client, camp, "boulder", "backpack", override=True)

    assert as_player.status_code == 403
    assert as_player.json()["type"] == "override-forbidden"
    assert as_gm.status_code == 200, as_gm.text
    assert await _parent(camp, "boulder") == camp.ids["backpack"]
    async with admin_session_factory() as session:
        detail = await session.scalar(
            select(AuditLog.detail).where(
                AuditLog.tenant_id == camp.tenant_id,
                AuditLog.action == "item_instance.container_set",
            )
        )
    assert detail == f"container={camp.ids['backpack']}; overridden"
    await delete_tenant(camp.tenant_id)


async def test_bulk_moves_refuse_per_item_and_a_gm_overrides_them_all(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    camp = await _camp(test_user_id)
    url = f"/tenants/{camp.tenant_id}/item-instances/bulk-move"
    body = {
        "to_container_entity_id": str(camp.ids["backpack"]),
        "items": [{"entity_id": str(camp.ids["pebble"])}, {"entity_id": str(camp.ids["boulder"])}],
    }

    refused = await client.post(url, json=body)
    await _gm(camp, test_user_id)
    overridden = await client.post(url, json={**body, "override": True})

    assert [r["status"] for r in refused.json()] == ["ok", "error"]
    problem = refused.json()[1]["problem"]
    assert problem["type"] == "capacity-exceeded"
    assert problem["detail"] == "Backpack can carry 20, and this would make it 27."
    assert [r["status"] for r in overridden.json()] == ["ok", "ok"]
    await delete_tenant(camp.tenant_id)


async def test_handing_over_and_creating_inside_are_checked(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    camp = await _camp(test_user_id)
    t, ids = camp.tenant_id, camp.ids
    async with admin_session_factory() as session:
        heavy = Entity(tenant_id=t, name="Anvil pattern")
        session.add(heavy)
        await session.flush()
        session.add(Item(entity_id=heavy.id, tenant_id=t, in_public_catalog=True))
        session.add(EntityPrototype(entity_id=heavy.id, prototype_id=ids["gear"], tenant_id=t))
        await _set(session, t, heavy.id, ids["stat:own_weight"], 40)
        # 20 arrows (1 each, from their pattern, so a split-off weighs the
        # same) of Alice's, in a chest she isn't carrying.
        arrow = Entity(tenant_id=t, name="Arrow")
        chest, arrows = Entity(tenant_id=t, name="Chest"), Entity(tenant_id=t, name="Arrows")
        session.add_all([arrow, chest, arrows])
        await session.flush()
        session.add(Item(entity_id=arrow.id, tenant_id=t, in_public_catalog=True))
        session.add(EntityPrototype(entity_id=arrow.id, prototype_id=ids["gear"], tenant_id=t))
        await _set(session, t, arrow.id, ids["stat:own_weight"], 1)
        for entity in (chest, arrows):
            session.add(ItemInstance(entity_id=entity.id, tenant_id=t))
        session.add(EntityPrototype(entity_id=arrows.id, prototype_id=arrow.id, tenant_id=t))
        session.add(
            Ownership(owned_entity_id=arrows.id, owner_character_id=ids["alice"], tenant_id=t)
        )
        session.add(
            Containment(
                child_entity_id=arrows.id, parent_entity_id=chest.id, tenant_id=t, quantity=20
            )
        )
        await session.commit()

    handed = await client.put(
        f"/tenants/{t}/item-instances/{ids['anvil']}/owner",
        json={"owner_character_id": str(ids["alice"]), "move_to_owner": True},
    )
    created = await client.post(
        f"/tenants/{t}/item-instances",
        json={
            "prototype_id": str(heavy.id),
            "owner_character_id": str(ids["alice"]),
            "container_entity_id": str(ids["pouch"]),
        },
    )
    # 15 of them split off into her hands: 19 + 15.
    split = await client.post(
        f"/tenants/{t}/item-instances/bulk-assign",
        json=[
            {
                "entity_id": str(arrows.id),
                "owner_character_id": str(ids["alice"]),
                "quantity": 15,
                "move_to_owner": True,
            }
        ],
    )
    light = await client.post(
        f"/tenants/{t}/item-instances",
        json={
            "prototype_id": str(ids["gear"]),
            "owner_character_id": str(ids["alice"]),
            "container_entity_id": str(ids["backpack"]),
        },
    )

    assert handed.status_code == 409
    assert handed.json()["detail"] == "Alice can carry 30, and this would make it 59."
    assert created.status_code == 409
    assert created.json()["type"] == "capacity-exceeded"
    assert split.json()[0]["problem"]["detail"] == "Alice can carry 30, and this would make it 34."
    # A Gear with no weight of its own weighs nothing; nothing to refuse.
    assert light.status_code == 201, light.text
    await delete_tenant(t)


async def _ownerless(
    camp: _Camp, name: str, inside: uuid.UUID | None = None, quantity: int = 1
) -> uuid.UUID:
    """A Gear nobody owns, in `inside` if given, a stack of `quantity` there."""
    t = camp.tenant_id
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=t, name=name)
        session.add(entity)
        await session.flush()
        session.add(ItemInstance(entity_id=entity.id, tenant_id=t))
        session.add(
            EntityPrototype(entity_id=entity.id, prototype_id=camp.ids["gear"], tenant_id=t)
        )
        if inside is not None:
            session.add(
                Containment(
                    child_entity_id=entity.id,
                    parent_entity_id=inside,
                    tenant_id=t,
                    quantity=quantity,
                )
            )
        await session.commit()
        return entity.id


async def test_handing_things_over_at_once_to_one_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Each hand-over's ownership row share-locks Alice, whose chain its move
    into her hands locks for capacity. That lock is taken before the row
    goes in, so several hand-overs to her at once queue up instead of each
    waiting on the others' share lock."""
    camp = await _camp(test_user_id)
    await _gm(camp, test_user_id)
    t, ids = camp.tenant_id, camp.ids
    coins = [await _ownerless(camp, f"Coin {n}") for n in range(4)]

    handed = await asyncio.gather(
        *(
            client.put(
                f"/tenants/{t}/item-instances/{coin}/owner",
                json={"owner_character_id": str(ids["alice"]), "move_to_owner": True},
            )
            for coin in coins
        )
    )

    assert [r.status_code for r in handed] == [200] * 4, [r.text for r in handed]
    async with admin_session_factory() as session:
        for coin in coins:
            assert (await session.get_one(Containment, coin)).parent_entity_id == ids["alice"]
    await delete_tenant(t)


async def test_bulk_handing_things_over_at_once_to_one_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The same through bulk-assign, where what's inside each Purse is given
    first (ADR 0125): its ownership row share-locks Alice too, so her chain
    is locked before that."""
    camp = await _camp(test_user_id)
    await _gm(camp, test_user_id)
    t, ids = camp.tenant_id, camp.ids
    purses = [await _ownerless(camp, f"Purse {n}") for n in range(4)]
    for n, purse in enumerate(purses):
        await _ownerless(camp, f"Coin {n}", inside=purse)

    assigned = await asyncio.gather(
        *(
            client.post(
                f"/tenants/{t}/item-instances/bulk-assign",
                json=[
                    {
                        "entity_id": str(purse),
                        "owner_character_id": str(ids["alice"]),
                        "move_to_owner": True,
                        "with_contents": True,
                    }
                ],
            )
            for purse in purses
        )
    )

    assert [r.status_code for r in assigned] == [200] * 4, [r.text for r in assigned]
    entries = [r.json()[0] for r in assigned]
    assert [e["status"] for e in entries] == ["ok"] * 4, entries
    assert [c["status"] for e in entries for c in e["contents"]] == ["ok"] * 4
    async with admin_session_factory() as session:
        for purse in purses:
            assert (await session.get_one(Containment, purse)).parent_entity_id == ids["alice"]
    await delete_tenant(t)


async def _bob(camp: _Camp) -> uuid.UUID:
    """Bob, another player's character at Alice's table."""
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"bob-{uuid.uuid4()}")
        session.add(user)
        await session.flush()
        bob = await _character(session, camp.tenant_id, camp.campaign_id, user.id, "Bob")
        await session.commit()
    return bob


# Two kinds of bulk-assign, each entry passing its own ownerless Gear to
# Alice or Bob: given, handed over (move_to_owner), or one split off a stack
# of two into their hands.
_CROSSINGS = {
    # The first entry's ownership row share-locks Alice, whose chain the
    # second's hand-over locks for capacity.
    "one-owner": (
        [("give", "alice"), ("hand over", "alice")],
        [("give", "alice"), ("hand over", "alice")],
    ),
    # Each move locks its owner's chain.
    "moves-crosswise": (
        [("hand over", "alice"), ("split off", "bob")],
        [("hand over", "bob"), ("split off", "alice")],
    ),
    # An entry that only gives share-locks its owner all the same.
    "give-and-move-crosswise": (
        [("give", "alice"), ("hand over", "bob")],
        [("give", "bob"), ("hand over", "alice")],
    ),
    # One that moves nothing locks no chain, and only share-locks its owners.
    "gives-against-moves": (
        [("give", "alice"), ("give", "bob")],
        [("hand over", "bob"), ("hand over", "alice")],
    ),
}


@pytest.mark.parametrize("crossing", _CROSSINGS)
async def test_bulk_assigns_at_once_never_wait_on_each_other(
    client: AsyncClient, test_user_id: uuid.UUID, crossing: str
) -> None:
    """What an entry locks stays locked until the commit, so taken entry by
    entry, two bulk-assigns could each wait on the other's earlier entries'
    locks. Every entry's chain is taken before any runs, in one go, and the
    share locks its ownership rows take never wait on a chain's. Two of
    each kind at once."""
    camp = await _camp(test_user_id)
    await _gm(camp, test_user_id)
    t = camp.tenant_id
    owners = {"alice": camp.ids["alice"], "bob": await _bob(camp)}
    chest = await _ownerless(camp, "Chest")
    bodies, expected = [], []
    for n, kind in enumerate(_CROSSINGS[crossing] * 2):
        body: list[dict[str, object]] = []
        for m, (how, who) in enumerate(kind):
            split = how == "split off"
            gear = await _ownerless(
                camp, f"Gear {n}.{m}", inside=chest if split else None, quantity=2
            )
            body.append(
                {
                    "entity_id": str(gear),
                    "owner_character_id": str(owners[who]),
                    "move_to_owner": how != "give",
                    **({"quantity": 1} if split else {}),
                }
            )
            expected.append((str(owners[who]), None if how == "give" else str(owners[who])))
        bodies.append(body)

    assigned = await asyncio.gather(
        *(client.post(f"/tenants/{t}/item-instances/bulk-assign", json=body) for body in bodies)
    )

    assert [r.status_code for r in assigned] == [200] * 4, [r.text for r in assigned]
    entries = [entry for r in assigned for entry in r.json()]
    assert [e["status"] for e in entries] == ["ok"] * len(entries), entries
    assert [
        (e["item_instance"]["owner_entity_id"], e["item_instance"]["container_entity_id"])
        for e in entries
    ] == expected
    await delete_tenant(t)


async def test_handing_over_at_once_with_a_bulk_assign_giving_it_away(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A bulk-assign handing a Coin over to Alice locks her chain before its
    first entry, then gives the Gear to Bob in its second, writing the
    Gear's ownership row. A hand-over of that Gear to Alice locks her chain
    before it writes that row: writing it first, it would hold the row while
    waiting on her chain, and the bulk-assign the other way around. Four of
    each at once."""
    camp = await _camp(test_user_id)
    await _gm(camp, test_user_id)
    t, alice = camp.tenant_id, camp.ids["alice"]
    bob = await _bob(camp)
    pairs = [
        (await _ownerless(camp, f"Gear {n}"), await _ownerless(camp, f"Coin {n}")) for n in range(4)
    ]

    done = await asyncio.gather(
        *(
            request
            for gear, coin in pairs
            for request in (
                client.put(
                    f"/tenants/{t}/item-instances/{gear}/owner",
                    json={"owner_character_id": str(alice), "move_to_owner": True},
                ),
                client.post(
                    f"/tenants/{t}/item-instances/bulk-assign",
                    json=[
                        {
                            "entity_id": str(coin),
                            "owner_character_id": str(alice),
                            "move_to_owner": True,
                        },
                        {"entity_id": str(gear), "owner_character_id": str(bob)},
                    ],
                ),
            )
        )
    )

    assert [r.status_code for r in done] == [200] * 8, [r.text for r in done]
    entries = [entry for r in done[1::2] for entry in r.json()]
    assert [e["status"] for e in entries] == ["ok"] * 8, entries
    async with admin_session_factory() as session:
        for gear, coin in pairs:
            for thing in (gear, coin):
                assert (await session.get_one(Containment, thing)).parent_entity_id == alice
    await delete_tenant(t)


async def test_deleting_a_container_keeps_what_was_inside(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The Backpack goes; its Rope and a stack of 20 Arrows land in Alice's
    hands, counts kept. An ownerless Chest in no container can't drop a
    stack out of every container, so deleting it waits; a single thing in
    it just leaves every container."""
    camp = await _camp(test_user_id)
    t, ids = camp.tenant_id, camp.ids
    await _gm(camp, test_user_id)
    async with admin_session_factory() as session:
        things = {}
        for name in ("Arrows", "Chest", "Loose arrows", "Coin", "Crate chest"):
            entity = Entity(tenant_id=t, name=name)
            session.add(entity)
            await session.flush()
            session.add(ItemInstance(entity_id=entity.id, tenant_id=t))
            things[name] = entity.id
        session.add_all(
            [
                Containment(
                    child_entity_id=things["Arrows"],
                    parent_entity_id=ids["backpack"],
                    tenant_id=t,
                    quantity=20,
                ),
                Containment(
                    child_entity_id=things["Loose arrows"],
                    parent_entity_id=things["Chest"],
                    tenant_id=t,
                    quantity=12,
                ),
                Containment(
                    child_entity_id=things["Coin"],
                    parent_entity_id=things["Crate chest"],
                    tenant_id=t,
                ),
            ]
        )
        await session.commit()
    base = f"/tenants/{t}/item-instances"

    backpack = await client.delete(f"{base}/{ids['backpack']}")
    chest = await client.delete(f"{base}/{things['Chest']}")
    crate = await client.delete(f"{base}/{things['Crate chest']}")

    assert backpack.status_code == 204, backpack.text
    async with admin_session_factory() as session:
        arrows = await session.get_one(Containment, things["Arrows"])
        assert (arrows.parent_entity_id, arrows.quantity) == (ids["alice"], 20)
        assert (await session.get_one(Containment, ids["rope"])).parent_entity_id == ids["alice"]
        assert await session.get(Containment, things["Coin"]) is None
        detail = await session.scalar(
            select(AuditLog.detail).where(
                AuditLog.tenant_id == t,
                AuditLog.action == "item_instance.deleted",
                AuditLog.target_id == ids["backpack"],
            )
        )
    assert detail == "contents moved out: 2"
    assert chest.status_code == 409
    assert chest.json()["type"] == "stack-needs-container"
    assert "Chest holds Loose arrows, a stack of 12" in chest.json()["detail"]
    assert crate.status_code == 204
    await delete_tenant(t)


async def test_nothing_is_measured_without_capacity_stats(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """A tenant without the three capacity names moves freely, however much
    things weigh."""
    camp = await _camp(test_user_id)
    async with admin_session_factory() as session:
        for name in ("carry_capacity", "containment_capacity", "max_item_size"):
            definition = await session.get_one(StatDefinition, camp.ids[f"stat:{name}"])
            await session.execute(
                EntityStat.__table__.delete().where(EntityStat.stat_definition_id == definition.id)
            )
            await session.delete(definition)
        await session.commit()

    moved = await _into(client, camp, "anvil", "backpack")

    assert moved.status_code == 200, moved.text
    await delete_tenant(camp.tenant_id)


async def test_creating_owned_things_at_once_into_what_their_owner_carries(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Each new Gear's ownership row share-locks Alice, whose Backpack it goes
    into. Capacity locks her chain before that row goes in, so several
    creates at once queue up instead of each waiting on the others' share
    lock - a deadlock inventory-web's end-to-end stacks ran into."""
    camp = await _camp(test_user_id)
    await _gm(camp, test_user_id)
    t, ids = camp.tenant_id, camp.ids

    created = await asyncio.gather(
        *(
            client.post(
                f"/tenants/{t}/item-instances",
                json={
                    "prototype_id": str(ids["gear"]),
                    "owner_character_id": str(ids["alice"]),
                    "container_entity_id": str(ids["backpack"]),
                },
            )
            for _ in range(4)
        )
    )

    assert [r.status_code for r in created] == [201] * 4, [r.text for r in created]
    await delete_tenant(t)


async def test_creating_things_at_once_into_what_someone_else_carries(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The ownership row share-locks the new Gear's owner, who needn't be in
    the chain capacity locks: Bob's goes into Alice's Backpack, Alice's into
    a Satchel Bob carries. Two of each at once each hold a chain the other's
    owner is in, and that share lock doesn't wait on it."""
    camp = await _camp(test_user_id)
    await _gm(camp, test_user_id)
    t, ids = camp.tenant_id, camp.ids
    bob = await _bob(camp)
    satchel = await _ownerless(camp, "Satchel", inside=bob)
    crosswise = [(bob, ids["backpack"]), (ids["alice"], satchel)] * 2

    created = await asyncio.gather(
        *(
            client.post(
                f"/tenants/{t}/item-instances",
                json={
                    "prototype_id": str(ids["gear"]),
                    "owner_character_id": str(owner),
                    "container_entity_id": str(container),
                },
            )
            for owner, container in crosswise
        )
    )

    assert [r.status_code for r in created] == [201] * 4, [r.text for r in created]
    assert [(r.json()["owner_entity_id"], r.json()["container_entity_id"]) for r in created] == [
        (str(owner), str(container)) for owner, container in crosswise
    ]
    await delete_tenant(t)


async def test_moving_things_at_once_into_room_for_one(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Checks on one chain still queue up, each measuring the one before's
    result: of three Bricks of 10 moved at once into a Sack that carries 15,
    only one gets in."""
    camp = await _camp(test_user_id)
    await _gm(camp, test_user_id)
    t, ids = camp.tenant_id, camp.ids
    sack = await _ownerless(camp, "Sack")
    bricks = [await _ownerless(camp, f"Brick {n}") for n in range(3)]
    async with admin_session_factory() as session:
        await _set(session, t, sack, ids["stat:carry_capacity"], 15)
        for brick in bricks:
            await _set(session, t, brick, ids["stat:own_weight"], 10)
        await session.commit()

    moved = await asyncio.gather(
        *(
            client.put(
                f"/tenants/{t}/item-instances/{brick}/container",
                json={"container_entity_id": str(sack)},
            )
            for brick in bricks
        )
    )

    assert sorted(r.status_code for r in moved) == [200, 409, 409], [r.text for r in moved]
    await delete_tenant(t)


async def test_a_check_holds_up_another_but_not_what_points_into_its_chain(
    test_user_id: uuid.UUID,
) -> None:
    """While a check holds the Backpack's chain, another check on it waits,
    but an ownership row for Alice and a containment row into the Backpack
    go straight in. What a write share-locks through those foreign keys -
    one that checks nothing, like a GM's moving anyway or a split beside its
    stack, included - never waits on a check, so never in a cycle with one."""
    camp = await _camp(test_user_id)
    t, ids = camp.tenant_id, camp.ids
    coin = await _ownerless(camp, "Coin")
    async with admin_session_factory() as holding, admin_session_factory() as other:
        assert await CapacityCheck.start(holding, tenant_id=t, target_id=ids["backpack"])

        await other.execute(text("SET LOCAL lock_timeout = '1s'"))
        other.add(Ownership(owned_entity_id=coin, owner_character_id=ids["alice"], tenant_id=t))
        other.add(Containment(child_entity_id=coin, parent_entity_id=ids["backpack"], tenant_id=t))
        await other.flush()
        await other.rollback()

        await other.execute(text("SET LOCAL lock_timeout = '1s'"))
        with pytest.raises(DBAPIError, match="lock timeout"):
            await CapacityCheck.start(other, tenant_id=t, target_id=ids["backpack"])
        await other.rollback()
        await holding.rollback()
    await delete_tenant(t)


async def test_a_stack_created_inside_weighs_all_of_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0140: a stack of n made in one create is checked as n, not as one."""
    camp = await _camp(test_user_id)
    t, ids = camp.tenant_id, camp.ids
    async with admin_session_factory() as session:
        pebble = Entity(tenant_id=t, name="Pebble pattern")
        session.add(pebble)
        await session.flush()
        session.add(Item(entity_id=pebble.id, tenant_id=t, in_public_catalog=True))
        session.add(EntityPrototype(entity_id=pebble.id, prototype_id=ids["gear"], tenant_id=t))
        await _set(session, t, pebble.id, ids["stat:own_weight"], 1)
        await session.commit()
        pebble_id = pebble.id

    def create(quantity: int):
        return client.post(
            f"/tenants/{t}/item-instances",
            json={
                "prototype_id": str(pebble_id),
                "owner_character_id": str(ids["alice"]),
                "container_entity_id": str(ids["backpack"]),
                "quantity": quantity,
            },
        )

    too_many = await create(25)
    fits = await create(5)

    # The Backpack carries 20 and already holds the Rope (1): 1 + 25 is too much, 1 + 5 is not.
    assert too_many.status_code == 409
    assert too_many.json()["detail"] == "Backpack can carry 20, and this would make it 26."
    assert fits.status_code == 201, fits.text
    assert fits.json()["quantity"] == 5
    await delete_tenant(t)
