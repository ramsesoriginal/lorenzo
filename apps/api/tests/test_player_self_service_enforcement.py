"""Player self-service, enforced (RFC 0034, ADR 0186): what a player may make
for their own character from the public catalog, and when it is switched off.
"""

import uuid
from dataclasses import dataclass, field

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from httpx import AsyncClient, Response
from sqlalchemy import select
from test_api_give_pack import _describe
from test_api_held_by import _character

from lorenzo_api.models import (
    Campaign,
    CampaignGm,
    CharacterPlayer,
    Containment,
    Entity,
    EntitySlug,
    GroupMember,
    Item,
    ItemInstance,
    Ownership,
    Player,
    User,
)


class _Unset:
    """override=None means 'clear it', so 'leave it' needs a value of its own."""


_UNSET = _Unset()
PACK = "- 1 x [Backpack](backpack)\n  - 2 x [Torch](torch)"


@dataclass
class _World:
    tenant_id: uuid.UUID
    campaign_id: uuid.UUID
    alice: uuid.UUID
    seat: uuid.UUID
    ids: dict[str, uuid.UUID] = field(default_factory=dict)
    extra_users: list[uuid.UUID] = field(default_factory=list)


async def _world(owner_id: uuid.UUID, caller_id: uuid.UUID) -> _World:
    """A tenant owned by someone else, so the caller is only a player: they
    play Alice in "Table". The catalog has a public Sword, a private Vault
    key, a public Backpack and Torch, a public pack, and a private pack."""
    tenant_id = await make_tenant(owner_id)
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=tenant_id, name="Table")
        alice = await _character(session, tenant_id, campaign.id, caller_id, "Alice")
        seat = await session.scalar(
            select(Player.id).where(Player.campaign_id == campaign.id, Player.user_id == caller_id)
        )
        assert seat is not None
        world = _World(tenant_id, campaign.id, alice, seat)

        async def item(name: str, slug: str, *, public: bool) -> uuid.UUID:
            entity = Entity(tenant_id=tenant_id, name=name)
            session.add(entity)
            await session.flush()
            session.add(Item(entity_id=entity.id, tenant_id=tenant_id, in_public_catalog=public))
            session.add(EntitySlug(entity_id=entity.id, tenant_id=tenant_id, slug=slug))
            await session.flush()
            return entity.id

        world.ids["sword"] = await item("Sword", "sword", public=True)
        world.ids["key"] = await item("Vault key", "vault-key", public=False)
        world.ids["backpack"] = await item("Backpack", "backpack", public=True)
        world.ids["torch"] = await item("Torch", "torch", public=True)
        world.ids["pack"] = await item("Explorer's pack", "explorers-pack", public=True)
        world.ids["secret-pack"] = await item("Secret pack", "secret-pack", public=False)
        world.ids["mixed-pack"] = await item("Mixed pack", "mixed-pack", public=True)
        world.ids["key2"] = await item("Another key", "another-key", public=False)
        for pack, text in (
            ("pack", PACK),
            ("secret-pack", PACK),
            ("mixed-pack", "- 1 x [Backpack](backpack)\n  - 1 x [Another key](another-key)"),
        ):
            await _describe(session, tenant_id, world.ids[pack], text, public=True)
        await session.commit()
    return world


async def _tear_down(world: _World) -> None:
    await delete_tenant(world.tenant_id)
    async with admin_session_factory() as session:
        for user_id in world.extra_users:
            await session.delete(await session.get_one(User, user_id))
        await session.commit()


async def _make(client: AsyncClient, world: _World, prototype: str, **extra: object) -> Response:
    return await client.post(
        f"/tenants/{world.tenant_id}/item-instances",
        json={
            "prototype_id": str(world.ids[prototype]),
            "owner_character_id": str(extra.pop("owner", world.alice)),
            **extra,
        },
    )


async def _set_campaign(
    world: _World, *, on: bool | None = None, override: bool | None | _Unset = _UNSET
) -> None:
    async with admin_session_factory() as session:
        if on is not None:
            campaign = await session.get_one(Campaign, world.campaign_id)
            campaign.player_self_service = on
        if not isinstance(override, _Unset):
            seat = await session.get_one(Player, world.seat)
            seat.self_service = override
        await session.commit()


