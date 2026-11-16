"""Optional time on a relationship, and reading as of an Event (ADR 0405)."""

import uuid
from typing import Any

from test_locations import place
from test_placement import entry
from test_relationship_audience import put_audience
from test_relationships import listing, made
from test_story_sessions import world


async def event(actor: Any, t: Any, name: str, *, public: bool = True) -> str:
    made_one = await entry(actor, t, name, ("event",))
    if public:
        done = await put_audience(
            actor, t, made_one, {"is_public": True, "entity_ids": [], "player_ids": []}
        )
        assert done.status_code == 200, done.text
    return made_one


async def after(actor: Any, t: Any, first: str, second: str, kind: str = "causes", *, share=False):
    """Records that `first` comes before `second`, optionally shared with readers."""
    base = f"/tenants/{t}/events/{first}/relationships"
    current = await actor.get(base)
    assert current.status_code == 200, current.text
    put = await actor.client.put(
        base + f"/{second}",
        headers={**actor.headers, "If-Match": current.headers["etag"]},
        json={"kind": kind},
    )
    assert put.status_code == 200, put.text
    if share:
        current = await actor.get(base)
        shared = await actor.client.put(
            base + f"/{second}/sharing",
            headers={**actor.headers, "If-Match": current.headers["etag"]},
            json={"kind": kind, "is_shared": True},
        )
        assert shared.status_code == 200, shared.text


async def states(actor: Any, t: Any, as_of: str, **params: Any) -> dict[str, str]:
    rows = await listing(actor, t, as_of=as_of, size=100, **params)
    return {row["name"]: row["as_of"] for row in rows}


