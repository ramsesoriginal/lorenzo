"""A GM's view of the beings in no campaign is a per-tenant setting (ADR 0152): who has standing,
for reading and for acting, with the setting on and off."""

import uuid
from dataclasses import dataclass

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_character, make_tenant
from httpx import AsyncClient, Response
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from test_api_give_pack import _count, _give, _World, _world
from test_api_give_pack import _tear_down as tear_down_world
from test_api_held_by import _character, _instance

from lorenzo_api.campaign_access import campaignless_holders_for, can_manage_owner
from lorenzo_api.information_visibility import (
    resolve_information_visibility,
    visible_information_clause,
)
from lorenzo_api.models import (
    AuditLog,
    Being,
    CampaignGm,
    Containment,
    Entity,
    GroupMember,
    Information,
    Membership,
    MembershipRole,
    Tenant,
    User,
)

GMS = ("gm_a", "gm_a2", "gm_b", "gm_ab")


@dataclass
class _Scene:
    tenant_id: uuid.UUID
    users: dict[str, uuid.UUID]
    ids: dict[str, uuid.UUID]
    info: dict[str, uuid.UUID]


def _user(label: str) -> User:
    return User(authgear_subject_id=f"authgear|npc-sharing-{label}-{uuid.uuid4()}")


async def _being(
    session: AsyncSession, tenant_id: uuid.UUID, name: str, author: uuid.UUID | None
) -> uuid.UUID:
    entity = Entity(tenant_id=tenant_id, name=name, created_by=author)
    session.add(entity)
    await session.flush()
    session.add(Being(entity_id=entity.id, tenant_id=tenant_id))
    await session.flush()
    return entity.id


async def _scene() -> _Scene:
    """Two campaigns, A and B, and the people around them:

    - gm_a and gm_a2 GM A (co-GMs); gm_b GMs B; gm_ab GMs both; plain GMs nothing; orga is a
      tenant organiser.
    - pc_a has a seat in A, pc_b one in B. A room holds pc_a and a being authored by gm_b.
    - The beings in no campaign: one authored by each of gm_a, gm_a2, gm_b, gm_ab and orga, one by
      nobody, a character nobody plays (drifter) and a group of it (the drifters), both gm_a's.
    - A plain entity that is neither a being nor a group, also gm_a's, and a Club owned by npc_a.
    """
    async with admin_session_factory() as session:
        tenant = Tenant()
        session.add(tenant)
        people = {
            label: _user(label)
            for label in (*GMS, "plain", "orga", "player_a", "player_b", "ghost")
        }
        session.add_all(people.values())
        await session.flush()
        t = tenant.id
        users = {label: user.id for label, user in people.items()}
        session.add(Membership(tenant_id=t, user_id=users["orga"], role=MembershipRole.ORGA))
        camp_a = await make_campaign(session, tenant_id=t, name="A")
        camp_b = await make_campaign(session, tenant_id=t, name="B")
        for who, campaign in (
            ("gm_a", camp_a),
            ("gm_a2", camp_a),
            ("gm_b", camp_b),
            ("gm_ab", camp_a),
            ("gm_ab", camp_b),
        ):
            session.add(CampaignGm(user_id=users[who], campaign_id=campaign.id, tenant_id=t))
        ids = {
            "camp_a": camp_a.id,
            "camp_b": camp_b.id,
            "pc_a": await _character(session, t, camp_a.id, users["player_a"], "Pia"),
            "pc_b": await _character(session, t, camp_b.id, users["player_b"], "Brisk"),
        }
        for name, author in (
            ("npc_a", "gm_a"),
            ("npc_a2", "gm_a2"),
            ("npc_b", "gm_b"),
            ("npc_ab", "gm_ab"),
            ("npc_orga", "orga"),
            ("npc_scene", "gm_b"),
            ("npc_ghost", "ghost"),
        ):
            ids[name] = await _being(session, t, name, users[author])
        ids["npc_none"] = await _being(session, t, "npc_none", None)
        drifter = await make_character(session, tenant_id=t, name="Drifter")
        await session.execute(
            update(Entity).where(Entity.id == drifter.entity_id).values(created_by=users["gm_a"])
        )
        ids["drifter"] = drifter.entity_id
        drifters = Entity(tenant_id=t, name="The Drifters", created_by=users["gm_a"])
        thing = Entity(tenant_id=t, name="A thing", created_by=users["gm_a"])
        room = Entity(tenant_id=t, name="Room")
        session.add_all([drifters, thing, room])
        await session.flush()
        session.add(
            GroupMember(
                group_entity_id=drifters.id, character_entity_id=drifter.entity_id, tenant_id=t
            )
        )
        ids |= {"drifters": drifters.id, "thing": thing.id, "room": room.id}
        for child in ("pc_a", "npc_scene"):
            session.add(
                Containment(child_entity_id=ids[child], parent_entity_id=room.id, tenant_id=t)
            )
        ids["club"] = await _instance(session, t, "Club", owner=ids["npc_a"])
        info: dict[str, uuid.UUID] = {}
        for name in ("npc_a", "npc_b", "npc_scene"):
            row = Information(
                tenant_id=t,
                entity_id=ids[name],
                title="Secret",
                type="description",
                is_public=False,
            )
            session.add(row)
            await session.flush()
            info[name] = row.id
        await session.commit()
    return _Scene(t, users, ids, info)


