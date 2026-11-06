"""Players write their own relationships (ADR 0425)."""

from typing import Any

from test_locations import place
from test_relationships import listing, made
from test_story_sessions import world


async def character(gm: Any, t: Any, name: str, player_id: Any):
    made_one = await gm.post(
        f"/tenants/{t}/characters",
        json={"name": name, "owner_player_id": str(player_id), "player_ids": []},
    )
    assert made_one.status_code == 201, made_one.text
    return str(made_one.json()["entity_id"])


async def test_a_player_makes_changes_and_deletes_a_relationship_with_their_being(
    raw_client, fake_jwks_server
):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        alice = await character(gm, t, "Alice", player_id)
        wren = await place(gm, t, "Wren", is_public=True)
        dren = await place(gm, t, "Dren", is_public=True)
        body = {"name": "Alice trusts Wren", "end_a": alice, "end_b": wren["id"], "one_way": True}
        # Public is not theirs to give; an entry that is not theirs is not theirs to tie.
        assert (
            await player.post(f"/tenants/{t}/relationships", json={**body, "is_public": True})
        ).status_code == 403
        stranger = {"name": "Not mine", "end_a": wren["id"], "end_b": dren["id"]}
        assert (await player.post(f"/tenants/{t}/relationships", json=stranger)).status_code == 403
        made_one = await player.post(f"/tenants/{t}/relationships", json=body)
        assert made_one.status_code == 201, made_one.text
        mine = made_one.json()
        assert mine["can_edit"] is True and mine["is_public"] is None
        # Restricted to the being and the GMs: the player reads it back, a GM too.
        assert [x["name"] for x in await listing(player, t)] == ["Alice trusts Wren"]
        gm_view = await gm.get(f"/tenants/{t}/relationships/{mine['id']}")
        assert gm_view.status_code == 200 and gm_view.json()["is_public"] is False
        # A player who made one reads can_edit; a writer's own reads do too.
        got = await player.get(f"/tenants/{t}/relationships/{mine['id']}")
        assert got.json()["can_edit"] is True
        # Changing: a replacement keeping the being's end is fine, one that drops it is not.
        tag = got.headers["etag"]
        headers = {**player.headers, "If-Match": tag}
        keep = await player.client.put(
            f"/tenants/{t}/relationships/{mine['id']}",
            headers=headers,
            json={"end_a": alice, "end_b": dren["id"], "one_way": False},
        )
        assert keep.status_code == 200, keep.text
        drop = await player.client.put(
            f"/tenants/{t}/relationships/{mine['id']}",
            headers={**player.headers, "If-Match": keep.headers["etag"]},
            json={"end_a": wren["id"], "end_b": dren["id"], "one_way": False},
        )
        assert drop.status_code == 403
        # The audience stays with the writers.
        audience = await player.get(f"/tenants/{t}/entities/{mine['id']}/audience")
        assert audience.status_code in {403, 404}
        # Deleting: needs the version, and then it is gone.
        url = f"/tenants/{t}/relationships/{mine['id']}"
        assert (await player.delete(url)).status_code == 428
        assert (
            await player.client.delete(url, headers={**player.headers, "If-Match": '"x"'})
        ).status_code == 412
        current = (await player.get(url)).headers["etag"]
        gone = await player.client.delete(url, headers={**player.headers, "If-Match": current})
        assert gone.status_code == 204, gone.text
        assert await listing(gm, t) == []
    finally:
        await w.clean_up()


async def test_a_player_cannot_change_what_someone_else_made(raw_client, fake_jwks_server):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        alice = await character(gm, t, "Alice", player_id)
        wren = await place(gm, t, "Wren", is_public=True)
        # A GM's relationship the player can see, with their being as an end.
        theirs = await made(gm, t, alice, wren["id"], "GM made this", is_public=True)
        got = await player.get(f"/tenants/{t}/relationships/{theirs['id']}")
        assert got.status_code == 200 and got.json()["can_edit"] is False
        tag = got.headers["etag"]
        headers = {**player.headers, "If-Match": tag}
        assert (
            await player.client.put(
                f"/tenants/{t}/relationships/{theirs['id']}",
                headers=headers,
                json={"end_a": alice, "end_b": wren["id"], "one_way": True},
            )
        ).status_code == 403
        assert (
            await player.client.delete(
                f"/tenants/{t}/relationships/{theirs['id']}", headers=headers
            )
        ).status_code == 403
        # A writer is unchanged: can_edit, and the delete route works for them.
        mine = await gm.get(f"/tenants/{t}/relationships/{theirs['id']}")
        assert mine.json()["can_edit"] is True
        removed = await gm.client.delete(
            f"/tenants/{t}/relationships/{theirs['id']}",
            headers={**gm.headers, "If-Match": mine.headers["etag"]},
        )
        assert removed.status_code == 204
    finally:
        await w.clean_up()
