"""The SocialWeb: a saved view of relationships (ADR 0406)."""

import json
import pathlib
import re
import uuid
from typing import Any

from test_locations import place
from test_placement import entry
from test_relationships import made
from test_story_sessions import world


async def web(actor: Any, t: Any, name: str = "Court", **fields: Any) -> dict[str, Any]:
    response = await actor.post(f"/tenants/{t}/social-webs", json={"name": name, **fields})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def members(
    actor: Any, t: Any, web_id: str, body: dict[str, Any], *, version: str | None = None
):
    base = f"/tenants/{t}/social-webs/{web_id}"
    tag = version or (await actor.get(base)).headers["etag"]
    return await actor.client.post(
        base + "/members/bulk", headers={**actor.headers, "If-Match": tag}, json=body
    )


async def test_a_web_is_made_restricted_read_replaced_and_validated(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        made_web = await web(gm, t, "The court", layout="circle", layout_seed=9, theme_hint="ink")
        assert made_web["layout"] == "circle" and made_web["layout_seed"] == 9
        assert made_web["is_public"] is False and made_web["members"] == []
        assert made_web["can_manage"] is True and made_web["types"] == []
        # Restricted: the player reads nothing until the audience is opened.
        assert (await player.get(f"/tenants/{t}/social-webs/{made_web['id']}")).status_code == 404
        assert (await player.get(f"/tenants/{t}/social-webs")).json()["items"] == []
        open_web = await web(gm, t, "Open court", is_public=True)
        seen = await player.get(f"/tenants/{t}/social-webs/{open_web['id']}")
        assert seen.status_code == 200 and seen.json()["can_manage"] is False
        assert seen.json()["is_public"] is None
        # Replaced under If-Match; the layout list is closed and a view holds no entry id.
        base = f"/tenants/{t}/social-webs/{made_web['id']}"
        tag = (await gm.get(base)).headers["etag"]
        headers = {**gm.headers, "If-Match": tag}
        put = await gm.client.put(
            base,
            headers=headers,
            json={"layout": "manual", "layout_seed": 3, "view": {"labels": True, "hulls": False}},
        )
        assert put.status_code == 200, put.text
        assert (put.json()["layout"], put.json()["view"]["labels"]) == ("manual", True)
        stale = await gm.client.put(base, headers=headers, json={"layout": "circle"})
        assert stale.status_code == 412
        fresh = {**gm.headers, "If-Match": put.headers["etag"]}
        assert (
            await gm.client.put(base, headers=fresh, json={"layout": "spiral"})
        ).status_code == 422
        leaking = await gm.client.put(
            base, headers=fresh, json={"layout": "circle", "view": {"focus": str(uuid.uuid4())}}
        )
        assert leaking.status_code == 422
        assert (
            await gm.client.put(base, headers=fresh, json={"layout": "circle"})
        ).status_code == 200
        assert (
            await gm.client.put(base, json={"layout": "circle"}, headers=gm.headers)
        ).status_code == 428
    finally:
        await w.clean_up()


async def test_members_are_set_placed_and_dropped_in_one_write(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        dren = await place(gm, t, "Dren", is_public=True)
        court = await web(gm, t, is_public=True)
        first = await members(
            gm,
            t,
            court["id"],
            {
                "set": [
                    {"entry_id": mara["id"], "x": 1.5, "y": -2},
                    {"entry_id": wren["id"]},
                    {"entry_id": dren["id"]},
                ]
            },
        )
        assert first.status_code == 200, first.text
        shown = {m["entry"]["name"]: (m["x"], m["y"]) for m in first.json()["members"]}
        assert shown == {"Mara": (1.5, -2.0), "Wren": (None, None), "Dren": (None, None)}
        again = await members(
            gm,
            t,
            court["id"],
            {"set": [{"entry_id": wren["id"], "x": 0, "y": 4}], "remove": [dren["id"]]},
        )
        assert {m["entry"]["name"]: m["x"] for m in again.json()["members"]} == {
            "Mara": 1.5,
            "Wren": 0.0,
        }
        # Refusals: one coordinate alone, a repeat, a relationship or a web as a member, too many
        # rows, and a stale version. Nothing is written by a refused request.
        bond = await made(gm, t, mara["id"], wren["id"], "Bond", is_public=True)
        for body in (
            {"set": [{"entry_id": dren["id"], "x": 1}]},
            {"set": [{"entry_id": dren["id"]}], "remove": [dren["id"]]},
            {"set": [{"entry_id": bond["id"]}]},
            {"set": [{"entry_id": court["id"]}]},
            {"remove": [str(uuid.uuid4())] * 101},
            {},
        ):
            assert (await members(gm, t, court["id"], body)).status_code == 422, body
        assert (
            await members(gm, t, court["id"], {"remove": [mara["id"]]}, version='"x"')
        ).status_code == 412
        listed = (await gm.get(f"/tenants/{t}/social-webs/{court['id']}")).json()
        assert len(listed["members"]) == 2
    finally:
        await w.clean_up()


async def test_a_web_holds_a_limited_number_of_members(raw_client, fake_jwks_server, monkeypatch):
    from lorenzo_api import social_webs as limits

    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        monkeypatch.setattr(limits, "MAX_MEMBERS", 2)
        places = [await place(gm, t, f"Place {n}", is_public=True) for n in range(3)]
        court = await web(gm, t)
        two = await members(
            gm, t, court["id"], {"set": [{"entry_id": p["id"]} for p in places[:2]]}
        )
        assert two.status_code == 200, two.text
        three = await members(gm, t, court["id"], {"set": [{"entry_id": places[2]["id"]}]})
        assert three.status_code == 422
        # Moving one that is already a member adds nothing.
        move = await members(
            gm, t, court["id"], {"set": [{"entry_id": places[0]["id"], "x": 1, "y": 1}]}
        )
        assert move.status_code == 200
    finally:
        await w.clean_up()


async def test_a_hidden_member_leaves_no_mark_and_moves_no_one(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        vault = await place(gm, t, "Secret vault")
        shown = await web(gm, t, "Shown", is_public=True)
        plain = await web(gm, t, "Plain", is_public=True)
        rows = [
            {"entry_id": mara["id"], "x": 1, "y": 2},
            {"entry_id": wren["id"], "x": 3, "y": 4},
        ]
        assert (
            await members(gm, t, shown["id"], {"set": [*rows, {"entry_id": vault["id"]}]})
        ).status_code == 200
        assert (await members(gm, t, plain["id"], {"set": rows})).status_code == 200
        with_hidden = (await player.get(f"/tenants/{t}/social-webs/{shown['id']}")).json()
        without = (await player.get(f"/tenants/{t}/social-webs/{plain['id']}")).json()
        assert with_hidden["members"] == without["members"]
        assert "vault" not in (await player.get(f"/tenants/{t}/social-webs/{shown['id']}")).text
        # Staff see the member; a relationship between a visible and a hidden member is no edge.
        staff = (await gm.get(f"/tenants/{t}/social-webs/{shown['id']}")).json()
        assert len(staff["members"]) == 3
        await made(gm, t, mara["id"], wren["id"], "Open tie", is_public=True)
        await made(gm, t, mara["id"], vault["id"], "Cut tie", is_public=True)
        reader = (await player.get(f"/tenants/{t}/social-webs/{shown['id']}/graph")).json()
        assert [e["name"] for e in reader["edges"]] == ["Open tie"] and not reader["truncated"]
        staff_graph = (await gm.get(f"/tenants/{t}/social-webs/{shown['id']}/graph")).json()
        assert [e["name"] for e in staff_graph["edges"]] == ["Cut tie", "Open tie"]
    finally:
        await w.clean_up()


async def test_a_web_limited_to_types_draws_only_their_edges(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        ally = await entry(gm, t, "Ally of")
        rival = await entry(gm, t, "Rival of")
        await made(gm, t, mara["id"], wren["id"], "Allies", is_public=True, prototypes=[ally])
        await made(gm, t, mara["id"], wren["id"], "Rivals", is_public=True, prototypes=[rival])
        court = await web(gm, t, is_public=True)
        assert (
            await members(
                gm, t, court["id"], {"set": [{"entry_id": mara["id"]}, {"entry_id": wren["id"]}]}
            )
        ).status_code == 200
        base = f"/tenants/{t}/social-webs/{court['id']}"
        names = lambda graph: [e["name"] for e in graph["edges"]]  # noqa: E731
        assert names((await gm.get(base + "/graph")).json()) == ["Allies", "Rivals"]
        tag = (await gm.get(base)).headers["etag"]
        put = await gm.client.put(
            base + "/types", headers={**gm.headers, "If-Match": tag}, json={"type_ids": [ally]}
        )
        assert put.status_code == 200, put.text
        assert [x["name"] for x in put.json()["types"]] == ["Ally of"]
        assert names((await gm.get(base + "/graph")).json()) == ["Allies"]
    finally:
        await w.clean_up()


async def test_the_kind_is_its_own_and_reach_code_never_reads_a_web(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        thing = await entry(gm, t, "Plain entry")
        court = await web(gm, t, is_public=True)
        refused = await gm.put(f"/tenants/{t}/entities/{thing}/kinds/social_web", json={})
        assert refused.status_code in {404, 405, 422}, refused.text
        plain = await gm.post(
            f"/tenants/{t}/entities", json={"name": "Not a web", "kinds": ["social_web"]}
        )
        assert plain.status_code == 422, plain.text
        read = (await gm.get(f"/tenants/{t}/entities/{court['id']}")).json()
        assert read["kinds"] == ["social_web"]
    finally:
        await w.clean_up()

    source = pathlib.Path(__file__).resolve().parents[1] / "src" / "lorenzo_api"
    for module in ("entity_access.py", "campaign_access.py", "session_access.py"):
        text = (source / module).read_text(encoding="utf-8") if (source / module).exists() else ""
        assert not re.search(r"SocialWebEntry|SocialWebType", text), module


def test_the_layouts_are_the_renderers_closed_list():
    """One source: the API's `layout` check and the renderer's engines share a list (ADR 0407)."""
    from lorenzo_api.social_webs import LAYOUTS

    listed = pathlib.Path(__file__).resolve().parents[3] / "packages" / "graph-renderer"
    names = json.loads((listed / "src" / "layouts.json").read_text(encoding="utf-8"))
    assert list(LAYOUTS) == names
