"""Play order is explicitly recorded, visibility filtered and never Event evidence."""

import uuid

from _admin_db import admin_session_factory
from sqlalchemy import func, select
from test_story_sessions import make_session, roster, world

from lorenzo_api.models import EventLearning, EventParticipant, EventRelationship


async def scene(w, sid, name, shared=True):
    t = w.tenant_id
    canonical = await w.author.post(f"/tenants/{t}/scenes", json={"name": name, "is_public": True})
    base = f"/tenants/{t}/sessions/{sid}"
    version = (await w.author.get(base)).headers["etag"]
    response = await w.author.client.post(
        base + "/scenes",
        headers={**w.author.headers, "If-Match": version},
        json={"scene_entity_id": canonical.json()["id"], "is_shared": shared},
    )
    assert response.status_code == 201, response.text
    return response.json()["scenes"][-1]["id"]


async def event(w, name, public=True):
    result = await w.author.post(
        f"/tenants/{w.tenant_id}/entities",
        json={
            "name": name,
            "kinds": ["event"],
            "visibility": "library" if public else "restricted",
        },
    )
    assert result.status_code == 201, result.text
    return result.json()["id"]


async def put_play(w, sid, played, skipped=None, version=None):
    base = f"/tenants/{w.tenant_id}/sessions/{sid}"
    version = version or (await w.author.get(base)).headers["etag"]
    return await w.author.client.put(
        base + "/play",
        headers={**w.author.headers, "If-Match": version},
        json={"played_appearance_ids": played, "skipped_appearance_ids": skipped or []},
    )


async def present(w, sid, aid, eid, shared=False, pid=None, version=None):
    base = f"/tenants/{w.tenant_id}/sessions/{sid}"
    version = version or (await w.author.get(base)).headers["etag"]
    return await w.author.client.post(
        base + f"/scenes/{aid}/presentations",
        headers={**w.author.headers, "If-Match": version},
        json={"id": pid or str(uuid.uuid4()), "event_id": eid, "is_shared": shared},
    )