async def test_a_player_makes_a_public_item_for_their_own_character(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    owner = uuid.uuid4()
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"owner-{owner}")
        session.add(user)
        await session.commit()
        owner_id = user.id
    world = await _world(owner_id, test_user_id)
    world.extra_users.append(owner_id)

    response = await _make(client, world, "sword", name="Aldric's blade")

    assert response.status_code == 201, response.text
    made = response.json()
    assert made["owner_entity_id"] == str(world.alice)
    assert made["container_entity_id"] is None
    assert made["title"] == "Aldric's blade"

    await _tear_down(world)


async def _owned_world(test_user_id: uuid.UUID) -> _World:
    async with admin_session_factory() as session:
        user = User(authgear_subject_id=f"owner-{uuid.uuid4()}")
        session.add(user)
        await session.commit()
        owner_id = user.id
    world = await _world(owner_id, test_user_id)
    world.extra_users.append(owner_id)
    return world


async def test_a_private_item_is_answered_like_an_unknown_one(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)

    private = await _make(client, world, "key")
    unknown = await client.post(
        f"/tenants/{world.tenant_id}/item-instances",
        json={"prototype_id": str(uuid.uuid4()), "owner_character_id": str(world.alice)},
    )

    assert private.status_code == unknown.status_code == 422
    assert private.json()["type"] == unknown.json()["type"] == "invalid-item-prototype"

    await _tear_down(world)


async def test_the_campaign_switch_and_the_players_override(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)

    await _set_campaign(world, on=False)
    off = await _make(client, world, "sword")
    assert off.status_code == 403
    assert off.json()["type"] == "self-service-disabled"

    await _set_campaign(world, override=True)  # campaign off, this player allowed
    assert (await _make(client, world, "sword")).status_code == 201

    await _set_campaign(world, on=True, override=False)  # campaign on, this player forbidden
    forbidden = await _make(client, world, "sword")
    assert forbidden.status_code == 403
    assert forbidden.json()["type"] == "self-service-disabled"

    await _set_campaign(world, override=None)  # back to following the campaign
    assert (await _make(client, world, "sword")).status_code == 201

    await _tear_down(world)


async def _second_seat(world: _World, caller_id: uuid.UUID, *, on: bool) -> uuid.UUID:
    """Alice also plays in a second campaign, through the caller's seat there."""
    async with admin_session_factory() as session:
        campaign = await make_campaign(session, tenant_id=world.tenant_id, name="Other table")
        campaign.player_self_service = on
        seat = Player(user_id=caller_id, campaign_id=campaign.id, tenant_id=world.tenant_id)
        session.add(seat)
        await session.flush()
        session.add(
            CharacterPlayer(
                character_entity_id=world.alice, player_id=seat.id, tenant_id=world.tenant_id
            )
        )
        await session.commit()
        return seat.id


async def test_any_enabled_seat_of_the_callers_is_enough_for_the_whole_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)
    await _set_campaign(world, on=False)

    assert (await _make(client, world, "sword")).status_code == 403
    await _second_seat(world, test_user_id, on=True)
    assert (await _make(client, world, "sword")).status_code == 201

    await _tear_down(world)


