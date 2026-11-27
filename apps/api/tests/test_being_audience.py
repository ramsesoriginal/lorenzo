"""Who sees a being: the audience routes work on one, and a restricted being is not there for a
reader outside its audience (ADR 0529)."""

from _admin_db import admin_session_factory
from conftest import make_character
from test_relationship_audience import put_audience
from test_story_sessions import world


async def two_beings(w, player_id):
    async with admin_session_factory() as s:
        npc = await make_character(s, tenant_id=w.tenant_id, name="Brisk")
        mine = await make_character(s, tenant_id=w.tenant_id, name="Pia", owner_player_id=player_id)
        await s.commit()
        return str(npc.entity_id), str(mine.entity_id)


async def names(actor, t):
    page = await actor.get(f"/tenants/{t}/characters")
    assert page.status_code == 200, page.text
    return sorted(i["name"] for i in page.json()["items"])


async def test_a_being_has_an_audience_that_starts_open(raw_client, fake_jwks_server):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        npc, _ = await two_beings(w, player_id)
        first = await gm.get(f"/tenants/{t}/entities/{npc}/audience")
        assert first.status_code == 200, first.text
        assert first.json() == {
            "is_public": True,
            "shared_with_participants": False,
            "entity_ids": [],
            "player_ids": [],
        }
        assert first.headers["etag"]
        assert await names(player, t) == ["Brisk", "Pia"]
        # A reader who may not manage it cannot read or write the audience.
        assert (await player.get(f"/tenants/{t}/entities/{npc}/audience")).status_code in {
            403,
            404,
        }
    finally:
        await w.clean_up()


async def test_a_restricted_being_is_absent_for_those_outside_its_audience(
    raw_client, fake_jwks_server
):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        npc, mine = await two_beings(w, player_id)
        open_ = (await gm.get(f"/tenants/{t}/entities/{npc}/audience")).json()
        done = await put_audience(gm, t, npc, {**open_, "is_public": False})
        assert done.status_code == 200, done.text
        # The GM still reads it everywhere; the player reads nothing of it.
        assert await names(gm, t) == ["Brisk", "Pia"]
        assert await names(player, t) == ["Pia"]
        assert (await gm.get(f"/tenants/{t}/characters/{npc}")).status_code == 200
        for path in (
            f"/characters/{npc}",
            f"/beings/{npc}/sheet",
            f"/entities/{npc}",
            f"/entities/{npc}/stat-changes",
        ):
            assert (await player.get(f"/tenants/{t}{path}")).status_code == 404, path
        # Their own character stays theirs, even when it is restricted.
        mine_open = (await gm.get(f"/tenants/{t}/entities/{mine}/audience")).json()
        assert (
            await put_audience(gm, t, mine, {**mine_open, "is_public": False})
        ).status_code == 200
        assert await names(player, t) == ["Pia"]
        assert (await player.get(f"/tenants/{t}/characters/{mine}")).status_code == 200
        # Naming the player brings the other one back; opening it again does the same.
        granted = await put_audience(
            gm, t, npc, {**open_, "is_public": False, "player_ids": [str(player_id)]}
        )
        assert granted.status_code == 200, granted.text
        assert await names(player, t) == ["Brisk", "Pia"]
        assert (await player.get(f"/tenants/{t}/characters/{npc}")).status_code == 200
        back = (await gm.get(f"/tenants/{t}/entities/{npc}/audience")).json()
        assert (
            await put_audience(gm, t, npc, {**back, "is_public": True, "player_ids": []})
        ).status_code == 200
        assert await names(player, t) == ["Brisk", "Pia"]
    finally:
        await w.clean_up()
