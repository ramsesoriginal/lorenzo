"""POST .../item-instances/from-pack - handing a pack out (RFC 0032, ADR 0149)."""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_held_by import _character

from lorenzo_api.exceptions import InvalidPackOwnerError
from lorenzo_api.models import (
    AuditLog,
    CampaignGm,
    ComputedStat,
    ComputedStatContents,
    ComputedStatSum,
    ComputedStatSumTerm,
    Containment,
    Entity,
    EntityChange,
    EntityPrototype,
    EntitySlug,
    EntityStat,
    GroupMember,
    Information,
    Item,
    ItemInstance,
    Ownership,
    Payload,
    PayloadDescription,
    StatDefinition,
    StatGroup,
    StatValueType,
    User,
)
from lorenzo_api.pack_giving import hand_out

LIST = (
    "This pack contains:\n\n"
    "- 1 x [Backpack](backpack)\n"
    "  - 5 x [Rations](rations)\n"
    "  - 2 x [Torch](torch)\n"
    "- 2 x [Rope](rope)"
)
STATS = ("own_weight", "contents_weight", "weight", "carry_capacity")


@dataclass
class _World:
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    bob_user_id: uuid.UUID
    ids: dict[str, uuid.UUID]
    stat: dict[str, uuid.UUID] = field(default_factory=dict)


async def _describe(
    session: AsyncSession, tenant_id: uuid.UUID, entity_id: uuid.UUID, text: str, *, public: bool
) -> None:
    information = Information(
        tenant_id=tenant_id,
        entity_id=entity_id,
        title="Description",
        type="description",
        is_public=public,
    )
    session.add(information)
    await session.flush()
    payload = Payload(tenant_id=tenant_id, information_id=information.id)
    session.add(payload)
    await session.flush()
    session.add(
        PayloadDescription(payload_id=payload.id, tenant_id=tenant_id, locale="en", content=text)
    )
    await session.flush()


async def _world(test_user_id: uuid.UUID, *, capacity: bool = False) -> _World:
    """The caller plays Alice, a plain player. Bob plays Brisk in the same
    campaign. The Company is a group Alice is a member of; Brisk is not.

    The catalog is Backpack, Rations, Torch, Rope (and Chest, Pouch and Coin
    for depth), the pack "Explorer's pack" (public description `LIST`), and
    "Secret pack" (the same list, GM-only). With `capacity`, every item
    inherits from Gear, whose weight is its own plus what's inside it, and
    weighs 2 (Backpack) or 1 (the rest).
    """
    tenant_id = await make_tenant(test_user_id)
    await make_plain_participant(tenant_id, test_user_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Table")
        bob = User(authgear_subject_id=f"bob-{uuid.uuid4()}")
        session.add(bob)
        await session.flush()
        alice = await _character(session, tenant_id, campaign.id, test_user_id, "Alice")
        brisk = await _character(session, tenant_id, campaign.id, bob.id, "Brisk")
        company = Entity(tenant_id=tenant_id, name="The Company")
        session.add(company)
        await session.flush()
        session.add(
            GroupMember(group_entity_id=company.id, character_entity_id=alice, tenant_id=tenant_id)
        )
        ids = {"alice": alice, "brisk": brisk, "company": company.id}
        stat: dict[str, uuid.UUID] = {}
        gear: uuid.UUID | None = None
        if capacity:
            group = StatGroup(tenant_id=tenant_id, name="physical")
            session.add(group)
            await session.flush()
            for name in STATS:
                definition = StatDefinition(
                    tenant_id=tenant_id,
                    stat_group_id=group.id,
                    name=name,
                    value_type=StatValueType.INT,
                )
                session.add(definition)
                await session.flush()
                stat[name] = definition.id
            gear_entity = Entity(tenant_id=tenant_id, name="Gear")
            session.add(gear_entity)
            await session.flush()
            session.add(Item(entity_id=gear_entity.id, tenant_id=tenant_id, in_public_catalog=True))
            for target in ("contents_weight", "weight"):
                session.add(
                    ComputedStat(
                        entity_id=gear_entity.id,
                        stat_definition_id=stat[target],
                        tenant_id=tenant_id,
                    )
                )
            await session.flush()
            key = {"entity_id": gear_entity.id, "tenant_id": tenant_id}
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
            gear = gear_entity.id

        async def item(name: str, slug: str, **stats: int) -> uuid.UUID:
            entity = Entity(tenant_id=tenant_id, name=name)
            session.add(entity)
            await session.flush()
            session.add(Item(entity_id=entity.id, tenant_id=tenant_id, in_public_catalog=True))
            session.add(EntitySlug(entity_id=entity.id, tenant_id=tenant_id, slug=slug))
            if gear is not None:
                session.add(
                    EntityPrototype(entity_id=entity.id, prototype_id=gear, tenant_id=tenant_id)
                )
                stats.setdefault("own_weight", 1)
            for stat_name, value in stats.items():
                session.add(
                    EntityStat(
                        entity_id=entity.id,
                        stat_definition_id=stat[stat_name],
                        tenant_id=tenant_id,
                        value_int=value,
                    )
                )
            await session.flush()
            return entity.id

        ids["backpack"] = await item("Backpack", "backpack", **({"own_weight": 2} if gear else {}))
        for name in ("Rations", "Torch", "Rope", "Chest", "Pouch", "Coin"):
            ids[name.lower()] = await item(name, name.lower())
        ids["pack"] = await item("Explorer's pack", "explorers-pack")
        ids["secret"] = await item("Secret pack", "secret-pack")
        await _describe(session, tenant_id, ids["pack"], LIST, public=True)
        await _describe(session, tenant_id, ids["secret"], LIST, public=False)
        if capacity:
            session.add(
                EntityStat(
                    entity_id=alice,
                    stat_definition_id=stat["carry_capacity"],
                    tenant_id=tenant_id,
                    value_int=11,
                )
            )
        await session.commit()
    return _World(tenant_id, campaign.id, bob.id, ids, stat)


async def _tear_down(world: _World) -> None:
    await delete_tenant(world.tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, world.bob_user_id))
        await session.commit()


