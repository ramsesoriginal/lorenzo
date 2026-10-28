"""The distance read (ADR 0366, 0367): a route over the connections a reader sees, and the straight
line on a Map."""

import uuid
from typing import Any

import pytest
from test_connections import made
from test_locations import place
from test_maps import draw, make_map, pin
from test_placement import entry
from test_story_sessions import world

from lorenzo_api import routing
from lorenzo_api.config import get_settings
from lorenzo_api.rate_limit import reset_user_rate_limiters


async def definition(actor: Any, t: Any, name: str, value_type: str, unit: str | None = None):
    """A stat definition in a group of its own."""
    group = await actor.post(f"/tenants/{t}/stat-groups", json={"name": f"{name} group"})
    assert group.status_code == 201, group.text
    body = {"name": name, "stat_group_id": group.json()["id"], "value_type": value_type}
    if unit:
        body["unit"] = unit
    created = await actor.post(f"/tenants/{t}/stat-definitions", json=body)
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def give(actor: Any, t: Any, who: str, stat: str, value: object) -> None:
    response = await actor.put(f"/tenants/{t}/entities/{who}/stats/{stat}", json={"value": value})
    assert response.status_code == 200, response.text


async def ask(actor: Any, t: Any, source: str, target: str, **params: Any):
    return await actor.get(
        f"/tenants/{t}/distance", params={"from": source, "to": target, **params}
    )


async def road(
    actor: Any, t: Any, a: str, b: str, length: float | None, stat: str, name: str = "Road", **kw
):
    one = await made(actor, t, a, b, name, is_public=True, **kw)
    if length is not None:
        await give(actor, t, one["id"], stat, float(length))
    return one


async def places(actor: Any, t: Any, *names: str) -> list[str]:
    return [(await place(actor, t, name, is_public=True))["id"] for name in names]


