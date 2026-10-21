"""Library-wide managers, player creators and reader note authors stay distinct."""

import uuid

import pytest
from _admin_db import admin_session_factory
from conftest import delete_tenant, make_campaign, make_tenant
from sqlalchemy import delete
from test_event_learning import information, learn
from test_event_order import event, relation
from test_event_participation import being, participate

from lorenzo_api.models import (
    CampaignGm,
    Entity,
    EntityAudience,
    Information,
    Membership,
    MembershipRole,
    Player,
    User,
)


async def role(t, user, kind):
    async with admin_session_factory() as s:
        await s.execute(
            delete(Membership).where(Membership.tenant_id == t, Membership.user_id == user)
        )
        c = await make_campaign(s, tenant_id=t)
        if kind == "author":
            s.add(Membership(tenant_id=t, user_id=user, role=MembershipRole.AUTHOR))
        elif kind == "gm":
            s.add(CampaignGm(tenant_id=t, campaign_id=c.id, user_id=user))
        else:
            s.add(Player(tenant_id=t, campaign_id=c.id, user_id=user))
        await s.commit()


@pytest.mark.parametrize("kind", ["author", "gm"])
async def test_managers_edit_complete_graph_and_learning(client, test_user_id, kind):
    t = await make_tenant(test_user_id)
    try:
        a, b = await event(client, t, "A"), await event(client, t, "B")
        person = await being(client, t, "Mara")
        i = await information(client, t, a, False)
        await role(t, test_user_id, kind)
        assert (await client.get(f"/tenants/{t}/events/access")).json()["can_order"]
        assert not (await client.get(f"/tenants/{t}/events/access")).json()["can_retain_private"]
        assert (await relation(client, t, a, b, "causes")).status_code == 200
        assert (await client.get(f"/tenants/{t}/events/{a}/relationships")).json()[0][
            "is_shared"
        ] is False
        assert (await participate(client, t, a, person)).status_code == 200
        assert (await learn(client, t, a, person, i)).status_code == 200
    finally:
        await delete_tenant(t)


async def test_player_creator_and_reader_notes_do_not_grant_other_editing(client, test_user_id):
    t = await make_tenant(test_user_id)
    try:
        a = await event(client, t, "Someone else's Event")
        private = await information(client, t, a, False)
        async with admin_session_factory() as s:
            other = User(authgear_subject_id=str(uuid.uuid4()))
            s.add(other)
            await s.flush()
            (await s.get_one(Entity, uuid.UUID(a))).created_by = other.id
            (await s.get_one(Information, uuid.UUID(private))).created_by = other.id
            (await s.get_one(EntityAudience, uuid.UUID(a))).is_public = True
            await s.commit()
        await role(t, test_user_id, "player")
        entry = await client.get(f"/tenants/{t}/entities/{a}")
        assert entry.status_code == 200 and entry.json()["information"] == []
        assert (
            await client.patch(f"/tenants/{t}/entities/{a}", json={"name": "Changed"})
        ).status_code == 403
        note = await information(client, t, a, False)
        assert note in [
            i["id"] for i in (await client.get(f"/tenants/{t}/entities/{a}")).json()["information"]
        ]
        assert (
            await client.patch(f"/tenants/{t}/information/{private}", json={"title": "Stolen"})
        ).status_code in (403, 404)
        assert (
            await client.patch(
                f"/tenants/{t}/information/{note}", json={"title": "My revised note"}
            )
        ).status_code == 200
        assert (
            await client.patch(f"/tenants/{t}/information/{note}", json={"type": "description"})
        ).status_code == 403
        for kind in ["event", "fact"]:
            made = await client.post(
                f"/tenants/{t}/entities", json={"name": "Mine", "kinds": [kind]}
            )
            assert made.status_code == 201, made.text
            e = made.json()["id"]
            assert (await client.get(f"/tenants/{t}/entities/{e}")).status_code == 200
            assert (
                await client.patch(f"/tenants/{t}/entities/{e}", json={"name": "Revised"})
            ).status_code == 200
            assert (await client.get(f"/tenants/{t}/entities/{e}/access")).json()["can_edit"]
        assert not (await client.get(f"/tenants/{t}/events/access")).json()["can_order"]
        assert (await client.get(f"/tenants/{t}/event-learning")).status_code == 403
    finally:
        await delete_tenant(t)