async def _tear_down(scene: _Scene) -> None:
    await delete_tenant(scene.tenant_id)
    async with admin_session_factory() as session:
        for user_id in scene.users.values():
            user = await session.get(User, user_id)
            if user is not None:
                await session.delete(user)
        await session.commit()


async def _share(tenant_id: uuid.UUID, shared: bool) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant).where(Tenant.id == tenant_id).values(npcs_shared_with_gms=shared)
        )
        await session.commit()


async def _holders(scene: _Scene, who: str) -> set[str]:
    names = {v: k for k, v in scene.ids.items()}
    async with admin_session_factory() as session:
        found = await campaignless_holders_for(
            session, user_id=scene.users[who], tenant_id=scene.tenant_id
        )
    return {names[entity_id] for entity_id in found}


EVERYONE = {
    "npc_a",
    "npc_a2",
    "npc_b",
    "npc_ab",
    "npc_orga",
    "npc_scene",
    "npc_ghost",
    "npc_none",
    "drifter",
    "drifters",
}


async def test_with_the_setting_on_every_gm_has_every_being_in_no_campaign() -> None:
    scene = await _scene()

    for who in GMS:
        found = await _holders(scene, who)
        assert found == EVERYONE, who
        # A being with a seat is in a campaign; a thing that is no being or group never is.
        assert not found & {"pc_a", "pc_b", "thing", "room", "club"}

    await _tear_down(scene)


async def test_only_a_gm_is_a_gm_here_whatever_else_they_are() -> None:
    scene = await _scene()

    assert await _holders(scene, "plain") == set()
    assert await _holders(scene, "orga") == set()
    assert await _holders(scene, "player_a") == set()

    await _tear_down(scene)


async def test_with_the_setting_off_a_gm_has_what_they_and_their_co_gms_authored() -> None:
    scene = await _scene()
    await _share(scene.tenant_id, False)

    assert await _holders(scene, "gm_a") == {"npc_a", "npc_a2", "npc_ab", "drifter", "drifters"}
    assert await _holders(scene, "gm_a2") == {"npc_a", "npc_a2", "npc_ab", "drifter", "drifters"}
    # B's only GMs besides gm_ab, who authored npc_ab, are gm_b and gm_ab themselves.
    assert await _holders(scene, "gm_b") == {"npc_b", "npc_ab", "npc_scene"}
    # gm_ab GMs both campaigns, so gm_ab is a co-GM of everyone, and everyone of gm_ab.
    assert await _holders(scene, "gm_ab") == {
        "npc_a",
        "npc_a2",
        "npc_b",
        "npc_ab",
        "npc_scene",
        "drifter",
        "drifters",
    }

    await _tear_down(scene)


async def test_what_an_administrator_or_nobody_authored_is_no_gms_with_the_setting_off() -> None:
    scene = await _scene()
    await _share(scene.tenant_id, False)

    for who in GMS:
        assert not await _holders(scene, who) & {"npc_orga", "npc_none", "npc_ghost"}, who

    await _tear_down(scene)


async def test_a_deleted_authors_being_is_unauthored() -> None:
    scene = await _scene()
    await _share(scene.tenant_id, False)
    async with admin_session_factory() as session:
        # The author is a GM of A, so while they are one, gm_a is their co-GM.
        session.add(
            CampaignGm(
                user_id=scene.users["ghost"],
                campaign_id=scene.ids["camp_a"],
                tenant_id=scene.tenant_id,
            )
        )
        await session.commit()
    assert "npc_ghost" in await _holders(scene, "gm_a")

    async with admin_session_factory() as session:
        # The account goes: the being stays, with no author.
        await session.delete(await session.get_one(User, scene.users["ghost"]))
        await session.commit()
        assert (await session.get_one(Entity, scene.ids["npc_ghost"])).created_by is None

    assert "npc_ghost" not in await _holders(scene, "gm_a")
    await _share(scene.tenant_id, True)
    assert "npc_ghost" in await _holders(scene, "gm_a")

    await _tear_down(scene)