async def _pack(
    world: _World, text: str, *, name: str = "A pack", public: bool = True
) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity = Entity(tenant_id=world.tenant_id, name=name)
        session.add(entity)
        await session.flush()
        session.add(Item(entity_id=entity.id, tenant_id=world.tenant_id, in_public_catalog=True))
        await _describe(session, world.tenant_id, entity.id, text, public=public)
        await session.commit()
        return entity.id


async def _make_gm(world: _World, user_id: uuid.UUID) -> None:
    """The caller GMs the campaign: a group's pack is a manager's to give (a
    player's self-service makes things for their own character only, ADR 0186)."""
    async with admin_session_factory() as session:
        session.add(
            CampaignGm(user_id=user_id, campaign_id=world.campaign_id, tenant_id=world.tenant_id)
        )
        await session.commit()


async def _give(
    client: AsyncClient,
    world: _World,
    pack: str | uuid.UUID,
    owner: str | uuid.UUID,
    *,
    dry_run: bool = False,
    **extra: Any,
) -> Any:
    return await client.post(
        f"/tenants/{world.tenant_id}/item-instances/from-pack",
        params={"dry_run": "true"} if dry_run else None,
        json={
            "pack_id": str(world.ids.get(pack, pack) if isinstance(pack, str) else pack),
            "owner_entity_id": str(
                world.ids.get(owner, owner) if isinstance(owner, str) else owner
            ),
            **extra,
        },
    )


@dataclass(frozen=True)
class _Row:
    name: str
    owner: uuid.UUID | None
    parent: uuid.UUID | None
    quantity: int | None
    prototype: str


async def _instances(world: _World) -> list[_Row]:
    """Every item instance of the tenant, oldest first."""
    async with admin_session_factory() as session:
        rows = await session.execute(
            select(
                Entity.name,
                Ownership.owner_character_id,
                Containment.parent_entity_id,
                Containment.quantity,
                EntityPrototype.prototype_id,
            )
            .select_from(ItemInstance)
            .join(Entity, Entity.id == ItemInstance.entity_id)
            .outerjoin(Ownership, Ownership.owned_entity_id == Entity.id)
            .outerjoin(Containment, Containment.child_entity_id == Entity.id)
            .join(EntityPrototype, EntityPrototype.entity_id == Entity.id)
            .where(ItemInstance.tenant_id == world.tenant_id)
            .order_by(Entity.created_at, Entity.name)
        )
        names = {v: k for k, v in world.ids.items()}
        return [
            _Row(name, owner, parent, quantity, names[prototype])
            for name, owner, parent, quantity, prototype in rows
        ]


