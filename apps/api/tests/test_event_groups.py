"""Groups include NPCs; Event snapshots are explicit, versioned and retry-safe."""

import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from test_event_collaboration import role
from test_event_order import event
from test_event_participation import being, participate

from lorenzo_api.models import Character, Entity, EventGroupCreation, GroupMember


@pytest.mark.parametrize("manager", ["author", "gm"])
async def test_snapshot_all_beings_is_versioned_and_retry_does_not_restore_members(
    client, test_user_id, manager
):
    t = await make_tenant(test_user_id)
    try:
        e = await event(client, t, "Council")
        a, b, c = [await being(client, t, n) for n in ["Mara", "Untracked guide", "Late arrival"]]
        async with admin_session_factory() as s:
            s.add(Character(tenant_id=t, entity_id=uuid.UUID(a)))
            await s.commit()
        await participate(client, t, e, a)
        await participate(client, t, e, b)
        await role(t, test_user_id, manager)
        url = f"/tenants/{t}/events/{e}/participant-groups"
        roster = f"/tenants/{t}/events/{e}/participants"
        body = {"id": str(uuid.uuid4()), "name": "The council"}
        assert (await client.post(url, json=body)).status_code == 428
        old = (await client.get(roster)).headers["etag"]
        await participate(client, t, e, c)
        assert (await client.post(url, json=body, headers={"If-Match": old})).status_code == 412
        version = (await client.get(roster)).headers["etag"]
        made = await client.post(url, json=body, headers={"If-Match": version})
        assert made.status_code == 201, made.text
        g = uuid.UUID(made.json()["id"])
        assert {x["id"] for x in (await client.get(f"/tenants/{t}/groups/{g}/members")).json()} == {
            a,
            b,
            c,
        }
        async with admin_session_factory() as s:
            assert set(
                await s.scalars(select(Character.entity_id).where(Character.tenant_id == t))
            ) == {uuid.UUID(a)}
            (await s.get_one(Entity, g)).name = "A local edit"
            await s.execute(
                delete(GroupMember).where(
                    GroupMember.group_entity_id == g,
                    GroupMember.character_entity_id == uuid.UUID(b),
                )
            )
            await s.commit()
        version2 = (await client.get(roster)).headers["etag"]
        assert (
            await client.delete(roster + f"/{c}", headers={"If-Match": version2})
        ).status_code == 200
        replay = await client.post(url, json=body, headers={"If-Match": version})
        assert replay.status_code == 200 and replay.json()["name"] == "A local edit"
        assert len((await client.get(f"/tenants/{t}/groups/{g}/members")).json()) == 2
        changed = await client.post(
            url, json={**body, "name": "Different request"}, headers={"If-Match": version}
        )
        assert changed.status_code == 409
        collision = await client.post(
            url, json={"id": a, "name": "Not a group replacement"}, headers={"If-Match": version2}
        )
        assert collision.status_code == 409
    finally:
        await delete_tenant(t)


async def test_player_cannot_create_snapshot_even_for_own_event(client, test_user_id):
    t = await make_tenant(test_user_id)
    try:
        await role(t, test_user_id, "player")
        e = await event(client, t, "Player record")
        r = await client.post(
            f"/tenants/{t}/events/{e}/participant-groups",
            json={"id": str(uuid.uuid4()), "name": "No"},
            headers={"If-Match": '"unknown"'},
        )
        assert r.status_code == 403
    finally:
        await delete_tenant(t)


async def test_generic_groups_accept_npcs_and_tracking_demotion_preserves_membership(
    client, test_user_id
):
    t = await make_tenant(test_user_id)
    try:
        b = await being(client, t, "Guide")
        group = await client.post(
            f"/tenants/{t}/groups", json={"name": "Travellers", "member_character_ids": [b]}
        )
        assert group.status_code == 201, group.text
        g = uuid.UUID(group.json()["id"])
        async with admin_session_factory() as s:
            assert await s.get(Character, uuid.UUID(b)) is None
            s.add(Character(tenant_id=t, entity_id=uuid.UUID(b)))
            await s.commit()
        assert (await client.delete(f"/tenants/{t}/characters/{b}")).status_code == 204
        async with admin_session_factory() as s:
            assert await s.get(GroupMember, (g, uuid.UUID(b))) is not None
            assert await s.get(Character, uuid.UUID(b)) is None
        assert len((await client.get(f"/tenants/{t}/groups/{g}/members")).json()) == 1
    finally:
        await delete_tenant(t)


async def test_group_receipt_and_member_reject_cross_tenant_keys(client, test_user_id):
    t, other = await make_tenant(test_user_id), await make_tenant(test_user_id)
    try:
        e = await event(client, t)
        b = await being(client, other)
        version = (await client.get(f"/tenants/{t}/events/{e}/participants")).headers["etag"]
        r = await client.post(
            f"/tenants/{t}/events/{e}/participant-groups",
            json={"id": b, "name": "Collision"},
            headers={"If-Match": version},
        )
        assert r.status_code == 409
        async with admin_session_factory() as s:
            with pytest.raises(IntegrityError):
                s.add(
                    EventGroupCreation(
                        tenant_id=t,
                        group_entity_id=uuid.UUID(b),
                        request_hash="foreign",
                        created_by=test_user_id,
                    )
                )
                await s.flush()
            await s.rollback()
    finally:
        await delete_tenant(t)
        await delete_tenant(other)


async def test_general_group_writes_keep_existing_private_npc_standing(client, test_user_id):
    from lorenzo_api.models import Tenant, User

    t = await make_tenant(test_user_id)
    try:
        b = await being(client, t, "Another author's NPC")
        group = (await client.post(f"/tenants/{t}/groups", json={"name": "Empty group"})).json()[
            "id"
        ]
        async with admin_session_factory() as s:
            other = User(authgear_subject_id=str(uuid.uuid4()))
            s.add(other)
            await s.flush()
            (await s.get_one(Entity, uuid.UUID(b))).created_by = other.id
            (await s.get_one(Tenant, t)).npcs_shared_with_gms = False
            await s.commit()
        await role(t, test_user_id, "gm")
        denied = await client.put(f"/tenants/{t}/groups/{group}/members/{b}")
        assert denied.status_code == 403
    finally:
        await delete_tenant(t)
