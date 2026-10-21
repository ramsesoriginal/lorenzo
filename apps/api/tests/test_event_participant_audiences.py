"""Live participant audiences retain both gates and never invent learning."""

import uuid

from _admin_db import admin_session_factory
from _author_world import make_world
from conftest import make_campaign, make_character
from sqlalchemy import select
from test_event_learning import information
from test_event_order import event

from lorenzo_api.models import CharacterPlayer, EventLearning, Knowledge, Player


async def audience(actor, t, e, *, info=False, shared=False, public=False, version=None):
    url = f"/tenants/{t}/" + (f"information/{e}" if info else f"entities/{e}") + "/audience"
    if version is None:
        version = (await actor.get(url)).headers["etag"]
    return await actor.client.put(
        url,
        headers={**actor.headers, "If-Match": version},
        json={
            "is_public": public,
            "shared_with_participants": shared,
            "entity_ids": [],
            "player_ids": [],
        },
    )


async def test_live_participants_require_independent_outer_and_inner_access(
    raw_client, fake_jwks_server
):
    w = await make_world(raw_client, fake_jwks_server)
    t = w.tenant_id
    try:
        async with admin_session_factory() as s:
            c = await make_campaign(s, tenant_id=t)
            p = Player(tenant_id=t, campaign_id=c.id, user_id=w.outsider.user_id)
            s.add(p)
            await s.flush()
            being = await make_character(s, tenant_id=t, name="Participant")
            s.add(CharacterPlayer(tenant_id=t, player_id=p.id, character_entity_id=being.entity_id))
            await s.commit()
            b = str(being.entity_id)
        e = await event(w.owner, t, "Secret expedition")
        hidden = await information(w.owner, t, e, False)
        shared_note = await information(w.owner, t, e, False)
        roster = f"/tenants/{t}/events/{e}/participants"
        version = (await w.owner.get(roster)).headers["etag"]
        added = await w.owner.client.put(
            roster + f"/{b}", headers={**w.owner.headers, "If-Match": version}
        )
        assert added.status_code == 200, added.text
        assert (await audience(w.owner, t, shared_note, info=True, shared=True)).status_code == 200
        base = f"/tenants/{t}/entities/{e}"
        assert (await w.outsider.get(base)).status_code == 404
        assert (await w.outsider.get(f"/tenants/{t}/information/{shared_note}")).status_code == 404
        assert (await audience(w.owner, t, e, shared=True)).status_code == 200
        shown = await w.outsider.get(base)
        assert shown.status_code == 200, shown.text
        assert [i["id"] for i in shown.json()["information"]] == [shared_note]
        assert (await w.outsider.get(f"/tenants/{t}/information/{hidden}")).status_code == 404
        assert (await w.outsider.get(f"/tenants/{t}/event-learning")).status_code == 403
        old = (await w.owner.get(base + "/audience")).headers["etag"]
        assert (await audience(w.owner, t, e, shared=False)).status_code == 200
        assert (await audience(w.owner, t, e, shared=True, version=old)).status_code == 412
        assert (await audience(w.owner, t, e, shared=True)).status_code == 200
        roster = f"/tenants/{t}/events/{e}/participants"
        version = (await w.owner.get(roster)).headers["etag"]
        assert (
            await w.owner.client.delete(
                roster + f"/{b}", headers={**w.owner.headers, "If-Match": version}
            )
        ).status_code == 200
        assert (await w.outsider.get(base)).status_code == 404
        assert (await w.outsider.get(f"/tenants/{t}/information/{shared_note}")).status_code == 404
        assert (await w.outsider.get(f"/tenants/{t}/events")).json()["total"] == 0
        async with admin_session_factory() as s:
            assert not (await s.scalars(select(Knowledge).where(Knowledge.tenant_id == t))).all()
            assert not (
                await s.scalars(select(EventLearning).where(EventLearning.tenant_id == t))
            ).all()
    finally:
        await w.clean_up()


async def test_creation_visibility_is_atomic_and_facts_have_no_participants(client, test_user_id):
    from conftest import delete_tenant, make_tenant

    from lorenzo_api.models import EntityAudience

    t = await make_tenant(test_user_id)
    try:
        e = uuid.uuid4()
        for visibility in ["participants", "library", "restricted"]:
            new = uuid.uuid4()
            made = await client.post(
                f"/tenants/{t}/entities",
                json={
                    "id": str(new),
                    "name": "Visible choice",
                    "kinds": ["event"],
                    "visibility": visibility,
                },
            )
            assert made.status_code == 201, made.text
            async with admin_session_factory() as s:
                gate = await s.get_one(EntityAudience, new)
                assert gate.is_public == (visibility == "library")
                assert gate.shared_with_participants == (visibility == "participants")
        bad = await client.post(
            f"/tenants/{t}/entities",
            json={"id": str(e), "name": "Fact", "kinds": ["fact"], "visibility": "participants"},
        )
        assert bad.status_code == 422
        assert (await client.get(f"/tenants/{t}/entities/{e}")).status_code == 404
        fact = (
            await client.post(f"/tenants/{t}/entities", json={"name": "Fact", "kinds": ["fact"]})
        ).json()["id"]
        url = f"/tenants/{t}/entities/{fact}/audience"
        v = (await client.get(url)).headers["etag"]
        assert (
            await client.put(
                url,
                json={"is_public": False, "shared_with_participants": True},
                headers={"If-Match": v},
            )
        ).status_code in (400, 422)
    finally:
        await delete_tenant(t)
