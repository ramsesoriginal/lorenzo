"""ADR 0128: capacity on every write that puts something somewhere, refused
only when a load grows past its limit; a GM's override; and a deleted
container's contents kept.
"""

import asyncio
import uuid
from dataclasses import dataclass
from decimal import Decimal

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_held_by import _character

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
        session.add(Item(entity_id=gear.id, tenant_id=tenant_id))
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
        session.add(Item(entity_id=heavy.id, tenant_id=t))
        session.add(EntityPrototype(entity_id=heavy.id, prototype_id=ids["gear"], tenant_id=t))
        await _set(session, t, heavy.id, ids["stat:own_weight"], 40)
        # 20 arrows (1 each, from their pattern, so a split-off weighs the
        # same) of Alice's, in a chest she isn't carrying.
        arrow = Entity(tenant_id=t, name="Arrow")
        chest, arrows = Entity(tenant_id=t, name="Chest"), Entity(tenant_id=t, name="Arrows")
        session.add_all([arrow, chest, arrows])
        await session.flush()
        session.add(Item(entity_id=arrow.id, tenant_id=t))
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