async def test_every_seat_off_is_off(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    world = await _owned_world(test_user_id)
    await _set_campaign(world, on=False)
    await _second_seat(world, test_user_id, on=False)

    response = await _make(client, world, "sword")

    assert response.status_code == 403
    assert response.json()["type"] == "self-service-disabled"

    await _tear_down(world)


async def test_someone_elses_enabled_seat_grants_the_caller_nothing(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)
    await _set_campaign(world, on=False)
    # A co-pilot of Alice's, in a campaign that has it on.
    async with admin_session_factory() as session:
        pia = User(authgear_subject_id=f"pia-{uuid.uuid4()}")
        session.add(pia)
        await session.flush()
        world.extra_users.append(pia.id)
        campaign = await make_campaign(session, tenant_id=world.tenant_id, name="Pia's table")
        seat = Player(user_id=pia.id, campaign_id=campaign.id, tenant_id=world.tenant_id)
        session.add(seat)
        await session.flush()
        session.add(
            CharacterPlayer(
                character_entity_id=world.alice, player_id=seat.id, tenant_id=world.tenant_id
            )
        )
        await session.commit()

    assert (await _make(client, world, "sword")).status_code == 403

    await _tear_down(world)


async def test_no_slug_and_no_container_but_the_characters_own(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)

    slug = await _make(client, world, "sword", slug="my-sword")
    assert slug.status_code == 403

    hands = await _make(client, world, "sword", container_entity_id=str(world.alice))
    assert hands.status_code == 403

    # Something that isn't the character's.
    async with admin_session_factory() as session:
        vault = Entity(tenant_id=world.tenant_id, name="Vault")
        session.add(vault)
        await session.flush()
        session.add(ItemInstance(entity_id=vault.id, tenant_id=world.tenant_id))
        await session.commit()
        vault_id = vault.id
    elsewhere = await _make(client, world, "torch", container_entity_id=str(vault_id), quantity=3)
    assert elsewhere.status_code == 403

    # A sack the character owns.
    sack = await _make(client, world, "backpack", name="Camp supplies")
    assert sack.status_code == 201
    inside = await _make(
        client,
        world,
        "torch",
        container_entity_id=sack.json()["entity_id"],
        quantity=3,
    )
    assert inside.status_code == 201, inside.text
    assert inside.json()["quantity"] == 3

    await _tear_down(world)


async def test_a_group_is_not_an_owner_for_self_service(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)
    async with admin_session_factory() as session:
        company = Entity(tenant_id=world.tenant_id, name="The Company")
        session.add(company)
        await session.flush()
        session.add(
            GroupMember(
                group_entity_id=company.id,
                character_entity_id=world.alice,
                tenant_id=world.tenant_id,
            )
        )
        await session.commit()
        company_id = company.id

    response = await _make(client, world, "sword", owner=company_id)

    assert response.status_code == 403
    assert response.json()["type"] == "item-instance-management-forbidden"

    await _tear_down(world)


async def test_a_gm_who_also_plays_is_judged_as_a_gm(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)
    await _set_campaign(world, on=False)
    async with admin_session_factory() as session:
        session.add(
            CampaignGm(
                user_id=test_user_id, campaign_id=world.campaign_id, tenant_id=world.tenant_id
            )
        )
        await session.commit()

    # Switched off, a private item, a slug: a manager's call, none of it a limit.
    response = await _make(client, world, "key", slug="the-key")

    assert response.status_code == 201, response.text

    await _tear_down(world)


async def _instances(world: _World) -> int:
    async with admin_session_factory() as session:
        rows = await session.scalars(
            select(Ownership.owned_entity_id).where(Ownership.tenant_id == world.tenant_id)
        )
        return len(rows.all())


async def test_a_player_may_give_themselves_a_public_pack_and_it_is_equipped(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)

    response = await client.post(
        f"/tenants/{world.tenant_id}/item-instances/from-pack",
        json={"pack_id": str(world.ids["pack"]), "owner_entity_id": str(world.alice)},
    )

    assert response.status_code == 201, response.text
    assert await _instances(world) == 2
    async with admin_session_factory() as session:
        hands = await session.scalars(
            select(Containment.child_entity_id).where(Containment.parent_entity_id == world.alice)
        )
        assert len(hands.all()) == 1

    await _tear_down(world)


async def test_a_pack_must_be_public_and_so_must_everything_in_it(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)
    url = f"/tenants/{world.tenant_id}/item-instances/from-pack"

    for pack in ("secret-pack", "mixed-pack"):
        response = await client.post(
            url, json={"pack_id": str(world.ids[pack]), "owner_entity_id": str(world.alice)}
        )
        assert response.status_code == 422, (pack, response.text)
    assert await _instances(world) == 0

    await _tear_down(world)


async def test_a_pack_follows_the_switch_and_refuses_a_group(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _owned_world(test_user_id)
    url = f"/tenants/{world.tenant_id}/item-instances/from-pack"
    body = {"pack_id": str(world.ids["pack"]), "owner_entity_id": str(world.alice)}

    await _set_campaign(world, on=False)
    off = await client.post(url, json=body)
    assert off.status_code == 403
    assert off.json()["type"] == "self-service-disabled"
    assert await _instances(world) == 0

    await _tear_down(world)


async def test_me_says_whether_each_seat_may(client: AsyncClient, test_user_id: uuid.UUID) -> None:
    world = await _owned_world(test_user_id)
    await _set_campaign(world, on=False)

    async def effective() -> dict[str, bool]:
        players = (await client.get("/me")).json()["players"]
        return {p["campaign_id"]: p["self_service_effective"] for p in players}

    assert (await effective())[str(world.campaign_id)] is False
    await _set_campaign(world, override=True)
    assert (await effective())[str(world.campaign_id)] is True

    await _tear_down(world)
