"""What the Locations pages of Maps need (ADR 0466): on how many Maps a Location is drawn, on which,
and where each character the reader may ask for would say it is."""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import make_character
from test_locations import place
from test_maps import draw, make_map, pin
from test_placement import character_of, put_at
from test_story_sessions import world


def rows(page: Any) -> list[dict[str, Any]]:
    assert page.status_code == 200, page.text
    items: list[dict[str, Any]] = page.json()["items"]
    return items


async def test_a_row_says_on_how_many_visible_maps_the_location_is_drawn(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        keep = await place(gm, t, "Waterdeep", is_public=True)
        quiet = await place(gm, t, "Daggerford", is_public=True, parent_id=keep["id"])
        open_map = (await make_map(gm, t, "Sword Coast", is_public=True))["id"]
        other_open = (await make_map(gm, t, "Trade routes", is_public=True))["id"]
        secret = (await make_map(gm, t, "Secret chart"))["id"]
        for chart in (open_map, other_open, secret):
            assert (await draw(gm, t, chart, keep["id"], pin(10, 20))).status_code == 200
        base = f"/tenants/{t}/locations"
        # The GM sees all three Maps; the player sees only the open two, with no trace of the third.
        listed = {r["name"]: r for r in rows(await gm.get(base))}
        assert listed["Waterdeep"]["map_count"] == 3 and listed["Daggerford"]["map_count"] == 0
        seen = {r["name"]: r for r in rows(await player.get(base))}
        assert seen["Waterdeep"]["map_count"] == 2 and seen["Daggerford"]["map_count"] == 0
        # The roots, a Location's parts and the Location itself carry the count too.
        roots = rows(await player.get(base + "?root=true"))
        assert [(r["name"], r["map_count"]) for r in roots] == [("Waterdeep", 2)]
        parts = rows(await player.get(f"{base}/{keep['id']}/parts"))
        assert [(r["name"], r["map_count"]) for r in parts] == [("Daggerford", 0)]
        assert (await player.get(f"{base}/{keep['id']}")).json()["map_count"] == 2
        assert (await player.get(f"{base}/{quiet['id']}")).json()["map_count"] == 0
    finally:
        await w.clean_up()


async def test_the_maps_a_location_is_on_are_the_ones_the_reader_may_see(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        keep = await place(gm, t, "Waterdeep", is_public=True)
        elsewhere = await place(gm, t, "Elsewhere", is_public=True)
        open_map = (await make_map(gm, t, "Sword Coast", is_public=True))["id"]
        secret = (await make_map(gm, t, "Secret chart"))["id"]
        await draw(gm, t, open_map, keep["id"], pin(1, 1))
        await draw(gm, t, secret, keep["id"], pin(2, 2))
        await draw(gm, t, open_map, elsewhere["id"], pin(3, 3))
        base = f"/tenants/{t}/maps"
        gm_names = [r["name"] for r in rows(await gm.get(base, params={"placed": keep["id"]}))]
        assert gm_names == ["Secret chart", "Sword Coast"]
        player_names = [
            r["name"] for r in rows(await player.get(base, params={"placed": keep["id"]}))
        ]
        assert player_names == ["Sword Coast"]
        # A hidden or missing entry is a 404, the same one, whoever asks about it.
        hidden = await place(gm, t, "Hidden keep")
        for target in (hidden["id"], str(uuid.uuid4())):
            denied = await player.get(base, params={"placed": target})
            assert denied.status_code == 404
    finally:
        await w.clean_up()


async def test_each_character_the_reader_may_ask_for_says_where_the_location_is(
    raw_client, fake_jwks_server
):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        quay = await place(gm, t, "The quay", is_public=True)
        inn = await place(gm, t, "The inn", is_public=True)
        bram = await character_of(t, player_id, "Bram")
        # Somebody else's character: the player may not ask for them.
        async with admin_session_factory() as session:
            other = await make_character(session, tenant_id=t, name="Ysolde")
            await session.commit()
            ysolde = other.entity_id
        assert (await put_at(gm, t, str(bram), inn["id"])).status_code == 200
        base = f"/tenants/{t}/locations/{quay['id']}/whereabouts"
        mine = rows(await player.get(base))
        assert [r["character"]["name"] for r in mine] == ["Bram"]
        assert mine[0]["state"] in {"elsewhere", "unknown", "with_you", "stashed"}
        everyone = rows(await gm.get(base))
        assert [r["character"]["name"] for r in everyone] == ["Bram", "Ysolde"]
        assert {r["character"]["id"] for r in everyone} == {str(bram), str(ysolde)}
        # A hidden Location and a missing one are the same 404.
        hidden = await place(gm, t, "Hidden keep")
        for target in (hidden["id"], str(uuid.uuid4())):
            assert (
                await player.get(f"/tenants/{t}/locations/{target}/whereabouts")
            ).status_code == 404
    finally:
        await w.clean_up()
