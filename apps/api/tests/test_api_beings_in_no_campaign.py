"""A being or group in no campaign: the tenant's GMs and administrators stand in for its GM
(ADR 0151), so items and packs can be given to any being."""

import uuid

from _admin_db import admin_session_factory
from conftest import make_being, make_campaign, make_character
from httpx import AsyncClient
from sqlalchemy import select
from test_api_give_pack import _count, _give, _instances, _tear_down, _world
from test_api_held_by import _instance

from lorenzo_api.models import (
    CampaignGm,
    Containment,
    Entity,
    GroupMember,
    ItemInstance,
    Membership,
    MembershipRole,
    Ownership,
)


async def _npcs(world_id: uuid.UUID) -> dict[str, uuid.UUID]:
    """Gruk, a bare being; Drifter, a character nobody plays; and the Drifters, a group of that
    one character: none of them is in any campaign."""
    async with admin_session_factory() as session:
        gruk = await make_being(session, tenant_id=world_id, name="Gruk")
        drifter = await make_character(session, tenant_id=world_id, name="Drifter")
        drifters = Entity(tenant_id=world_id, name="The Drifters")
        session.add(drifters)
        await session.flush()
        session.add(
            GroupMember(
                group_entity_id=drifters.id,
                character_entity_id=drifter.entity_id,
                tenant_id=world_id,
            )
        )
        await session.commit()
        return {"gruk": gruk.entity_id, "drifter": drifter.entity_id, "drifters": drifters.id}


