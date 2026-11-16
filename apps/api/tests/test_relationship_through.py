"""Relationship through: an authored, ordered chain (ADR 0402)."""

import uuid
from typing import Any

from test_locations import place
from test_relationships import made
from test_story_sessions import world


async def chain(
    actor: Any, t: Any, relationship: str, via: list[str], *, version: str | None = None
):
    base = f"/tenants/{t}/relationships/{relationship}"
    current = await actor.get(base + "/through")
    assert current.status_code == 200, current.text
    headers = {**actor.headers, "If-Match": version or current.headers["etag"]}
    return await actor.client.put(base + "/through", headers=headers, json={"via": via})


async def steps(actor: Any, t: Any, relationship: str) -> list[str]:
    read = await actor.get(f"/tenants/{t}/relationships/{relationship}/through")
    assert read.status_code == 200, read.text
    return [row["name"] for row in read.json()["via"]]


async def ties(gm: Any, t: Any, names: list[str], *, public: bool = True) -> dict[str, str]:
    """One relationship per name, between two places each, so a chain can be built of them."""
    made_ones: dict[str, str] = {}
    left = await place(gm, t, "Left", is_public=True)
    right = await place(gm, t, "Right", is_public=True)
    for name in names:
        one = await made(gm, t, left["id"], right["id"], name, is_public=public)
        made_ones[name] = one["id"]
    return made_ones


async def test_a_chain_is_authored_read_in_order_and_replaced(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        r = await ties(gm, t, ["Grandfather", "Father one", "Father two", "Father three"])
        assert await steps(gm, t, r["Grandfather"]) == []
        first = await chain(gm, t, r["Grandfather"], [r["Father two"], r["Father one"]])
        assert first.status_code == 200, first.text
        assert [x["name"] for x in first.json()["via"]] == ["Father two", "Father one"]
        assert first.headers["etag"]
        assert await steps(gm, t, r["Grandfather"]) == ["Father two", "Father one"]
        # Replaced as a whole, and cleared by an empty list.
        again = await chain(gm, t, r["Grandfather"], [r["Father one"], r["Father three"]])
        assert [x["name"] for x in again.json()["via"]] == ["Father one", "Father three"]
        assert (await chain(gm, t, r["Grandfather"], [])).json() == {"via": []}
        # The relationship's own version moves, so a stale write is refused.
        stale = await chain(gm, t, r["Grandfather"], [r["Father one"]], version='"stale"')
        assert stale.status_code == 412
        base = f"/tenants/{t}/relationships/{r['Grandfather']}/through"
        nothing = await gm.client.put(base, headers=gm.headers, json={"via": []})
        assert nothing.status_code == 428
    finally:
        await w.clean_up()


async def test_a_chain_cannot_loop_or_name_the_same_step_twice(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        r = await ties(gm, t, ["A", "B", "C"])
        assert (await chain(gm, t, r["A"], [r["A"]])).status_code == 422
        assert (await chain(gm, t, r["A"], [r["B"], r["B"]])).status_code == 422
        assert (await chain(gm, t, r["A"], [r["B"]])).status_code == 200
        # Directly: B through A would close the loop A -> B -> A.
        assert (await chain(gm, t, r["B"], [r["A"]])).status_code == 422
        # By a longer path: A -> B -> C, and C through A.
        assert (await chain(gm, t, r["B"], [r["C"]])).status_code == 200
        assert (await chain(gm, t, r["C"], [r["A"]])).status_code == 422
        assert await steps(gm, t, r["C"]) == []
        # What is not a relationship in this library is not a step.
        assert (await chain(gm, t, r["A"], [str(uuid.uuid4())])).status_code == 404
    finally:
        await w.clean_up()


async def test_a_chain_holds_at_most_twelve_steps(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        r = await ties(gm, t, ["Head"] + [f"Step {n:02d}" for n in range(13)])
        ids = [r[f"Step {n:02d}"] for n in range(13)]
        assert (await chain(gm, t, r["Head"], ids)).status_code == 422
        assert (await chain(gm, t, r["Head"], ids[:12])).status_code == 200
    finally:
        await w.clean_up()


async def test_a_hidden_step_leaves_no_gap_and_no_marker(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        shown = await ties(gm, t, ["Head one", "Head two", "Open one", "Open two"])
        secret = await made(gm, t, *(await _ends(gm, t)), "Secret step")
        assert (
            await chain(
                gm, t, shown["Head one"], [shown["Open one"], secret["id"], shown["Open two"]]
            )
        ).status_code == 200
        assert (
            await chain(gm, t, shown["Head two"], [shown["Open one"], shown["Open two"]])
        ).status_code == 200
        assert await steps(gm, t, shown["Head one"]) == ["Open one", "Secret step", "Open two"]
        with_it = await player.get(f"/tenants/{t}/relationships/{shown['Head one']}/through")
        without = await player.get(f"/tenants/{t}/relationships/{shown['Head two']}/through")
        assert with_it.status_code == 200
        assert [x["name"] for x in with_it.json()["via"]] == ["Open one", "Open two"]
        assert [x["id"] for x in with_it.json()["via"]] == [x["id"] for x in without.json()["via"]]
    finally:
        await w.clean_up()


async def _ends(gm: Any, t: Any) -> tuple[str, str]:
    a = await place(gm, t, "Elsewhere A", is_public=True)
    b = await place(gm, t, "Elsewhere B", is_public=True)
    return a["id"], b["id"]


async def test_deleting_a_step_removes_it_from_the_chain(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        r = await ties(gm, t, ["Head", "One", "Two"])
        assert (await chain(gm, t, r["Head"], [r["One"], r["Two"]])).status_code == 200
        gone = await gm.delete(f"/tenants/{t}/entities/{r['One']}")
        assert gone.status_code == 204, gone.text
        assert await steps(gm, t, r["Head"]) == ["Two"]
    finally:
        await w.clean_up()


async def test_staff_are_told_of_a_chain_that_does_not_join_its_ends(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        wren = await place(gm, t, "Wren", is_public=True)
        mara = await place(gm, t, "Mara", is_public=True)
        tomas = await place(gm, t, "Tomas", is_public=True)
        stranger = await place(gm, t, "Stranger", is_public=True)
        grand = await made(gm, t, wren["id"], tomas["id"], "Wren and Tomas", is_public=True)
        up = await made(gm, t, wren["id"], mara["id"], "Wren and Mara", is_public=True)
        on = await made(gm, t, mara["id"], tomas["id"], "Mara and Tomas", is_public=True)
        off = await made(gm, t, stranger["id"], tomas["id"], "Stranger and Tomas", is_public=True)
        assert (await chain(gm, t, grand["id"], [up["id"], on["id"]])).status_code == 200
        read = await gm.get(f"/tenants/{t}/relationship-problems")
        assert read.status_code == 200 and read.json() == {"items": []}
        assert (await chain(gm, t, grand["id"], [up["id"], off["id"]])).status_code == 200
        read = await gm.get(f"/tenants/{t}/relationship-problems")
        assert [x["relationship"]["name"] for x in read.json()["items"]] == ["Wren and Tomas"]
        assert read.json()["items"][0]["kind"] == "through_ends_do_not_meet"
        assert (await player.get(f"/tenants/{t}/relationship-problems")).status_code == 403
    finally:
        await w.clean_up()
