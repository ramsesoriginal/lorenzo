"""Who sees a relationship: named recipients and the audience routes (ADR 0404)."""

from typing import Any

from test_locations import place
from test_relationships import listing, made
from test_story_sessions import world


async def put_audience(actor: Any, t: Any, entry: str, body: dict[str, Any], *, version=None):
    base = f"/tenants/{t}/entities/{entry}/audience"
    current = await actor.get(base)
    assert current.status_code == 200, current.text
    headers = {**actor.headers}
    if version != "none":
        headers["If-Match"] = version or current.headers["etag"]
    return await actor.client.put(base, headers=headers, json=body)


async def test_the_audience_routes_work_on_a_relationship(raw_client, fake_jwks_server):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        tie = await made(gm, t, a["id"], b["id"], "Secret bond")
        base = f"/tenants/{t}/entities/{tie['id']}/audience"
        first = await gm.get(base)
        assert first.status_code == 200, first.text
        assert first.json() == {
            "is_public": False,
            "shared_with_participants": False,
            "entity_ids": [],
            "player_ids": [],
        }
        assert first.headers["etag"]
        # Restricted: the player reads nothing until it is granted.
        assert await listing(player, t) == []
        assert (await player.get(f"/tenants/{t}/relationships/{tie['id']}")).status_code == 404
        # A grant needs If-Match, and a stale one is refused.
        missing = await put_audience(gm, t, tie["id"], first.json(), version="none")
        assert missing.status_code == 428
        stale = await put_audience(gm, t, tie["id"], first.json(), version='"stale"')
        assert stale.status_code == 412
        granted = await put_audience(
            gm, t, tie["id"], {**first.json(), "player_ids": [str(player_id)]}
        )
        assert granted.status_code == 200, granted.text
        assert [x["name"] for x in await listing(player, t)] == ["Secret bond"]
        shown = await player.get(f"/tenants/{t}/relationships/{tie['id']}")
        assert shown.status_code == 200 and shown.json()["can_manage"] is False
        # The grant is taken back by replacing it.
        again = await put_audience(gm, t, tie["id"], first.json())
        assert again.status_code == 200
        assert await listing(player, t) == []
        # A reader who is not a manager cannot read or write the audience.
        assert (await player.get(base)).status_code in {403, 404}
    finally:
        await w.clean_up()


async def test_a_grant_does_not_reveal_an_end_the_reader_cannot_see(raw_client, fake_jwks_server):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        open_end = await place(gm, t, "Open hall", is_public=True)
        closed_end = await place(gm, t, "Closed vault")
        tie = await made(gm, t, open_end["id"], closed_end["id"], "Granted but cut")
        done = await put_audience(
            gm,
            t,
            tie["id"],
            {"is_public": False, "entity_ids": [], "player_ids": [str(player_id)]},
        )
        assert done.status_code == 200, done.text
        assert await listing(player, t) == []
        assert (await player.get(f"/tenants/{t}/relationships/{tie['id']}")).status_code == 404
        # Opening the end shows it: the grant was held all along.
        opened = await put_audience(
            gm, t, closed_end["id"], {"is_public": True, "entity_ids": [], "player_ids": []}
        )
        assert opened.status_code == 200, opened.text
        assert [x["name"] for x in await listing(player, t)] == ["Granted but cut"]
    finally:
        await w.clean_up()


async def test_two_relationships_for_one_pair_read_with_their_own_audiences(
    raw_client, fake_jwks_server
):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        await made(gm, t, a["id"], b["id"], "Friends", is_public=True)
        secret = await made(gm, t, a["id"], b["id"], "Lovers")
        assert [x["name"] for x in await listing(gm, t)] == ["Friends", "Lovers"]
        assert [x["name"] for x in await listing(player, t)] == ["Friends"]
        await put_audience(
            gm,
            t,
            secret["id"],
            {"is_public": False, "entity_ids": [], "player_ids": [str(player_id)]},
        )
        assert [x["name"] for x in await listing(player, t)] == ["Friends", "Lovers"]
    finally:
        await w.clean_up()