async def _become_gm(world_tenant: uuid.UUID, campaign: uuid.UUID, user: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        session.add(CampaignGm(user_id=user, campaign_id=campaign, tenant_id=world_tenant))
        await session.commit()


async def test_a_player_may_not_give_a_pack_or_make_an_item_for_a_being_in_no_campaign(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    world.ids |= await _npcs(world.tenant_id)

    pack = await _give(client, world, "pack", "gruk")
    item = await client.post(
        f"/tenants/{world.tenant_id}/item-instances",
        json={"prototype_id": str(world.ids["rope"]), "owner_character_id": str(world.ids["gruk"])},
    )

    assert pack.status_code == 403
    assert item.status_code == 403
    assert await _count(world) == 0

    await _tear_down(world)


async def test_a_gm_gives_a_pack_to_a_bare_being_into_its_hands(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    world.ids |= await _npcs(world.tenant_id)
    await _become_gm(world.tenant_id, world.campaign_id, test_user_id)
    gruk = world.ids["gruk"]

    response = await _give(client, world, "pack", "gruk")

    assert response.status_code == 201, response.text
    rows = {row.name: row for row in await _instances(world)}
    assert {row.owner for row in rows.values()} == {gruk}
    assert rows["Backpack"].parent == gruk
    assert rows["Rope"].parent == gruk
    assert (rows["Rope"].quantity, rows["Rations"].quantity) == (2, 5)

    await _tear_down(world)


async def test_a_gm_makes_an_item_for_a_bare_being_and_may_override_for_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    world.ids |= await _npcs(world.tenant_id)
    gruk = world.ids["gruk"]
    body = {"prototype_id": str(world.ids["rope"]), "owner_character_id": str(gruk)}
    path = f"/tenants/{world.tenant_id}/item-instances"

    before = await client.post(path, json=body)
    await _become_gm(world.tenant_id, world.campaign_id, test_user_id)
    made = await client.post(path, json=body)
    forced = await client.post(path, json={**body, "override": True})

    assert before.status_code == 403
    assert made.status_code == 201, made.text
    assert made.json()["owner_entity_id"] == str(gruk)
    assert forced.status_code == 201, forced.text

    await _tear_down(world)


async def test_a_tenant_administrator_stands_in_too(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    world.ids |= await _npcs(world.tenant_id)
    async with admin_session_factory() as session:
        session.add(
            Membership(tenant_id=world.tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        await session.commit()

    response = await _give(client, world, "pack", "gruk")

    assert response.status_code == 201, response.text

    await _tear_down(world)


async def test_a_character_nobody_plays_and_a_group_of_such_are_covered_too(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    world.ids |= await _npcs(world.tenant_id)
    await _become_gm(world.tenant_id, world.campaign_id, test_user_id)

    to_character = await _give(client, world, "pack", "drifter")
    to_group = await _give(client, world, "pack", "drifters")

    assert to_character.status_code == 201, to_character.text
    assert to_group.status_code == 201, to_group.text
    owners = {row.owner for row in await _instances(world)}
    assert owners == {world.ids["drifter"], world.ids["drifters"]}

    await _tear_down(world)


async def test_a_being_in_a_campaign_keeps_its_own_gm_not_any_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """The GM of a campaign Alice doesn't play in can't act for her: only a being in *no*
    campaign falls back to the tenant's GMs."""
    world = await _world(test_user_id)
    async with admin_session_factory() as session:
        elsewhere = await make_campaign(session, tenant_id=world.tenant_id, name="Elsewhere")
        await session.commit()
        elsewhere_id = elsewhere.id
    await _become_gm(world.tenant_id, elsewhere_id, test_user_id)

    # Brisk is Bob's, in the campaign the caller does not GM.
    refused = await _give(client, world, "pack", "brisk")
    # Alice is the caller's own: always allowed.
    own = await _give(client, world, "pack", "alice")

    assert refused.status_code == 403
    assert own.status_code == 201
    assert {row.owner for row in await _instances(world)} == {world.ids["alice"]}

    await _tear_down(world)


async def test_something_that_is_neither_a_being_nor_a_group_still_has_nobody_with_standing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    await _become_gm(world.tenant_id, world.campaign_id, test_user_id)
    async with admin_session_factory() as session:
        session.add(
            Membership(tenant_id=world.tenant_id, user_id=test_user_id, role=MembershipRole.OWNER)
        )
        await session.commit()

    # A backpack (an item entity) as the owner.
    response = await _give(client, world, "pack", "backpack")

    assert response.status_code == 403
    assert await _count(world) == 0

    await _tear_down(world)


async def test_what_a_bare_being_holds_can_be_taken_back_by_a_gm_and_not_by_a_player(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    world.ids |= await _npcs(world.tenant_id)
    gruk, alice = world.ids["gruk"], world.ids["alice"]
    async with admin_session_factory() as session:
        club = await _instance(session, world.tenant_id, "Club", owner=gruk)
        await session.commit()
    path = f"/tenants/{world.tenant_id}/item-instances/{club}"

    as_player = await client.put(f"{path}/owner", json={"owner_character_id": str(alice)})
    await _become_gm(world.tenant_id, world.campaign_id, test_user_id)
    as_gm = await client.put(f"{path}/owner", json={"owner_character_id": str(alice)})

    assert as_player.status_code == 403
    assert as_gm.status_code == 200, as_gm.text
    async with admin_session_factory() as session:
        assert (
            await session.scalar(
                select(Ownership.owner_character_id).where(Ownership.owned_entity_id == club)
            )
            == alice
        )

    await _tear_down(world)


async def test_a_player_gives_their_own_item_to_any_being(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """Giving an existing item never needed standing over the recipient: this holds before and
    after ADR 0151."""
    world = await _world(test_user_id)
    world.ids |= await _npcs(world.tenant_id)
    async with admin_session_factory() as session:
        sword = await _instance(
            session,
            world.tenant_id,
            "Sword",
            owner=world.ids["alice"],
            container=world.ids["alice"],
        )
        await session.commit()

    gave = await client.put(
        f"/tenants/{world.tenant_id}/item-instances/{sword}/owner",
        json={"owner_character_id": str(world.ids["gruk"]), "move_to_owner": True},
    )

    assert gave.status_code == 200, gave.text
    async with admin_session_factory() as session:
        assert (
            await session.scalar(
                select(Ownership.owner_character_id).where(Ownership.owned_entity_id == sword)
            )
            == world.ids["gruk"]
        )
        assert (
            await session.scalar(
                select(Containment.parent_entity_id).where(Containment.child_entity_id == sword)
            )
            == world.ids["gruk"]
        )
        assert await session.get(ItemInstance, sword) is not None

    await _tear_down(world)
