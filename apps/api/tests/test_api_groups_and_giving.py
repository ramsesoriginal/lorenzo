"""Groups own things, and moving something isn't giving it away - ADR 0124."""

import uuid
from dataclasses import dataclass

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_plain_participant, make_tenant
from httpx import AsyncClient
from sqlalchemy import select
from test_api_held_by import _character, _instance

from lorenzo_api.models import (
    CampaignGm,
    Containment,
    Entity,
    EntityChange,
    GroupMember,
    Item,
    User,
)


@dataclass
class _Party:
    tenant_id: uuid.UUID
    pia_user_id: uuid.UUID
    ids: dict[str, uuid.UUID]


async def _make_party(test_user_id: uuid.UUID, *, alice_in_company: bool = True) -> _Party:
    """The caller plays Alice; another player plays Pia, in a campaign the
    caller isn't in. The caller is a plain participant - no Membership, so
    no OWNER bypass.

    Alice carries a Backpack with Pia's Potion (a stack of 3) in it. Pia has
    Alice's Ring in hand. The Company - Pia, and Alice unless told not -
    owns a Chest in no container, with the Company's Rope in it.
    """
    tenant_id = await make_tenant(test_user_id)
    await make_plain_participant(tenant_id, test_user_id)
    async with admin_session_factory() as session:
        alices = await make_campaign(session, tenant_id=tenant_id, name="Alice's")
        pias = await make_campaign(session, tenant_id=tenant_id, name="Pia's")
        await session.flush()
        pia_user = User(authgear_subject_id=f"pia-{uuid.uuid4()}")
        session.add(pia_user)
        await session.flush()
        alice = await _character(session, tenant_id, alices.id, test_user_id, "Alice")
        pia = await _character(session, tenant_id, pias.id, pia_user.id, "Pia")

        company = Entity(tenant_id=tenant_id, name="The Company")
        session.add(company)
        await session.flush()
        members = [pia, alice] if alice_in_company else [pia]
        session.add_all(
            GroupMember(group_entity_id=company.id, character_entity_id=m, tenant_id=tenant_id)
            for m in members
        )

        torch = Entity(tenant_id=tenant_id, name="Torch")
        session.add(torch)
        await session.flush()
        session.add(Item(entity_id=torch.id, tenant_id=tenant_id))

        ids = {
            "alice": alice,
            "pia": pia,
            "company": company.id,
            "pias_campaign": pias.id,
            "torch": torch.id,
        }
        ids["backpack"] = await _instance(
            session, tenant_id, "Backpack", owner=alice, container=alice
        )
        ids["potion"] = await _instance(
            session, tenant_id, "Potion", owner=pia, container=ids["backpack"]
        )
        (await session.get_one(Containment, ids["potion"])).quantity = 3
        ids["ring"] = await _instance(session, tenant_id, "Ring", owner=alice, container=pia)
        ids["chest"] = await _instance(session, tenant_id, "Chest", owner=company.id)
        ids["rope"] = await _instance(
            session, tenant_id, "Rope", owner=company.id, container=ids["chest"]
        )
        await session.commit()
    return _Party(tenant_id=tenant_id, pia_user_id=pia_user.id, ids=ids)


async def _tear_down(party: _Party) -> None:
    await delete_tenant(party.tenant_id)
    async with admin_session_factory() as session:
        await session.delete(await session.get_one(User, party.pia_user_id))
        await session.commit()