async def test_among_narrows_the_answer_to_those_beings() -> None:
    scene = await _scene()
    await _share(scene.tenant_id, False)
    ids = scene.ids
    async with admin_session_factory() as session:
        found = await campaignless_holders_for(
            session,
            user_id=scene.users["gm_a"],
            tenant_id=scene.tenant_id,
            among={ids["npc_a"], ids["npc_b"], ids["pc_a"]},
        )

    assert found == {ids["npc_a"]}

    await _tear_down(scene)


@pytest.mark.parametrize("shared", [True, False])
async def test_acting_and_reading_agree_for_every_being_and_gm(shared: bool) -> None:
    """Standing to act is the same set as standing to read, but for a scene."""
    scene = await _scene()
    await _share(scene.tenant_id, shared)
    campaignless = {
        name: scene.ids[name]
        for name in (
            "npc_a",
            "npc_a2",
            "npc_b",
            "npc_ab",
            "npc_orga",
            "npc_scene",
            "npc_ghost",
            "npc_none",
            "drifter",
            "drifters",
        )
    }

    async with admin_session_factory() as session:
        for who in (*GMS, "plain"):
            holders = await campaignless_holders_for(
                session, user_id=scene.users[who], tenant_id=scene.tenant_id
            )
            for name, entity_id in campaignless.items():
                acts = await can_manage_owner(
                    session,
                    user_id=scene.users[who],
                    owner_entity_id=entity_id,
                    tenant_id=scene.tenant_id,
                )
                assert acts == (entity_id in holders), (who, name, shared)

    await _tear_down(scene)


async def test_an_administrator_always_acts_for_a_being_in_no_campaign() -> None:
    scene = await _scene()
    await _share(scene.tenant_id, False)

    async with admin_session_factory() as session:
        for name in ("npc_b", "npc_none", "drifters"):
            assert await can_manage_owner(
                session,
                user_id=scene.users["orga"],
                owner_entity_id=scene.ids[name],
                tenant_id=scene.tenant_id,
            ), name
        # But not for what is neither a being nor a group.
        assert not await can_manage_owner(
            session,
            user_id=scene.users["orga"],
            owner_entity_id=scene.ids["thing"],
            tenant_id=scene.tenant_id,
        )

    await _tear_down(scene)


async def test_a_being_with_a_campaign_keeps_its_own_gms_whatever_the_setting() -> None:
    scene = await _scene()

    for shared in (True, False):
        await _share(scene.tenant_id, shared)
        async with admin_session_factory() as session:
            for who, expected in (("gm_a", True), ("gm_b", False), ("plain", False)):
                assert (
                    await can_manage_owner(
                        session,
                        user_id=scene.users[who],
                        owner_entity_id=scene.ids["pc_a"],
                        tenant_id=scene.tenant_id,
                    )
                    is expected
                ), (who, shared)

    await _tear_down(scene)


async def _reach(scene: _Scene, who: str) -> set[str]:
    names = {v: k for k, v in scene.ids.items()}
    async with admin_session_factory() as session:
        visibility = await resolve_information_visibility(
            session, user_id=scene.users[who], tenant_id=scene.tenant_id
        )
        return {names[i] for i in visibility.gm_reachable_entity_ids if i in names}


async def test_reading_follows_the_same_set_and_the_beings_holdings() -> None:
    scene = await _scene()

    # On: gm_b reaches npc_a, and the Club npc_a owns, though it is gm_a's.
    on = await _reach(scene, "gm_b")
    assert {"npc_a", "club", "npc_a2", "drifters"} <= on
    await _share(scene.tenant_id, False)
    off = await _reach(scene, "gm_b")
    assert "npc_a" not in off and "club" not in off
    assert {"npc_b", "npc_scene"} <= off

    await _tear_down(scene)


async def test_a_scene_still_gives_reading_but_never_standing_with_the_setting_off() -> None:
    """gm_a's player character stands in a room with a being gm_b authored."""
    scene = await _scene()
    await _share(scene.tenant_id, False)
    npc_scene = scene.ids["npc_scene"]

    assert "npc_scene" in await _reach(scene, "gm_a")
    assert "npc_scene" not in await _holders(scene, "gm_a")
    async with admin_session_factory() as session:
        assert not await can_manage_owner(
            session,
            user_id=scene.users["gm_a"],
            owner_entity_id=npc_scene,
            tenant_id=scene.tenant_id,
        )

    await _tear_down(scene)