async def test_flashback_and_repeated_presentations_do_not_rewrite_preparation_or_graph(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        sid = await make_session(w, c)
        await roster(w, sid, p)
        first = await scene(w, sid, "Arrival")
        flashback = await scene(w, sid, "A memory")
        skipped = await scene(w, sid, "Unused preparation")
        late = await event(w, "The wreck")
        early = await event(w, "The launch")
        assert (await put_play(w, sid, [flashback, first], [skipped])).status_code == 204
        base = f"/tenants/{t}/sessions/{sid}"
        version = (await w.author.get(base)).headers["etag"]
        outline = await w.author.client.put(
            base + "/scenes/order",
            headers={**w.author.headers, "If-Match": version},
            json={"appearance_ids": [skipped, first, flashback]},
        )
        assert outline.status_code == 200
        for aid, eid in [(first, late), (flashback, early), (flashback, early)]:
            made = await present(w, sid, aid, eid, True)
            assert made.status_code == 201, made.text
        result = (await w.outsider.get(base + "/play")).json()
        assert result["played_appearance_ids"] == [flashback, first]
        assert [r["id"] for r in result["appearances"]] == [skipped, first, flashback]
        assert [r["status"] for r in result["appearances"]] == ["skipped", "played", "played"]
        repeats = [r for r in result["presentations"] if r["event_id"] == early]
        assert len(repeats) == 2 and repeats[0]["id"] != repeats[1]["id"]
        async with admin_session_factory() as db:
            for model in [EventRelationship, EventParticipant, EventLearning]:
                assert (
                    await db.scalar(
                        select(func.count()).select_from(model).where(model.tenant_id == t)
                    )
                    == 0
                )
        version = (await w.author.get(base)).headers["etag"]
        refused = await w.author.client.delete(
            base + f"/scenes/{first}", headers={**w.author.headers, "If-Match": version}
        )
        assert refused.status_code == 409
    finally:
        await w.clean_up()


async def test_hidden_play_has_no_placeholders_and_retries_and_stale_order_are_safe(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        sid = await make_session(w, c)
        await roster(w, sid, p)
        visible = await scene(w, sid, "Shared")
        hidden = await scene(w, sid, "Preparation", False)
        public = await event(w, "Visible Event")
        secret = await event(w, "Hidden Event", False)
        base = f"/tenants/{t}/sessions/{sid}"
        assert (await put_play(w, sid, [hidden, visible])).status_code == 204
        pid = str(uuid.uuid4())
        old = (await w.author.get(base)).headers["etag"]
        assert (await present(w, sid, visible, public, True, pid, old)).status_code == 201
        assert (await present(w, sid, visible, public, True, pid, old)).status_code == 201
        assert (await put_play(w, sid, [visible], version=old)).status_code == 412
        assert (await present(w, sid, visible, secret, True)).status_code == 201
        assert (await present(w, sid, visible, public, False)).status_code == 201
        result = (await w.outsider.get(base + "/play")).json()
        assert result["played_appearance_ids"] == [visible]
        assert len(result["appearances"]) == 1
        assert [r["id"] for r in result["presentations"]] == [pid]
        assert "position" not in str(result)
        version = (await w.author.get(base)).headers["etag"]
        forbidden = await w.outsider.client.put(
            base + "/play",
            headers={**w.outsider.headers, "If-Match": version},
            json={"played_appearance_ids": []},
        )
        assert forbidden.status_code == 403
        delete = await w.author.client.delete(
            f"/tenants/{t}/entities/{public}", headers=w.author.headers
        )
        assert delete.status_code == 409
    finally:
        await w.clean_up()


async def test_campaign_session_order_is_explicit_and_scoped_without_date_inference(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        first = await make_session(w, c)
        second = (
            await w.author.post(
                f"/tenants/{t}/sessions", json={"name": "Second", "campaign_id": str(c)}
            )
        ).json()["id"]
        await roster(w, first, p)
        url = f"/tenants/{t}/campaigns/{c}/session-sequence"
        current = await w.author.get(url)
        assert current.json()["ordered"] == [] and len(current.json()["unplaced"]) == 2
        saved = await w.author.client.put(
            url,
            headers={**w.author.headers, "If-Match": current.headers["etag"]},
            json={"session_ids": [second, first]},
        )
        assert saved.status_code == 204, saved.text
        assert [r["id"] for r in (await w.outsider.get(url)).json()["ordered"]] == [first]
        stale = await w.author.client.put(
            url,
            headers={**w.author.headers, "If-Match": current.headers["etag"]},
            json={"session_ids": [first, second]},
        )
        assert stale.status_code == 412
        base = f"/tenants/{t}/sessions/{first}"
        version = (await w.author.get(base)).headers["etag"]
        await w.author.client.patch(
            base,
            headers={**w.author.headers, "If-Match": version},
            json={"real_date": "2020-01-01"},
        )
        assert [r["id"] for r in (await w.author.get(url)).json()["ordered"]] == [second, first]
    finally:
        await w.clean_up()


async def test_scoped_session_order_ignores_hidden_session_edits_and_serializes_writers(
    raw_client, fake_jwks_server
):
    import asyncio

    from sqlalchemy import delete

    from lorenzo_api.models import CampaignGm, SessionGm

    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        first = await make_session(w, c)
        second = (
            await w.author.post(
                f"/tenants/{t}/sessions",
                json={"name": "Other GM preparation", "campaign_id": str(c)},
            )
        ).json()["id"]
        async with admin_session_factory() as db:
            db.add(CampaignGm(tenant_id=t, campaign_id=c, user_id=w.outsider.user_id))
            await db.execute(
                delete(SessionGm).where(SessionGm.session_entity_id == uuid.UUID(second))
            )
            await db.flush()
            db.add(
                SessionGm(
                    tenant_id=t, session_entity_id=uuid.UUID(second), user_id=w.outsider.user_id
                )
            )
            await db.commit()
        url = f"/tenants/{t}/campaigns/{c}/session-sequence"
        own = await w.author.get(url)
        other = await w.outsider.get(url)
        assert len(own.json()["unplaced"]) == 1
        assert (
            await w.outsider.client.put(
                url,
                headers={**w.outsider.headers, "If-Match": other.headers["etag"]},
                json={"session_ids": [second]},
            )
        ).status_code == 204
        # No hidden revision participates in this GM's precondition.
        assert (await w.author.get(url)).headers["etag"] == own.headers["etag"]
        results = await asyncio.gather(
            *[
                w.author.client.put(
                    url,
                    headers={**w.author.headers, "If-Match": own.headers["etag"]},
                    json={"session_ids": [first]},
                )
                for _ in range(2)
            ]
        )
        assert sorted(r.status_code for r in results) == [204, 412]
        assert [r["id"] for r in (await w.outsider.get(url)).json()["ordered"]] == [second]
    finally:
        await w.clean_up()