async def test_carrying_someone_elses_things_lets_you_move_them_not_give_them(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    party = await _make_party(test_user_id)
    t, ids = party.tenant_id, party.ids
    potion = f"/tenants/{t}/item-instances/{ids['potion']}"

    # Where it is: Alice holds it, so she may.
    moved = await client.put(f"{potion}/container", json={"container_entity_id": str(ids["alice"])})
    assert moved.status_code == 200
    split_in_place = await client.post(f"{potion}/split", json={"quantity": 1})
    assert split_in_place.status_code == 201

    # Who owns it: it's Pia's, so Alice may not.
    given = await client.put(f"{potion}/owner", json={"owner_character_id": str(ids["alice"])})
    assert given.status_code == 403
    assert given.json()["type"] == "item-not-yours-to-give"
    assert "only its owner or a GM can give it away" in given.json()["detail"]
    assert (await client.delete(f"{potion}/owner")).status_code == 403
    assert (await client.delete(potion)).status_code == 403
    split_off = await client.post(
        f"{potion}/split", json={"quantity": 1, "owner_character_id": str(ids["alice"])}
    )
    assert split_off.status_code == 403
    assigned = await client.post(
        f"/tenants/{t}/item-instances/bulk-assign",
        json=[{"entity_id": str(ids["potion"]), "owner_character_id": str(ids["alice"])}],
    )
    assert assigned.status_code == 200
    assert assigned.json()[0]["status"] == "error"
    assert assigned.json()[0]["problem"]["status"] == 403

    await _tear_down(party)


async def test_the_owner_gives_what_someone_else_carries(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    party = await _make_party(test_user_id)
    t, ids = party.tenant_id, party.ids

    given = await client.put(
        f"/tenants/{t}/item-instances/{ids['ring']}/owner",
        json={"owner_character_id": str(ids["pia"])},
    )

    assert given.status_code == 200
    assert given.json()["owner_entity_id"] == str(ids["pia"])

    await _tear_down(party)


async def test_members_see_move_and_give_what_their_group_owns(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    party = await _make_party(test_user_id)
    t, ids = party.tenant_id, party.ids
    rope = f"/tenants/{t}/item-instances/{ids['rope']}"

    board = await client.get(f"/tenants/{t}/item-instances/held-by/{ids['company']}")
    assert board.status_code == 200
    groups = {g["container"]["name"]: g for g in board.json()["groups"]}
    assert [i["title"] for i in groups["The Company"]["item_instances"]] == ["Chest"]
    assert [i["title"] for i in groups["Chest"]["item_instances"]] == ["Rope"]
    assert (await client.get(rope)).status_code == 200

    moved = await client.put(f"{rope}/container", json={"container_entity_id": str(ids["alice"])})
    assert moved.status_code == 200
    given = await client.put(f"{rope}/owner", json={"owner_character_id": str(ids["alice"])})
    assert given.status_code == 200

    # But making something new for the group is a GM's: a member's own
    # self-service is for their own character (ADR 0186).
    created = await client.post(
        f"/tenants/{t}/item-instances",
        json={"prototype_id": str(ids["torch"]), "owner_character_id": str(ids["company"])},
    )
    assert created.status_code == 403

    await _tear_down(party)


async def test_a_groups_things_are_out_of_reach_for_anyone_else(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    party = await _make_party(test_user_id, alice_in_company=False)
    t, ids = party.tenant_id, party.ids

    board = await client.get(f"/tenants/{t}/item-instances/held-by/{ids['company']}")
    assert board.status_code == 404
    given = await client.put(
        f"/tenants/{t}/item-instances/{ids['rope']}/owner",
        json={"owner_character_id": str(ids["alice"])},
    )
    assert given.status_code == 403
    assert given.json()["type"] == "item-instance-management-forbidden"

    await _tear_down(party)


async def test_a_gm_of_a_members_campaign_manages_a_groups_things(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    party = await _make_party(test_user_id, alice_in_company=False)
    t, ids = party.tenant_id, party.ids
    async with admin_session_factory() as session:
        session.add(CampaignGm(user_id=test_user_id, campaign_id=ids["pias_campaign"], tenant_id=t))
        await session.commit()

    board = await client.get(f"/tenants/{t}/item-instances/held-by/{ids['company']}")
    assert board.status_code == 200
    given = await client.put(
        f"/tenants/{t}/item-instances/{ids['rope']}/owner",
        json={"owner_character_id": str(ids["alice"])},
    )
    assert given.status_code == 200

    await _tear_down(party)


async def test_members_hear_when_their_groups_things_change(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    """ADR 0099's feed counts a group's members as holders (ADR 0124): Alice
    takes the Company's Rope out of its Chest, then keeps it, and Pia's
    player hears both. While it was still in the Company's Chest, the
    Company - so Pia - still held it."""
    party = await _make_party(test_user_id)
    t, ids = party.tenant_id, party.ids
    rope = f"/tenants/{t}/item-instances/{ids['rope']}"

    moved = await client.put(f"{rope}/container", json={"container_entity_id": str(ids["alice"])})
    assert moved.status_code == 200
    given = await client.put(f"{rope}/owner", json={"owner_character_id": str(ids["alice"])})
    assert given.status_code == 200

    async with admin_session_factory() as session:
        kinds = (
            await session.execute(
                select(EntityChange.kind).where(
                    EntityChange.user_id == party.pia_user_id,
                    EntityChange.entity_id == ids["rope"],
                )
            )
        ).scalars()
        assert sorted(kinds) == ["given_away", "moved"]

    await _tear_down(party)
