"""The Sessions a being takes part in, from the roster and from the Scenes told (ADR 0531)."""

import uuid

from _admin_db import admin_session_factory
from conftest import make_character
from test_story_context import reference
from test_story_sessions import make_session, roster, world

from lorenzo_api.models import CharacterPlayer


async def character_of(w, player_id, name="Pia"):
    async with admin_session_factory() as s:
        c = await make_character(s, tenant_id=w.tenant_id, name=name, owner_player_id=player_id)
        s.add(
            CharacterPlayer(
                character_entity_id=c.entity_id, player_id=player_id, tenant_id=w.tenant_id
            )
        )
        await s.commit()
        return str(c.entity_id)


async def attend(w, sid, player_id, character):
    base = f"/tenants/{w.tenant_id}/sessions/{sid}"
    version = (await w.author.get(base)).headers["etag"]
    put = await w.author.client.put(
        base + "/roster",
        headers={**w.author.headers, "If-Match": version},
        json={
            "gm_user_ids": [str(w.author.user_id)],
            "players": [{"player_id": str(player_id), "character_ids": [character]}],
        },
    )
    assert put.status_code == 204, put.text


async def appear(w, sid, scene, shared):
    base = f"/tenants/{w.tenant_id}/sessions/{sid}"
    version = (await w.author.get(base)).headers["etag"]
    made = await w.author.client.post(
        base + "/scenes",
        headers={**w.author.headers, "If-Match": version},
        json={"scene_entity_id": scene, "is_shared": shared},
    )
    assert made.status_code == 201, made.text


async def sessions_of(actor, t, being):
    got = await actor.get(f"/tenants/{t}/beings/{being}/sessions")
    assert got.status_code == 200, got.text
    return [(s["name"], s["via"]) for s in got.json()]


async def test_a_being_is_in_the_sessions_it_came_to_and_the_scenes_that_tell_of_it(
    raw_client, fake_jwks_server
):
    w, c, p = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        pia = await character_of(w, p)
        npc = (
            await w.owner.post(f"/tenants/{t}/entities", json={"name": "Brisk", "kinds": ["being"]})
        ).json()["id"]
        first = await make_session(w, c)
        second = (
            await w.author.post(
                f"/tenants/{t}/sessions",
                json={
                    "id": str(uuid.uuid4()),
                    "name": "Under the wreck",
                    "campaign_id": str(c),
                    "slug": "under",
                },
            )
        ).json()["id"]
        await attend(w, first, p, pia)
        await roster(w, second, p)
        scene = (
            await w.author.post(
                f"/tenants/{t}/scenes", json={"name": "The wreck", "is_public": True}
            )
        ).json()["id"]
        assert (
            await reference(w.author, t, "scenes", scene, "beings", npc, False)
        ).status_code == 204
        await appear(w, second, scene, False)
        # Who came is the roster; a Scene that tells of a being is the other way in.
        assert await sessions_of(w.author, t, pia) == [("At the wreck", ["roster"])]
        assert await sessions_of(w.author, t, npc) == [("Under the wreck", ["scene"])]
        # The player reads who came, and a telling only once both it and the appearance are shared.
        assert await sessions_of(w.outsider, t, pia) == [("At the wreck", ["roster"])]
        assert await sessions_of(w.outsider, t, npc) == []
        assert (
            await reference(w.author, t, "scenes", scene, "beings", npc, True)
        ).status_code == 204
        assert await sessions_of(w.outsider, t, npc) == []
        # Share the appearance too.
        async with admin_session_factory() as s:
            from sqlalchemy import update

            from lorenzo_api.models import SceneAppearance

            await s.execute(
                update(SceneAppearance)
                .where(SceneAppearance.session_entity_id == uuid.UUID(second))
                .values(is_shared=True)
            )
            await s.commit()
        assert await sessions_of(w.outsider, t, npc) == [("Under the wreck", ["scene"])]
        # Not a being, and no such being.
        fact = (
            await w.author.post(
                f"/tenants/{t}/entities",
                json={"name": "A guild", "kinds": ["fact"], "visibility": "library"},
            )
        ).json()["id"]
        assert (await w.author.get(f"/tenants/{t}/beings/{fact}/sessions")).status_code == 404
        assert (
            await w.author.get(f"/tenants/{t}/beings/{uuid.uuid4()}/sessions")
        ).status_code == 404
    finally:
        await w.clean_up()
