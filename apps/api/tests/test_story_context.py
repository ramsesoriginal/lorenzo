"""Narrative references preserve visibility and never manufacture lived story records."""

from _admin_db import admin_session_factory
from sqlalchemy import func, select
from test_story_sessions import make_session, roster, world

from lorenzo_api.models import EventLearning, EventParticipant, Knowledge


async def reference(actor, tenant, source_kind, source, kind, target, shared=False, version=None):
    base = f"/tenants/{tenant}/{source_kind}/{source}"
    if version is None:
        version = (await actor.get(base)).headers["etag"]
    return await actor.client.put(
        base + f"/references/{kind}/{target}",
        headers={**actor.headers, "If-Match": version},
        json={"is_shared": shared},
    )


async def test_references_require_sharing_and_both_endpoints_without_learning(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        scene = (
            await w.author.post(
                f"/tenants/{t}/scenes", json={"name": "The wreck", "is_public": True}
            )
        ).json()["id"]
        fact = (
            await w.author.post(
                f"/tenants/{t}/entities",
                json={
                    "name": "The ship belonged to the guild",
                    "kinds": ["fact"],
                    "visibility": "library",
                },
            )
        ).json()["id"]
        event = (
            await w.author.post(
                f"/tenants/{t}/entities", json={"name": "A hidden meeting", "kinds": ["event"]}
            )
        ).json()["id"]
        person = (
            await w.owner.post(
                f"/tenants/{t}/entities", json={"name": "The guide", "kinds": ["being"]}
            )
        ).json()["id"]
        assert (await reference(w.author, t, "scenes", scene, "facts", fact)).status_code == 204
        url = f"/tenants/{t}/scenes/{scene}/references"
        assert (await w.outsider.get(url)).json() == []
        assert (
            await reference(w.author, t, "scenes", scene, "facts", fact, True)
        ).status_code == 204
        assert (
            await reference(w.author, t, "scenes", scene, "events", event, True)
        ).status_code == 204
        assert (
            await reference(w.author, t, "scenes", scene, "beings", person, True)
        ).status_code == 204
        rows = (await w.outsider.get(url)).json()
        assert {r["id"] for r in rows} == {fact, person}
        assert (
            await w.outsider.client.put(
                url + f"/facts/{fact}", headers=w.outsider.headers, json={"is_shared": False}
            )
        ).status_code == 403
        sid = await make_session(w, c)
        assert (
            await reference(w.author, t, "sessions", sid, "facts", fact, True)
        ).status_code == 204
        assert (await w.outsider.get(f"/tenants/{t}/sessions/{sid}/references")).status_code == 404
        await roster(w, sid, p)
        assert [
            r["id"]
            for r in (await w.outsider.get(f"/tenants/{t}/sessions/{sid}/references")).json()
        ] == [fact]
        async with admin_session_factory() as s:
            for model in (EventLearning, EventParticipant, Knowledge):
                assert (
                    await s.scalar(
                        select(func.count()).select_from(model).where(model.tenant_id == t)
                    )
                    == 0
                )
    finally:
        await w.clean_up()


async def test_shared_event_can_be_referenced_by_two_scenes_and_stale_edits_are_kept(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        scenes = [
            (
                await w.author.post(f"/tenants/{t}/scenes", json={"name": n, "is_public": True})
            ).json()["id"]
            for n in ["Group A", "Group B"]
        ]
        event = (
            await w.author.post(
                f"/tenants/{t}/entities",
                json={"name": "The ship sank", "kinds": ["event"], "visibility": "library"},
            )
        ).json()["id"]
        old = (await w.author.get(f"/tenants/{t}/scenes/{scenes[0]}")).headers["etag"]
        for scene in scenes:
            assert (
                await reference(w.author, t, "scenes", scene, "events", event, True)
            ).status_code == 204
        stale = await w.author.client.patch(
            f"/tenants/{t}/scenes/{scenes[0]}",
            headers={**w.author.headers, "If-Match": old},
            json={"name": "Overwritten"},
        )
        assert stale.status_code == 412
        for scene in scenes:
            assert [
                r["id"]
                for r in (await w.outsider.get(f"/tenants/{t}/scenes/{scene}/references")).json()
            ] == [event]
        assert (
            await w.author.client.delete(f"/tenants/{t}/entities/{event}", headers=w.author.headers)
        ).status_code == 409
        for scene in scenes:
            version = (await w.author.get(f"/tenants/{t}/scenes/{scene}")).headers["etag"]
            assert (
                await w.author.client.delete(
                    f"/tenants/{t}/scenes/{scene}/references/events/{event}",
                    headers={**w.author.headers, "If-Match": version},
                )
            ).status_code == 204
    finally:
        await w.clean_up()


async def test_repository_purge_preserves_local_scene_appearance_and_notes(
    raw_client, fake_jwks_server
):
    import uuid

    from _repository_actors import cleanup
    from conftest import make_campaign
    from test_kind_matrix import _scene

    from lorenzo_api.models import Entity, SceneAppearance, StorySession

    w = await _scene(raw_client, fake_jwks_server, ("scene",), bridge=False)
    try:
        local = await w.library_entry("Alpha")
        async with admin_session_factory() as db:
            campaign = await make_campaign(db, tenant_id=w.table)
            session_entry = Entity(tenant_id=w.table, name="Local session")
            appearance_entry = Entity(tenant_id=w.table, name="Local appearance")
            db.add_all([session_entry, appearance_entry])
            await db.flush()
            db.add(
                StorySession(entity_id=session_entry.id, tenant_id=w.table, campaign_id=campaign.id)
            )
            await db.flush()
            db.add(
                SceneAppearance(
                    entity_id=appearance_entry.id,
                    tenant_id=w.table,
                    session_entity_id=session_entry.id,
                    scene_entity_id=uuid.UUID(local["id"]),
                    position=0,
                )
            )
            await db.commit()
            appearance_id = appearance_entry.id
        response = await w.gm.post(
            f"/tenants/{w.table}/repositories/{w.repository}/copy", json={"again": "purge"}
        )
        assert response.status_code == 409, response.text
        async with admin_session_factory() as db:
            assert await db.get(SceneAppearance, appearance_id) is not None
    finally:
        await cleanup(w.tenants, [w.author, w.gm])