async def test_gm_only_information_follows_reach() -> None:
    scene = await _scene()

    async def seen(who: str) -> set[uuid.UUID]:
        async with admin_session_factory() as session:
            visibility = await resolve_information_visibility(
                session, user_id=scene.users[who], tenant_id=scene.tenant_id
            )
            rows = await session.scalars(
                select(Information.id).where(
                    Information.tenant_id == scene.tenant_id, visible_information_clause(visibility)
                )
            )
            return set(rows)

    info = scene.info
    # On: any GM reads the notes on any of them.
    assert {info["npc_a"], info["npc_b"], info["npc_scene"]} <= await seen("gm_b")
    await _share(scene.tenant_id, False)
    # Off: gm_b authored npc_b and npc_scene, not npc_a.
    assert info["npc_a"] not in await seen("gm_b")
    assert {info["npc_b"], info["npc_scene"]} <= await seen("gm_b")
    # gm_a reaches the notes on npc_a (its own) and npc_scene (in a scene of theirs), not npc_b's.
    assert {info["npc_a"], info["npc_scene"]} <= await seen("gm_a")
    assert info["npc_b"] not in await seen("gm_a")

    await _tear_down(scene)


async def test_the_setting_is_read_and_changed_through_the_tenant(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    tenant_id = await make_tenant(test_user_id)
    path = f"/tenants/{tenant_id}"

    assert (await client.get(path)).json()["npcs_shared_with_gms"] is True
    off = await client.patch(path, json={"npcs_shared_with_gms": False})
    unrelated = await client.patch(path, json={"description": "A world"})
    on = await client.patch(path, json={"npcs_shared_with_gms": True})

    assert off.status_code == 200, off.text
    assert off.json()["npcs_shared_with_gms"] is False
    # Naming another field leaves the setting where it was.
    assert unrelated.json()["npcs_shared_with_gms"] is False
    assert on.json()["npcs_shared_with_gms"] is True
    async with admin_session_factory() as session:
        details = list(
            await session.scalars(
                select(AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.action == "tenant.updated")
                .order_by(AuditLog.created_at)
            )
        )
    assert details == [
        "fields=npcs_shared_with_gms",
        "fields=description",
        "fields=npcs_shared_with_gms",
    ]

    await delete_tenant(tenant_id)


async def _authored(tenant_id: uuid.UUID, name: str, author: uuid.UUID | None) -> uuid.UUID:
    async with admin_session_factory() as session:
        entity_id = await _being(session, tenant_id, name, author)
        await session.commit()
        return entity_id


async def test_over_http_a_gm_acts_and_reads_for_the_beings_the_setting_gives_them(
    client: AsyncClient, test_user_id: uuid.UUID
) -> None:
    world = await _world(test_user_id)
    t = world.tenant_id
    async with admin_session_factory() as session:
        stranger = _user("stranger")
        co_gm = _user("co-gm")
        session.add_all([stranger, co_gm])
        await session.flush()
        stranger_id, co_gm_id = stranger.id, co_gm.id
        session.add_all(
            [
                CampaignGm(user_id=test_user_id, campaign_id=world.campaign_id, tenant_id=t),
                CampaignGm(user_id=co_gm_id, campaign_id=world.campaign_id, tenant_id=t),
            ]
        )
        await session.commit()
    mine = await _authored(t, "Mine", test_user_id)
    co = await _authored(t, "Co-GM's", co_gm_id)
    theirs = await _authored(t, "A stranger's", stranger_id)

    async def held_by(entity_id: uuid.UUID) -> Response:
        return await client.get(f"/tenants/{t}/item-instances/held-by/{entity_id}")

    async def give(owner: uuid.UUID) -> Response:
        response: Response = await _give(client, world, "pack", owner)
        return response

    # On, the default: all three.
    assert (await held_by(theirs)).status_code == 200
    assert (await give(theirs)).status_code == 201

    await _share(t, False)
    assert (await held_by(mine)).status_code == 200
    assert (await held_by(co)).status_code == 200
    assert (await held_by(theirs)).status_code == 404
    before = await _count(world)
    assert (await give(theirs)).status_code == 403
    assert await _count(world) == before
    assert (await give(mine)).status_code == 201
    assert (await give(co)).status_code == 201

    await _share(t, True)
    assert (await held_by(theirs)).status_code == 200

    await _tear_down_world(world, stranger_id, co_gm_id)


async def _tear_down_world(world: _World, *extra: uuid.UUID) -> None:
    await tear_down_world(world)
    async with admin_session_factory() as session:
        for user_id in extra:
            user = await session.get(User, user_id)
            if user is not None:
                await session.delete(user)
        await session.commit()