async def test_a_route_is_the_shortest_one_measured_in_the_stat_with_its_unit(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        miles = await definition(gm, t, "Miles", "float", "miles")
        a, b, c, d = await places(gm, t, "Hollowmere", "Dunmere", "Brindle", "Ashford")
        await road(gm, t, a, b, 10, miles, "First")
        await road(gm, t, b, c, 5.5, miles, "Second")
        await road(gm, t, c, d, 7, miles, "Third")
        await road(gm, t, a, d, 40, miles, "Direct")

        for who in (gm, player):
            got = await ask(who, t, a, d, measure=miles)
            body = got.json()
            assert got.status_code == 200, got.text
            assert body["mode"] == "route" and body["state"] == "known"
            assert body["value"] == 22.5 and body["unit"] == "miles"
            assert body["reason"] is None and body["at_least"] is None
            assert [x["connection"]["name"] for x in body["route"]] == ["First", "Second", "Third"]
            assert [x["length"] for x in body["route"]] == [10, 5.5, 7]
            assert body["route"][0]["start"]["name"] == "Hollowmere"
            assert body["route"][-1]["end"]["name"] == "Ashford"
        # It runs both ways along a two-way road, and a place is no distance from itself.
        assert (await ask(gm, t, d, a, measure=miles)).json()["value"] == 22.5
        same = (await ask(gm, t, a, a, measure=miles)).json()
        assert same["state"] == "known" and same["value"] == 0 and same["route"] == []
    finally:
        await w.clean_up()


async def test_a_one_way_connection_goes_one_way_and_a_missing_route_is_unknown(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        miles = await definition(gm, t, "Miles", "float", "miles")
        a, b, island = await places(gm, t, "Hollowmere", "Dunmere", "Island")
        await road(gm, t, a, b, 4, miles, "Ferry", one_way=True)

        assert (await ask(gm, t, a, b, measure=miles)).json()["value"] == 4
        back = (await ask(gm, t, b, a, measure=miles)).json()
        assert back["state"] == "unknown" and back["reason"] == "no known route"
        assert back["value"] is None and back["route"] == []
        nowhere = (await ask(gm, t, a, island, measure=miles)).json()
        assert nowhere["state"] == "unknown" and nowhere["value"] is None
    finally:
        await w.clean_up()


async def test_a_measured_route_beats_one_that_is_not_and_a_partial_one_says_what_it_lacks(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        miles = await definition(gm, t, "Miles", "float", "miles")
        a, b, c, d = await places(gm, t, "Hollowmere", "Dunmere", "Brindle", "Ashford")
        await road(gm, t, a, d, None, miles, "Unmeasured shortcut")
        await road(gm, t, a, b, 100, miles, "Long first")
        await road(gm, t, b, d, 100, miles, "Long second")
        known = (await ask(gm, t, a, d, measure=miles)).json()
        assert known["state"] == "known" and known["value"] == 200
        assert [x["connection"]["name"] for x in known["route"]] == ["Long first", "Long second"]

        # Only a route with a leg of no length: what is measured is a lower bound, never a value.
        await road(gm, t, a, c, 30, miles, "Known leg")
        await road(gm, t, c, d, None, miles, "Unknown leg")
        # The measured pair of roads above is still the better answer to Ashford...
        assert (await ask(gm, t, a, d, measure=miles)).json()["state"] == "known"
        # ...but a place only reachable through an unmeasured leg is partial.
        (e,) = await places(gm, t, "Elder Hill")
        await road(gm, t, d, e, None, miles, "Rough track")
        partial = (await ask(gm, t, a, e, measure=miles)).json()
        assert partial["state"] == "partial" and partial["value"] is None
        assert partial["at_least"] == 200 and partial["unmeasured_legs"] == 1
        assert partial["unit"] == "miles"
        assert [x["length"] for x in partial["route"]] == [100, 100, None]
    finally:
        await w.clean_up()


async def test_a_length_is_inherited_through_a_prototype_and_a_formula_or_a_negative_is_none(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        miles = await definition(gm, t, "Miles", "float", "miles")
        days = await definition(gm, t, "Days", "int")
        a, b, c, d = await places(gm, t, "Hollowmere", "Dunmere", "Brindle", "Ashford")
        highway = await entry(gm, t, "Highway")
        await give(gm, t, highway, miles, 12.0)
        await road(gm, t, a, b, None, miles, "By prototype", prototypes=[highway])
        # An own value wins over an inherited one.
        second = await road(gm, t, b, c, 3, miles, "Own", prototypes=[highway])
        assert second["id"]
        assert (await ask(gm, t, a, c, measure=miles)).json()["value"] == 15
        # A formula is no length: it is computed from something else, never read here.
        sick = await road(gm, t, c, d, None, miles, "Computed")
        await give(gm, t, sick["id"], days, 4)
        formula = await gm.put(
            f"/tenants/{t}/entities/{sick['id']}/computed-stats/{miles}",
            json={
                "kind": "linear",
                "multiplier": 10,
                "offset": 0,
                "round_mode": "floor",
                "source_stat_definition_id": days,
            },
        )
        assert formula.status_code == 200, formula.text
        formula_answer = (await ask(gm, t, c, d, measure=miles)).json()
        assert formula_answer["state"] == "partial" and formula_answer["unmeasured_legs"] == 1
        # A negative length is no length either.
        (e,) = await places(gm, t, "Elder Hill")
        await road(gm, t, d, e, -5, miles, "Backwards")
        backwards = (await ask(gm, t, d, e, measure=miles)).json()
        assert backwards["state"] == "partial" and backwards["unmeasured_legs"] == 1
    finally:
        await w.clean_up()


async def test_avoid_leaves_out_a_connection_that_carries_the_tag(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        miles = await definition(gm, t, "Miles", "float", "miles")
        flooded = await definition(gm, t, "Flooded", "bool")
        a, b, c = await places(gm, t, "Hollowmere", "Dunmere", "Brindle")
        short = await road(gm, t, a, b, 2, miles, "Short but flooded")
        await give(gm, t, short["id"], flooded, True)
        await road(gm, t, a, c, 5, miles, "Long way")
        await road(gm, t, c, b, 5, miles, "Long way round")
        # A tag that is false does not exclude.
        dry = await road(gm, t, a, b, 9, miles, "Dry")
        await give(gm, t, dry["id"], flooded, False)

        assert (await ask(gm, t, a, b, measure=miles)).json()["value"] == 2
        got = (await ask(gm, t, a, b, measure=miles, avoid=flooded)).json()
        assert got["value"] == 9 and got["route"][0]["connection"]["name"] == "Dry"
    finally:
        await w.clean_up()


async def test_what_cannot_be_asked_is_refused(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        miles = await definition(gm, t, "Miles", "float", "miles")
        label = await definition(gm, t, "Label", "text")
        flag = await definition(gm, t, "Flag", "bool")
        a, b = await places(gm, t, "Hollowmere", "Dunmere")
        secret = (await place(gm, t, "Hidden keep"))["id"]

        assert (await ask(gm, t, a, b)).status_code == 422
        assert (await ask(gm, t, a, b, measure=label)).status_code == 422
        assert (await ask(gm, t, a, b, measure=flag)).status_code == 422
        assert (await ask(gm, t, a, b, measure=miles, avoid=miles)).status_code == 422
        assert (await ask(gm, t, a, b, measure=str(uuid.uuid4()))).status_code == 404
        assert (await ask(gm, t, a, str(uuid.uuid4()), measure=miles)).status_code == 404
        assert (await ask(gm, t, a, b, measure=miles, mode="sideways")).status_code == 422
        # An entry the reader cannot see is the same 404 as one that is not there.
        player = w.outsider
        hidden = await ask(player, t, a, secret, measure=miles)
        missing = await ask(player, t, a, str(uuid.uuid4()), measure=miles)
        assert hidden.status_code == missing.status_code == 404
        assert hidden.json()["detail"] == missing.json()["detail"]
    finally:
        await w.clean_up()


def shape(body: dict[str, Any]) -> dict[str, Any]:
    """An answer without the ids, so two libraries can be compared."""
    return {
        **{k: v for k, v in body.items() if k not in ("route", "map")},
        "route": [
            [x["connection"]["name"], x["start"]["name"], x["end"]["name"], x["length"]]
            for x in body["route"]
        ],
    }


async def build(w: Any, *, extra: bool) -> dict[str, Any]:
    """The same visible library twice; with `extra`, hidden things that would shorten the route."""
    t, gm, player = w.tenant_id, w.author, w.outsider
    miles = await definition(gm, t, "Miles", "float", "miles")
    a, b, c = await places(gm, t, "Hollowmere", "Dunmere", "Brindle")
    await road(gm, t, a, b, 50, miles, "Open road")
    await road(gm, t, b, c, 50, miles, "Open road two")
    if extra:
        closed = (await place(gm, t, "Closed vault"))["id"]
        # A connection of its own audience, one to a place the reader cannot see, and a hidden
        # place on a would-be shorter way.
        hidden = await made(gm, t, a, c, "Secret road", is_public=False)
        await give(gm, t, hidden["id"], miles, 1.0)
        via_a = await made(gm, t, a, closed, "To the vault", is_public=True)
        via_b = await made(gm, t, closed, c, "From the vault", is_public=True)
        await give(gm, t, via_a["id"], miles, 1.0)
        await give(gm, t, via_b["id"], miles, 1.0)
    return {
        "reader": shape((await ask(player, t, a, c, measure=miles)).json()),
        "writer": shape((await ask(gm, t, a, c, measure=miles)).json()),
    }


async def test_what_the_reader_cannot_see_changes_nothing_they_are_told(
    raw_client, fake_jwks_server
):
    plain, _, _ = await world(raw_client, fake_jwks_server)
    crowded, _, _ = await world(raw_client, fake_jwks_server)
    try:
        without = await build(plain, extra=False)
        with_hidden = await build(crowded, extra=True)

        assert with_hidden["reader"] == without["reader"] == without["writer"]
        assert with_hidden["reader"]["value"] == 100
        # The writer, who sees all of it, gets the shorter route the reader never hears of.
        assert with_hidden["writer"]["value"] == 1
    finally:
        await plain.clean_up()
        await crowded.clean_up()


async def test_the_same_visible_rows_give_the_same_answer_to_a_writer_and_a_reader(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        miles = await definition(gm, t, "Miles", "float", "miles")
        a, b, c = await places(gm, t, "Hollowmere", "Dunmere", "Brindle")
        await road(gm, t, a, b, 3, miles, "A")
        await road(gm, t, b, c, 4, miles, "B")
        await road(gm, t, a, c, None, miles, "C")

        mine = (await ask(gm, t, a, c, measure=miles)).json()
        theirs = (await ask(player, t, a, c, measure=miles)).json()

        assert mine == theirs and mine["value"] == 7
    finally:
        await w.clean_up()


async def test_a_tie_goes_to_the_lower_connection_id(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        miles = await definition(gm, t, "Miles", "float", "miles")
        a, b = await places(gm, t, "Hollowmere", "Dunmere")
        twins = [await road(gm, t, a, b, 5, miles, f"Twin {n}") for n in range(3)]

        got = (await ask(gm, t, a, b, measure=miles)).json()

        assert got["route"][0]["connection"]["id"] == min(x["id"] for x in twins)
    finally:
        await w.clean_up()


async def test_a_cap_is_a_limit_reached_never_an_unknown(raw_client, fake_jwks_server, monkeypatch):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        miles = await definition(gm, t, "Miles", "float", "miles")
        a, b, c, d = await places(gm, t, "Hollowmere", "Dunmere", "Brindle", "Ashford")
        for left, right in ((a, b), (b, c), (c, d)):
            await road(gm, t, left, right, 1, miles)

        monkeypatch.setattr(routing, "MAX_LEGS", 2)
        limited = (await ask(gm, t, a, d, measure=miles)).json()
        assert limited["state"] == "limit_reached" and limited["reason"] == "too much to search"
        assert limited["value"] is None and limited["route"] == []
        assert (await ask(gm, t, a, c, measure=miles)).json()["state"] == "known"
        monkeypatch.setattr(routing, "MAX_LEGS", 64)
        monkeypatch.setattr(routing, "MAX_CONNECTIONS", 2)
        assert (await ask(gm, t, a, d, measure=miles)).json()["state"] == "limit_reached"
    finally:
        await w.clean_up()


async def test_a_signed_in_user_is_limited_and_told_when_to_come_back(
    raw_client, fake_jwks_server, monkeypatch
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        miles = await definition(gm, t, "Miles", "float", "miles")
        a, b = await places(gm, t, "Hollowmere", "Dunmere")
        monkeypatch.setenv("DISTANCE_RATE_LIMIT_PER_MINUTE", "3")
        get_settings.cache_clear()
        reset_user_rate_limiters()
        codes = [(await ask(gm, t, a, b, measure=miles)).status_code for _ in range(3)]
        limited = await ask(gm, t, a, b, measure=miles)
        elsewhere = await ask(w.outsider, t, a, b, measure=miles)

        assert codes == [200, 200, 200]
        assert limited.status_code == 429 and int(limited.headers["retry-after"]) >= 1
        assert elsewhere.status_code == 200
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        reset_user_rate_limiters()
        await w.clean_up()


# --- the straight line -----------------------------------------------------------------------

SCALED = {
    "format": "lorenzo.map-system/1",
    "kind": "plane",
    "extent": [0, 0, 1000, 800],
    "scale": {"per_unit": 0.5, "unit": "miles"},
}


async def test_the_straight_line_is_measured_on_the_map_in_its_own_unit(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a, b = await places(gm, t, "Hollowmere", "Dunmere")
        chart = await make_map(gm, t, "Scaled", system=SCALED, is_public=True)
        assert (await draw(gm, t, chart["id"], a, pin(0, 0))).status_code == 200
        assert (await draw(gm, t, chart["id"], b, pin(300, 400))).status_code == 200

        for who in (gm, player):
            got = (await ask(who, t, a, b, mode="straight")).json()
            assert got["mode"] == "straight" and got["state"] == "known"
            assert got["value"] == 250 and got["unit"] == "miles" and got["route"] == []
            assert got["map"]["id"] == chart["id"] and got["map"]["name"] == "Scaled"
        assert (await ask(gm, t, a, b, mode="straight", map=chart["id"])).json()["value"] == 250
        # A shape is measured from the middle of its box.
        wide = (await place(gm, t, "Wide plain", is_public=True))["id"]
        from test_maps import square

        assert (await draw(gm, t, chart["id"], wide, square(100, 100, 100))).status_code == 200
        got = (await ask(gm, t, a, wide, mode="straight")).json()
        assert got["value"] == pytest.approx(0.5 * (150**2 + 150**2) ** 0.5, abs=1e-6)
    finally:
        await w.clean_up()


async def test_a_grid_counts_cells_by_the_maps_metric(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        a, b = await places(gm, t, "Hollowmere", "Dunmere")
        answers = {}
        for metric in ("chebyshev", "manhattan", "alternating", None):
            system = {
                "format": "lorenzo.map-system/1",
                "kind": "square",
                "extent": [0, 0, 1000, 800],
                "cell": {"size": 50},
                "measure": {"per_cell": 5, "unit": "feet"},
                **({"metric": metric} if metric else {}),
            }
            chart = await make_map(gm, t, f"Grid {metric}", system=system, is_public=True)
            await draw(gm, t, chart["id"], a, pin(25, 25))
            await draw(gm, t, chart["id"], b, pin(175, 125))
            got = (await ask(gm, t, a, b, mode="straight", map=chart["id"])).json()
            answers[metric] = (got["value"], got["unit"])

        assert answers == {
            "chebyshev": (15, "feet"),
            "manhattan": (25, "feet"),
            "alternating": (20, "feet"),
            None: (18.027756, "feet"),
        }
    finally:
        await w.clean_up()


async def test_a_map_that_measures_nothing_says_why_and_never_answers_zero(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        a, b, c = await places(gm, t, "Hollowmere", "Dunmere", "Brindle")
        chart = await make_map(gm, t, "Bare", is_public=True)
        await draw(gm, t, chart["id"], a, pin(10, 10))
        await draw(gm, t, chart["id"], b, pin(20, 20))

        bare = (await ask(gm, t, a, b, mode="straight")).json()
        assert bare["state"] == "unknown" and bare["reason"] == "the Map has no scale"
        assert bare["value"] is None and bare["map"]["id"] == chart["id"]
        apart = (await ask(gm, t, a, c, mode="straight")).json()
        assert apart["state"] == "unknown" and apart["reason"] == "they are not drawn on one Map"
        assert apart["map"] is None
    finally:
        await w.clean_up()


async def test_two_maps_holding_both_places_ask_which_and_a_hidden_map_does_not_count(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a, b = await places(gm, t, "Hollowmere", "Dunmere")
        west = await make_map(gm, t, "West", system=SCALED, is_public=True)
        secret = await make_map(gm, t, "Secret", system=SCALED)
        for chart in (west, secret):
            await draw(gm, t, chart["id"], a, pin(0, 0))
            await draw(gm, t, chart["id"], b, pin(100, 0))

        # The player does not see the second Map, so the first is the only one there is.
        assert (await ask(player, t, a, b, mode="straight")).json()["map"]["name"] == "West"
        assert (await ask(player, t, a, b, mode="straight", map=secret["id"])).status_code == 404
        # The writer sees both and is asked to choose.
        both = await ask(gm, t, a, b, mode="straight")
        assert both.status_code == 422
        chosen = await ask(gm, t, a, b, mode="straight", map=secret["id"])
        assert chosen.json()["map"]["name"] == "Secret" and chosen.json()["value"] == 50
        # Not a Map at all.
        assert (await ask(gm, t, a, b, mode="straight", map=a)).status_code == 404
    finally:
        await w.clean_up()