async def test_the_limits_are_set_read_replaced_and_checked(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        wedding = await event(gm, t, "The wedding")
        funeral = await event(gm, t, "The funeral")
        secret = await event(gm, t, "The secret oath", public=False)
        plain = await made(gm, t, a["id"], b["id"], "Plain", is_public=True)
        assert plain["starts_at"] is None and plain["ends_at"] is None
        bound = await made(
            gm,
            t,
            a["id"],
            b["id"],
            "Marriage",
            is_public=True,
            starts_at=wedding,
            ends_at=funeral,
        )
        assert (bound["starts_at"]["name"], bound["ends_at"]["id"]) == ("The wedding", funeral)
        # One Event cannot both start and end it, a place is no limit, and a hidden Event is
        # not one the writer can name.
        assert (
            await gm.post(
                f"/tenants/{t}/relationships",
                json={
                    "name": "Loop",
                    "end_a": a["id"],
                    "end_b": b["id"],
                    "starts_at": wedding,
                    "ends_at": wedding,
                },
            )
        ).status_code == 422
        assert (
            await gm.post(
                f"/tenants/{t}/relationships",
                json={"name": "Place", "end_a": a["id"], "end_b": b["id"], "starts_at": a["id"]},
            )
        ).status_code == 422
        # Replaced with the rest, and cleared by null.
        base = f"/tenants/{t}/relationships/{bound['id']}"
        tag = (await gm.get(base)).headers["etag"]
        put = await gm.client.put(
            base,
            headers={**gm.headers, "If-Match": tag},
            json={"end_a": a["id"], "end_b": b["id"], "starts_at": secret},
        )
        assert put.status_code == 200, put.text
        assert (
            put.json()["starts_at"]["name"] == "The secret oath" and put.json()["ends_at"] is None
        )
        # A reader who cannot see an Event is not told which: it reads as null.
        seen = (await player.get(base)).json()
        assert seen["starts_at"] is None and seen["ends_at"] is None
        assert "secret oath" not in (await player.get(base)).text
    finally:
        await w.clean_up()


async def test_four_states_as_of_an_event_from_recorded_paths_only(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        e0, e1, e2, e3 = [await event(gm, t, f"E{n}") for n in range(4)]
        await after(gm, t, e0, e1, "causes")
        await after(gm, t, e1, e2, "order")
        await after(gm, t, e2, e3, "causes")
        loose = await event(gm, t, "Unrecorded")
        for name, fields in {
            "none": {},
            "start e1": {"starts_at": e1},
            "end e2": {"ends_at": e2},
            "e1 to e2": {"starts_at": e1, "ends_at": e2},
            "start unrecorded": {"starts_at": loose},
        }.items():
            await made(gm, t, a["id"], b["id"], name, is_public=True, **fields)
        assert await states(gm, t, e0) == {
            "none": "holds",
            "start e1": "not_yet",
            "end e2": "holds",
            "e1 to e2": "not_yet",
            "start unrecorded": "unknown",
        }
        assert await states(gm, t, e1) == {
            "none": "holds",
            "start e1": "holds",
            "end e2": "holds",
            "e1 to e2": "holds",
            "start unrecorded": "unknown",
        }
        assert await states(gm, t, e3) == {
            "none": "holds",
            "start e1": "holds",
            "end e2": "ended",
            "e1 to e2": "ended",
            "start unrecorded": "unknown",
        }
        # Filtering happens before the page is cut.
        one = await gm.get(
            f"/tenants/{t}/relationships",
            params={"as_of": e3, "state": "ended", "size": 1, "page": 1},
        )
        assert one.json()["total"] == 2 and len(one.json()["items"]) == 1
        # A Event that is not one, or does not exist, is the generic 404.
        assert (
            await gm.get(f"/tenants/{t}/relationships", params={"as_of": a["id"]})
        ).status_code == 404
        assert (
            await gm.get(f"/tenants/{t}/relationships", params={"as_of": str(uuid.uuid4())})
        ).status_code == 404
    finally:
        await w.clean_up()


async def test_a_linearized_order_decides_nothing(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        first, second = await event(gm, t, "First"), await event(gm, t, "Second")
        # No assertion joins them, though a display order puts one ahead of the other.
        await made(gm, t, a["id"], b["id"], "From first", is_public=True, starts_at=first)
        await made(gm, t, a["id"], b["id"], "From second", is_public=True, starts_at=second)
        from_first, from_second = await states(gm, t, first), await states(gm, t, second)
        assert from_first == {"From first": "holds", "From second": "unknown"}
        assert from_second == {"From first": "unknown", "From second": "holds"}
    finally:
        await w.clean_up()


async def test_a_reader_with_fewer_assertions_gets_unknown_and_no_hidden_name(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        e1, e2 = await event(gm, t, "Open one"), await event(gm, t, "Open two")
        hidden = await event(gm, t, "Hidden start", public=False)
        await after(gm, t, e1, e2, "causes")  # not shared: the reader does not see it
        await after(gm, t, hidden, e1, "causes")
        await made(gm, t, a["id"], b["id"], "Bounded by e1", is_public=True, ends_at=e1)
        await made(gm, t, a["id"], b["id"], "Hidden limit", is_public=True, starts_at=hidden)
        assert await states(gm, t, e2) == {"Bounded by e1": "ended", "Hidden limit": "holds"}
        assert await states(player, t, e2) == {
            "Bounded by e1": "unknown",
            "Hidden limit": "unknown",
        }
        read = await player.get(f"/tenants/{t}/relationships", params={"as_of": e2, "size": 100})
        assert "Hidden start" not in read.text and hidden not in read.text
        # Sharing the assertion gives the reader the answer it can see; the hidden limit stays
        # unknown.
        await after(gm, t, e1, e2, "causes", share=True)
        assert await states(player, t, e2) == {
            "Bounded by e1": "ended",
            "Hidden limit": "unknown",
        }
    finally:
        await w.clean_up()


async def test_deleting_a_bounding_event_clears_it_and_leaves_a_staff_note(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        wedding = await event(gm, t, "The wedding")
        war = await made(gm, t, a["id"], b["id"], "At war", is_public=True, starts_at=wedding)
        gone = await gm.delete(f"/tenants/{t}/entities/{wedding}")
        assert gone.status_code == 204, gone.text
        read = (await gm.get(f"/tenants/{t}/relationships/{war['id']}")).json()
        assert read["starts_at"] is None
        notes = await gm.get(f"/tenants/{t}/entities/{war['id']}/information")
        assert notes.status_code == 200, notes.text
        titles = [n["title"] for n in notes.json()["items"]]
        assert titles == ["An Event that bounded this was deleted"]
        seen = await player.get(f"/tenants/{t}/entities/{war['id']}/information")
        assert seen.status_code == 200 and seen.json()["items"] == []
    finally:
        await w.clean_up()


async def test_as_seen_by_a_being_for_staff_and_not_for_a_stranger(raw_client, fake_jwks_server):
    w, _, player_id = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        x = await place(gm, t, "Observer X", is_public=True)
        y = await place(gm, t, "Observer Y", is_public=True)
        await made(gm, t, a["id"], b["id"], "Open", is_public=True)
        secret = await made(gm, t, a["id"], b["id"], "Secret")
        granted = await put_audience(
            gm, t, secret["id"], {"is_public": False, "entity_ids": [x["id"]], "player_ids": []}
        )
        assert granted.status_code == 200, granted.text
        assert [r["name"] for r in await listing(gm, t, as_seen_by=x["id"])] == ["Open", "Secret"]
        assert [r["name"] for r in await listing(gm, t, as_seen_by=y["id"])] == ["Open"]
        # A player may not read as a being they do not control.
        refused = await player.get(f"/tenants/{t}/relationships", params={"as_seen_by": x["id"]})
        assert refused.status_code == 403
        assert player_id
    finally:
        await w.clean_up()
