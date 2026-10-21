"""Session scope must hold on both dedicated and generic Information routes."""

import uuid

from _admin_db import admin_session_factory
from _author_world import make_world
from conftest import make_campaign

from lorenzo_api.models import CampaignGm, Player
from lorenzo_api.repository_content import load_content


async def world(raw_client, fake_jwks_server):
    w = await make_world(raw_client, fake_jwks_server)
    async with admin_session_factory() as s:
        c = await make_campaign(s, tenant_id=w.tenant_id)
        s.add(CampaignGm(tenant_id=w.tenant_id, campaign_id=c.id, user_id=w.author.user_id))
        p = Player(tenant_id=w.tenant_id, campaign_id=c.id, user_id=w.outsider.user_id)
        s.add(p)
        await s.commit()
        return w, c.id, p.id


async def make_session(w, campaign):
    made = await w.author.post(
        f"/tenants/{w.tenant_id}/sessions",
        json={
            "id": str(uuid.uuid4()),
            "name": "At the wreck",
            "campaign_id": str(campaign),
            "slug": "wreck-session",
        },
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


async def roster(w, sid, pid, *, include=True, version=None):
    base = f"/tenants/{w.tenant_id}/sessions/{sid}"
    current = await w.author.get(base)
    return await w.author.client.put(
        base + "/roster",
        headers={**w.author.headers, "If-Match": version or current.headers["etag"]},
        json={
            "gm_user_ids": [str(w.author.user_id)],
            "players": [{"player_id": str(pid)}] if include else [],
        },
    )


async def note(actor, t, entry, title, public=False):
    made = await actor.post(
        f"/tenants/{t}/entities/{entry}/information",
        json={
            "title": title,
            "type": "note",
            "is_public": public,
            "content": "A thought about the wreck",
        },
    )
    assert made.status_code == 201, made.text
    return made.json()["id"]


async def test_preparation_empty_roster_and_generic_visibility(raw_client, fake_jwks_server):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        sid = await make_session(w, c)
        base = f"/tenants/{t}/sessions/{sid}"
        current = await w.author.get(base)
        assert current.json()["players"] == [] and current.json()["real_date"] is None
        assert (await w.outsider.get(base)).status_code == 404
        assert (await w.outsider.get(f"/tenants/{t}/entities/{sid}")).status_code == 404
        assert (await roster(w, sid, p)).status_code == 204
        mine = await note(w.outsider, t, sid, "My restricted note")
        preparation = await note(w.author, t, sid, "GM preparation")
        shared = await note(w.author, t, sid, "Shared recap", True)
        result = await w.outsider.get(f"/tenants/{t}/entities/{sid}")
        assert {i["id"] for i in result.json()["information"]} == {mine, shared}
        assert (await w.author.get(f"/tenants/{t}/information/{mine}")).status_code == 200
        assert (await w.outsider.get(f"/tenants/{t}/information/{preparation}")).status_code == 404
        assert (
            await w.outsider.client.patch(
                f"/tenants/{t}/information/{mine}",
                headers=w.outsider.headers,
                json={"title": "Revised"},
            )
        ).status_code == 200
        assert (
            await w.outsider.client.patch(
                f"/tenants/{t}/information/{mine}",
                headers=w.outsider.headers,
                json={"type": "description"},
            )
        ).status_code == 403
        assert (await roster(w, sid, p, include=False)).status_code == 204
        assert (await w.outsider.get(f"/tenants/{t}/information/{mine}")).status_code == 404
    finally:
        await w.clean_up()


async def test_another_campaign_gm_does_not_gain_session_notes(raw_client, fake_jwks_server):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        sid = await make_session(w, c)
        private = await note(w.author, t, sid, "GM preparation")
        async with admin_session_factory() as s:
            s.add(CampaignGm(tenant_id=t, campaign_id=c, user_id=w.outsider.user_id))
            await s.commit()
        assert (await w.outsider.get(f"/tenants/{t}/sessions/{sid}")).status_code == 404
        assert (await w.outsider.get(f"/tenants/{t}/information/{private}")).status_code == 404
        assert (await w.outsider.get(f"/tenants/{t}/sessions")).json() == []
    finally:
        await w.clean_up()


async def test_scene_reuse_separates_notes_and_filters_outline(raw_client, fake_jwks_server):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        sid = await make_session(w, c)
        await roster(w, sid, p)
        scene = (
            await w.author.post(
                f"/tenants/{t}/scenes", json={"name": "Exploring the wreck", "is_public": True}
            )
        ).json()["id"]
        base = f"/tenants/{t}/sessions/{sid}"
        appearances = []
        for shared in [False, True, True]:
            version = (await w.author.get(base)).headers["etag"]
            made = await w.author.client.post(
                base + "/scenes",
                headers={**w.author.headers, "If-Match": version},
                json={"scene_entity_id": scene, "is_shared": shared},
            )
            assert made.status_code == 201, made.text
            appearances.append(made.json()["scenes"][-1]["id"])
        read = await w.outsider.get(base)
        assert [r["id"] for r in read.json()["scenes"]] == appearances[1:]
        assert all("position" not in r for r in read.json()["scenes"])
        note_id = await note(w.outsider, t, appearances[1], "Our first encounter")
        assert (await w.author.get(f"/tenants/{t}/information/{note_id}")).status_code == 200
        assert (await w.outsider.get(f"/tenants/{t}/entities/{appearances[2]}")).json()[
            "information"
        ] == []
        assert (await w.author.get(f"/tenants/{t}/entities/{scene}")).json()["information"] == []
        async with admin_session_factory() as s:
            content = await load_content(s, t)
            assert sid not in content.entities and all(
                i not in content.entities for i in appearances
            )
            assert note_id not in {str(i) for i in content.information}
            assert uuid.UUID(scene) in content.scenes
    finally:
        await w.clean_up()


async def test_session_roster_stale_and_cross_campaign_rejected(raw_client, fake_jwks_server):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        sid = await make_session(w, c)
        base = f"/tenants/{t}/sessions/{sid}"
        old = (await w.author.get(base)).headers["etag"]
        assert (await roster(w, sid, p)).status_code == 204
        assert (await roster(w, sid, p, include=False, version=old)).status_code == 412
        async with admin_session_factory() as s:
            other = await make_campaign(s, tenant_id=t)
            wrong = Player(tenant_id=t, campaign_id=other.id, user_id=w.outsider.user_id)
            s.add(wrong)
            await s.commit()
        assert (await roster(w, sid, wrong.id)).status_code == 422
        version = (await w.author.get(base)).headers["etag"]
        result = await w.author.client.put(
            base + "/roster",
            headers={**w.author.headers, "If-Match": version},
            json={"gm_user_ids": [], "players": []},
        )
        assert result.status_code == 422
    finally:
        await w.clean_up()


async def test_creation_retries_and_atomic_slug_conflict(raw_client, fake_jwks_server):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        sid = await make_session(w, c)
        base = f"/tenants/{t}/sessions/{sid}"
        retry = await w.author.post(
            f"/tenants/{t}/sessions",
            json={"id": sid, "name": "At the wreck", "campaign_id": str(c)},
        )
        assert retry.status_code == 200 and retry.json()["id"] == sid
        scene = (
            await w.author.post(
                f"/tenants/{t}/scenes", json={"name": "The wreck", "slug": "occupied"}
            )
        ).json()["id"]
        version = (await w.author.get(base)).headers["etag"]
        edit = await w.author.client.patch(
            base,
            headers={**w.author.headers, "If-Match": version},
            json={"name": "Must roll back", "slug": "occupied"},
        )
        assert edit.status_code == 409
        assert (await w.author.get(base)).json()["name"] == "At the wreck"
        identity = str(uuid.uuid4())
        args = {"id": identity, "scene_entity_id": scene}
        headers = {**w.author.headers, "If-Match": version}
        first = await w.author.client.post(base + "/scenes", headers=headers, json=args)
        assert first.status_code == 201, first.text
        retry = await w.author.client.post(base + "/scenes", headers=headers, json=args)
        assert retry.status_code == 200 and len(retry.json()["scenes"]) == 1
        own = await w.author.get("/me/sessions")
        assert [r["id"] for r in own.json()] == [sid]
    finally:
        await w.clean_up()