async def _count(world: _World) -> int:
    async with admin_session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(ItemInstance)
                .where(ItemInstance.tenant_id == world.tenant_id)
            )
            or 0
        )


def _titles(created: list[dict[str, Any]]) -> list[Any]:
    return [
        [
            entry["item_instance"]["title"],
            entry["item_instance"]["quantity"],
            _titles(entry["children"]),
        ]
        for entry in created
    ]


async def test_gives_a_pack_to_a_being_into_its_hands(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    alice = world.ids["alice"]

    response = await _give(client, world, "pack", "alice")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["dry_run"] is False
    assert body["pack_id"] == str(world.ids["pack"])
    assert body["owner_entity_id"] == str(alice)
    # A container with its stacks, then the loose stack.
    assert _titles(body["created"]) == [
        ["Backpack", 1, [["Rations", 5, []], ["Torch", 2, []]]],
        ["Rope", 2, []],
    ]
    rows = {row.name: row for row in await _instances(world)}
    assert set(rows) == {"Backpack", "Rations", "Torch", "Rope"}
    # Everything is Alice's, and the top of the list is in her hands.
    assert {row.owner for row in rows.values()} == {alice}
    assert rows["Backpack"].parent == alice
    assert rows["Rope"].parent == alice
    assert (rows["Rope"].quantity, rows["Rope"].prototype) == (2, "rope")
    backpack = body["created"][0]["item_instance"]["entity_id"]
    assert rows["Rations"].parent == uuid.UUID(backpack)
    assert (rows["Rations"].quantity, rows["Torch"].quantity) == (5, 2)
    assert rows["Backpack"].prototype == "backpack"
    # The pack item is a recipe: it isn't instantiated.
    assert "Explorer's pack" not in rows

    await _tear_down(world)


async def test_a_container_is_made_once_for_each_unit(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    pack = await _pack(world, "- 2 x [Backpack](backpack)\n  - 3 x [Rations](rations)")

    response = await _give(client, world, pack, "alice")

    assert response.status_code == 201, response.text
    assert _titles(response.json()["created"]) == [
        ["Backpack", 1, [["Rations", 3, []]]],
        ["Backpack", 1, [["Rations", 3, []]]],
    ]
    rows = await _instances(world)
    assert [row.name for row in rows].count("Backpack") == 2
    backpacks = {entry["item_instance"]["entity_id"] for entry in response.json()["created"]}
    assert {str(row.parent) for row in rows if row.name == "Rations"} == backpacks

    await _tear_down(world)


async def test_nests_as_deep_as_the_list_does(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    world = await _world(test_user_id)
    pack = await _pack(
        world, "- 1 x [Chest](chest)\n  - 1 x [Pouch](pouch)\n    - 20 x [Coin](coin)"
    )

    response = await _give(client, world, pack, "alice")

    assert response.status_code == 201, response.text
    assert _titles(response.json()["created"]) == [["Chest", 1, [["Pouch", 1, [["Coin", 20, []]]]]]]
    rows = {row.name: row for row in await _instances(world)}
    assert rows["Chest"].parent == world.ids["alice"]
    assert rows["Coin"].quantity == 20

    await _tear_down(world)


async def test_gives_a_pack_to_a_group_owned_and_in_no_container(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await _make_gm(world, test_user_id)
    company = world.ids["company"]

    response = await _give(client, world, "pack", "company")

    assert response.status_code == 201, response.text
    # A group has no container for a count: the loose Rope is two instances,
    # and nothing in no container has a count at all (ADR 0041).
    assert _titles(response.json()["created"]) == [
        ["Backpack", None, [["Rations", 5, []], ["Torch", 2, []]]],
        ["Rope", None, []],
        ["Rope", None, []],
    ]
    rows = await _instances(world)
    assert {row.owner for row in rows} == {company}
    top = [row for row in rows if row.name in ("Backpack", "Rope")]
    assert len(top) == 3
    assert all(row.parent is None and row.quantity is None for row in top)
    # What is inside the backpack is still a stack in it.
    inside = {row.name: row for row in rows if row.name in ("Rations", "Torch")}
    assert inside["Rations"].quantity == 5
    assert inside["Rations"].parent is not None

    await _tear_down(world)


async def test_a_dry_run_answers_like_a_real_call_and_keeps_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)

    response = await _give(client, world, "pack", "alice", dry_run=True)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["dry_run"] is True
    assert _titles(body["created"]) == [
        ["Backpack", 1, [["Rations", 5, []], ["Torch", 2, []]]],
        ["Rope", 2, []],
    ]
    assert await _count(world) == 0
    async with admin_session_factory() as session:
        assert (
            await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.tenant_id == world.tenant_id,
                    AuditLog.action == "item_instance.created",
                )
            )
            == 0
        )

    await _tear_down(world)


async def test_a_dry_run_is_refused_by_capacity_as_a_real_call_is(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id, capacity=True)
    async with admin_session_factory() as session:
        stat = await session.get_one(EntityStat, (world.ids["alice"], world.stat["carry_capacity"]))
        stat.value_int = 10
        await session.commit()

    response = await _give(client, world, "pack", "alice", dry_run=True)

    assert response.status_code == 409
    assert response.json()["type"] == "capacity-exceeded"
    assert await _count(world) == 0

    await _tear_down(world)


async def test_what_fits_is_given_and_a_load_at_the_limit_is_not_refused(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    # Backpack 2 + Rations 5 + Torch 2 = 9 in the pack, and 2 Ropes: Alice
    # carries 11, her limit.
    world = await _world(test_user_id, capacity=True)

    response = await _give(client, world, "pack", "alice")

    assert response.status_code == 201, response.text
    assert await _count(world) == 4

    await _tear_down(world)


async def test_a_pack_that_overfills_the_being_is_refused_whole(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id, capacity=True)
    async with admin_session_factory() as session:
        stat = await session.get_one(EntityStat, (world.ids["alice"], world.stat["carry_capacity"]))
        stat.value_int = 10
        await session.commit()

    response = await _give(client, world, "pack", "alice")

    assert response.status_code == 409
    body = response.json()
    assert body["type"] == "capacity-exceeded"
    assert body["detail"] == "Alice can carry 10, and this would make it 11."
    assert await _count(world) == 0

    await _tear_down(world)


async def test_a_new_container_holds_its_own_limit(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id, capacity=True)
    async with admin_session_factory() as session:
        # What goes in the Backpack weighs 7; it can carry 6.
        session.add(
            EntityStat(
                entity_id=world.ids["backpack"],
                stat_definition_id=world.stat["carry_capacity"],
                tenant_id=world.tenant_id,
                value_int=6,
            )
        )
        await session.commit()

    response = await _give(client, world, "pack", "alice")

    assert response.status_code == 409
    body = response.json()
    assert body["type"] == "capacity-exceeded"
    assert body["container"]["name"] == "Backpack"
    assert body["stat"] == "carry_capacity"
    assert await _count(world) == 0

    await _tear_down(world)


async def test_a_group_has_no_limit_of_its_own_at_the_top(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id, capacity=True)
    await _make_gm(world, test_user_id)
    async with admin_session_factory() as session:
        stat = await session.get_one(EntityStat, (world.ids["alice"], world.stat["carry_capacity"]))
        stat.value_int = 1
        await session.commit()

    # Alice could not carry it, but the Company carries nothing.
    response = await _give(client, world, "pack", "company")

    assert response.status_code == 201, response.text
    assert await _count(world) == 5

    await _tear_down(world)


async def test_only_a_gm_may_override_capacity(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id, capacity=True)
    async with admin_session_factory() as session:
        session.add(
            EntityStat(
                entity_id=world.ids["brisk"],
                stat_definition_id=world.stat["carry_capacity"],
                tenant_id=world.tenant_id,
                value_int=1,
            )
        )
        await session.commit()

    # Not a GM: refused up front, whether or not it was needed.
    own = await _give(client, world, "pack", "alice", override=True)
    assert own.status_code == 403
    assert own.json()["type"] == "override-forbidden"
    assert await _count(world) == 0

    async with admin_session_factory() as session:
        session.add(
            CampaignGm(
                user_id=test_user_id, campaign_id=world.campaign_id, tenant_id=world.tenant_id
            )
        )
        await session.commit()

    refused = await _give(client, world, "pack", "brisk")
    assert refused.status_code == 409
    forced = await _give(client, world, "pack", "brisk", override=True)
    assert forced.status_code == 201, forced.text
    assert await _count(world) == 4
    async with admin_session_factory() as session:
        details = list(
            await session.scalars(
                select(AuditLog.detail).where(
                    AuditLog.tenant_id == world.tenant_id,
                    AuditLog.action == "item_instance.created",
                )
            )
        )
    assert len(details) == 4
    assert all(detail is not None and detail.endswith("; overridden") for detail in details)

    await _tear_down(world)


async def test_a_gm_can_give_a_pack_to_another_players_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)

    # Not yet a GM: Brisk is another player's.
    refused = await _give(client, world, "pack", "brisk")
    assert refused.status_code == 403
    assert await _count(world) == 0

    async with admin_session_factory() as session:
        session.add(
            CampaignGm(
                user_id=test_user_id, campaign_id=world.campaign_id, tenant_id=world.tenant_id
            )
        )
        await session.commit()

    given = await _give(client, world, "pack", "brisk")

    assert given.status_code == 201, given.text
    assert {row.owner for row in await _instances(world)} == {world.ids["brisk"]}

    await _tear_down(world)


async def test_a_pack_is_recorded_for_the_log_and_told_to_who_receives_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    async with admin_session_factory() as session:
        session.add(
            CampaignGm(
                user_id=test_user_id, campaign_id=world.campaign_id, tenant_id=world.tenant_id
            )
        )
        await session.commit()

    response = await _give(client, world, "pack", "brisk")

    assert response.status_code == 201, response.text
    made = {
        uuid.UUID(entry["item_instance"]["entity_id"])
        for entry in _flatten(response.json()["created"])
    }
    assert len(made) == 4
    async with admin_session_factory() as session:
        logged = (
            await session.execute(
                select(AuditLog.action, AuditLog.target_id, AuditLog.detail).where(
                    AuditLog.tenant_id == world.tenant_id
                )
            )
        ).all()
        received = (
            await session.execute(
                select(EntityChange.entity_id).where(
                    EntityChange.user_id == world.bob_user_id,
                    EntityChange.character_entity_id == world.ids["brisk"],
                    EntityChange.kind == "received",
                )
            )
        ).scalars()
        received_ids = set(received)
    assert {entry[1] for entry in logged if entry[0] == "item_instance.created"} == made
    assert len([entry for entry in logged if entry[0] == "item_instance.created"]) == 4
    assert all(
        "prototype=" in (entry[2] or "") and f"pack={world.ids['pack']}" in (entry[2] or "")
        for entry in logged
        if entry[0] == "item_instance.created"
    )
    assert received_ids == made

    await _tear_down(world)


def _flatten(created: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    for entry in created:
        flat.append(entry)
        flat.extend(_flatten(entry["children"]))
    return flat


async def test_someone_who_may_not_gets_no_answer_about_the_pack(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    broken = await _pack(world, "- 1 x Alms box")

    # Brisk is another player's, and the caller is no GM: forbidden before
    # anything is read, so what is wrong with the pack isn't revealed.
    for pack in (world.ids["secret"], broken, uuid.uuid4()):
        response = await _give(client, world, pack, "brisk")
        assert response.status_code == 403
        assert response.json()["type"] != "pack-list"

    await _tear_down(world)


async def test_a_line_without_a_link_refuses_the_whole_pack(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    pack = await _pack(world, "- 1 x [Backpack](backpack)\n  - 1 x Alms box\n- 1 x Censer")

    response = await _give(client, world, pack, "alice")

    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "pack-list"
    assert body["lines"] == [
        "“Alms box” has no link to an item",
        "“Censer” has no link to an item",
    ]
    assert await _count(world) == 0

    await _tear_down(world)


async def test_a_slug_that_is_not_an_item_refuses_the_whole_pack(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    async with admin_session_factory() as session:
        # A slug the tenant holds, but not for an item.
        being = Entity(tenant_id=world.tenant_id, name="Not an item")
        session.add(being)
        await session.flush()
        session.add(EntitySlug(entity_id=being.id, tenant_id=world.tenant_id, slug="not-an-item"))
        await session.commit()
    pack = await _pack(
        world, "- 1 x [Backpack](backpack)\n- 1 x [Gone](gone)\n- 1 x [Odd](not-an-item)"
    )

    response = await _give(client, world, pack, "alice")

    assert response.status_code == 422
    body = response.json()
    assert body["type"] == "pack-list"
    assert body["lines"] == [
        "“gone” is not an item of this tenant",
        "“not-an-item” is not an item of this tenant",
    ]
    assert await _count(world) == 0

    await _tear_down(world)


async def test_the_limits_refuse_the_whole_pack(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await _make_gm(world, test_user_id)

    too_many = await _give(
        client, world, await _pack(world, "- 1001 x [Rations](rations)"), "alice"
    )
    loose = await _pack(world, "- 51 x [Rope](rope)")
    for_a_being = await _give(client, world, loose, "alice")
    for_a_group = await _give(client, world, loose, "company")
    crowd = await _give(
        client,
        world,
        await _pack(world, "- 101 x [Backpack](backpack)\n  - 1 x [Torch](torch)"),
        "alice",
    )

    assert too_many.status_code == 422
    assert too_many.json()["lines"] == ["“Rations”: 1001 is more than 1000"]
    assert for_a_being.status_code == 201
    assert for_a_group.status_code == 422
    assert for_a_group.json()["lines"][0].startswith("“Rope”: a group holds 51 loose")
    assert crowd.status_code == 422
    assert crowd.json()["lines"][0].startswith("the list would create 202 instances")
    # Only the one for a being was given, and that is a single stack.
    assert await _count(world) == 1

    await _tear_down(world)


@pytest.mark.parametrize("what", ["an item with no list", "a private list", "not an item"])
async def test_a_pack_that_isnt_one_is_refused(
    client: AsyncClient, test_user_id: uuid.UUID, what: str
) -> None:
    world = await _world(test_user_id)
    pack: uuid.UUID = {
        "an item with no list": world.ids["backpack"],
        # The description is GM-only, so nobody's call reads it as a list.
        "a private list": world.ids["secret"],
        "not an item": world.ids["alice"],
    }[what]

    response = await _give(client, world, pack, "alice")

    assert response.status_code == 422
    assert response.json()["type"] == "not-a-pack"
    assert await _count(world) == 0

    await _tear_down(world)


async def test_a_list_nothing_nests_into_is_not_a_pack(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    # Indented with nothing above it, so mis-indented and ignored.
    pack = await _pack(world, "  - 1 x [Backpack](backpack)")

    response = await _give(client, world, pack, "alice")

    assert response.status_code == 422
    assert response.json()["type"] == "not-a-pack"

    await _tear_down(world)


async def test_an_owner_must_be_a_being_or_a_group_with_members(
    test_user_id: uuid.UUID,
) -> None:
    """Authorization admits only characters and groups with members today, so
    this guard can't be reached over HTTP; it holds if that is ever widened
    (a faction owning things, say)."""
    world = await _world(test_user_id)
    async with admin_session_factory() as session:
        # An empty group is only an entity, until it has a member.
        empty = Entity(tenant_id=world.tenant_id, name="Empty group")
        session.add(empty)
        await session.flush()
        for owner in (world.ids["backpack"], empty.id):
            with pytest.raises(InvalidPackOwnerError):
                await hand_out(
                    session,
                    tenant_id=world.tenant_id,
                    actor_id=test_user_id,
                    pack_id=world.ids["pack"],
                    owner_id=owner,
                    override=False,
                )
        await session.rollback()
    assert await _count(world) == 0

    await _tear_down(world)


async def test_the_contract_declares_both_answers(client: AsyncClient) -> None:
    """A dry run answers 200 and a real call 201, and a generated client has to know both."""
    document = (await client.get("/openapi.json")).json()
    operation = document["paths"]["/tenants/{tenant_id}/item-instances/from-pack"]["post"]

    assert {"200", "201"} <= set(operation["responses"])
    for status in ("200", "201"):
        schema = operation["responses"][status]["content"]["application/json"]["schema"]
        assert schema["$ref"].endswith("/PackGivenOut")
