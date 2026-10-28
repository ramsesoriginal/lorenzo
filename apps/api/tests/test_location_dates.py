"""The date lens on the Locations list (ADR 0374), held to the Maps list's own results: one rule,
two lists."""

from typing import Any

from test_calendars import make_calendar
from test_locations import place
from test_map_dates import _links, open_up, period, tie
from test_maps import make_map
from test_story_sessions import world

NAMES = {
    "A year of it": "year",
    "B month of it": "month",
    "C day sixteen": "day16",
    "D day eighteen": "day18",
    "E next year": "next",
    "F no date": None,
    "G festival": "festival",
}


async def both(w: Any) -> dict[str, Any]:
    """A calendar and, for each name, a Map and a Location tied to the same period."""
    t, gm = w.tenant_id, w.author
    calendar = (await make_calendar(gm, t)).json()["entity_id"]
    await open_up(gm, t, calendar)
    dates = {
        "year": {"year": 3286},
        "month": {"year": 3286, "segment": "first"},
        "day16": {"year": 3286, "segment": "first", "day": 16},
        "day18": {"year": 3286, "segment": "first", "day": 18},
        "festival": {"year": 3286, "segment": "festival", "day": 1},
        "next": {"year": 3287},
    }
    ids = {key: await period(gm, t, calendar, **date) for key, date in dates.items()}
    for each in ids.values():
        await open_up(gm, t, each)
    for name, key in NAMES.items():
        chart = await make_map(gm, t, name, is_public=True)
        spot = await place(gm, t, name, is_public=True)
        if key:
            await tie(gm, t, chart["id"], ids[key])
            await tie(gm, t, spot["id"], ids[key])
    return {"calendar": calendar, "periods": ids}


async def maps(actor: Any, t: Any, **params: Any) -> dict[str, Any]:
    response = await actor.get(f"/tenants/{t}/maps", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def locations(actor: Any, t: Any, **params: Any) -> dict[str, Any]:
    response = await actor.get(f"/tenants/{t}/locations", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def ties(page: dict[str, Any]) -> list[tuple[str, str]]:
    return [(row["name"], row["tie"]) for row in page["items"]]


async def test_a_location_and_a_map_tied_alike_read_alike_for_every_reader(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        cal = (await both(w))["calendar"]
        asks = [
            {"tied_year": 3286, "tied_segment": "first", "tied_day": 16},
            {"tied_year": 3286, "tied_segment": "first"},
            {"tied_year": 3286},
            {"tied_year": 3287},
            {"tied_year": 1},
            {"tied_year": 3286, "tied_segment": "festival", "tied_day": 1},
        ]
        for actor in (w.author, w.outsider):
            for ask in asks:
                for extra in ({}, {"exclude_other": "true"}):
                    one = {"tied_calendar": cal, **ask, **extra}
                    assert ties(await locations(actor, t, **one)) == ties(
                        await maps(actor, t, **one)
                    ), one
        # And the three classes, in their order, through a day.
        day = await locations(
            w.author, t, tied_calendar=cal, tied_year=3286, tied_segment="first", tied_day=16
        )
        assert ties(day) == [
            ("A year of it", "tied"),
            ("B month of it", "tied"),
            ("C day sixteen", "tied"),
            ("F no date", "untied"),
            ("D day eighteen", "other"),
            ("E next year", "other"),
            ("G festival", "other"),
        ]
    finally:
        await w.clean_up()


async def test_other_locations_can_be_left_out_before_the_page(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        cal = (await both(w))["calendar"]
        asked = {"tied_calendar": cal, "tied_year": 3286, "tied_segment": "first", "tied_day": 16}
        kept = await locations(gm, t, exclude_other="true", **asked)
        assert [n for n, _ in ties(kept)] == [
            "A year of it",
            "B month of it",
            "C day sixteen",
            "F no date",
        ]
        assert kept["total"] == 4
        first = await locations(gm, t, exclude_other="true", size=3, page=1, **asked)
        second = await locations(gm, t, exclude_other="true", size=3, page=2, **asked)
        assert [n for n, _ in ties(first) + ties(second)] == [n for n, _ in ties(kept)]
        assert first["total"] == 4 and first["pages"] == 2
        assert (await locations(gm, t, **asked))["total"] == 7
        # A search narrows it.
        found = await locations(gm, t, q="month", **asked)
        assert ties(found) == [("B month of it", "tied")]
    finally:
        await w.clean_up()


async def test_without_a_date_the_reads_are_what_they_were_and_a_date_takes_no_tree(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        town = await place(gm, t, "Town", is_public=True)
        inn = await place(gm, t, "Inn", is_public=True, parent_id=town["id"])
        before_links = await _links(t)
        lib = await both(w)
        before_roots = (await gm.get(f"/tenants/{t}/locations", params={"root": "true"})).content
        before_parts = (await gm.get(f"/tenants/{t}/locations/{town['id']}/parts")).content
        # The list keeps its keys; the tree and the parts do not change by a byte.
        plain = await locations(player, t)
        for row in plain["items"]:
            assert set(row) == {"id", "name", "slug", "kinds", "level_ordinal"}
        await locations(gm, t, tied_calendar=lib["calendar"], tied_year=3286)
        assert (
            await gm.get(f"/tenants/{t}/locations", params={"root": "true"})
        ).content == before_roots
        assert (await gm.get(f"/tenants/{t}/locations/{town['id']}/parts")).content == before_parts
        # A date and the tree of roots together is refused, in words.
        refused = await gm.get(
            f"/tenants/{t}/locations",
            params={"root": "true", "tied_calendar": lib["calendar"], "tied_year": 3286},
        )
        assert refused.status_code == 422 and "tree" in refused.json()["detail"]
        # A date is the Location's own: not passed down to what is part of it, nor up.
        await tie(gm, t, town["id"], lib["periods"]["year"])
        through = dict(ties(await locations(gm, t, tied_calendar=lib["calendar"], tied_year=3286)))
        assert through["Town"] == "tied" and through["Inn"] == "untied"
        await tie(gm, t, town["id"])
        await tie(gm, t, inn["id"], lib["periods"]["year"])
        through = dict(ties(await locations(gm, t, tied_calendar=lib["calendar"], tied_year=3286)))
        assert through["Inn"] == "tied" and through["Town"] == "untied"
        # Asking writes nothing.
        links = await _links(t)
        await locations(player, t, tied_calendar=lib["calendar"], tied_year=3286)
        assert await _links(t) == links and links > before_links
    finally:
        await w.clean_up()


async def test_a_date_the_reader_cannot_see_is_no_date_for_a_location_either(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        cal = (await both(w))["calendar"]
        closed = (await make_calendar(gm, t, name="Closed calendar")).json()["entity_id"]
        closed_period = await period(gm, t, closed, year=3286)
        await open_up(gm, t, closed_period)
        private_period = await period(gm, t, cal, year=3290)
        in_closed = await place(gm, t, "H in a closed calendar", is_public=True)
        in_private = await place(gm, t, "I at a private period", is_public=True)
        await tie(gm, t, in_closed["id"], closed_period)
        await tie(gm, t, in_private["id"], private_period)
        asked = {"tied_calendar": cal, "tied_year": 3290}
        for_gm = dict(ties(await locations(gm, t, **asked)))
        for_player = dict(ties(await locations(player, t, **asked)))
        assert for_gm["I at a private period"] == "tied"
        assert for_gm["H in a closed calendar"] == "other"
        assert for_player["I at a private period"] == "untied"
        assert for_player["H in a closed calendar"] == "untied"
        refused = await player.get(
            f"/tenants/{t}/locations", params={"tied_calendar": closed, "tied_year": 3286}
        )
        missing = await player.get(
            f"/tenants/{t}/locations",
            params={"tied_calendar": "00000000-0000-0000-0000-000000000001", "tied_year": 1},
        )
        assert refused.status_code == missing.status_code == 404
        assert refused.json()["detail"] == missing.json()["detail"]
    finally:
        await w.clean_up()


async def test_the_refusals_are_the_maps_lists_refusals(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        lib = await both(w)
        cal = lib["calendar"]
        chart = (await maps(gm, t))["items"][0]["id"]
        for params in (
            {"tied_calendar": cal},
            {"tied_calendar": cal, "tied_segment": "first"},
            {"tied_calendar": cal, "tied_year": 1, "tied_day": 3},
            {"tied_calendar": cal, "tied_year": 1, "tied_segment": "First"},
            {"tied_calendar": cal, "tied_year": 1, "tied_segment": "first", "tied_day": 0},
            {"tied_calendar": cal, "tied_year": 2_000_000},
            {"tied_year": 3286},
            {"exclude_other": "true"},
        ):
            for path in ("locations", "maps"):
                got = await gm.get(f"/tenants/{t}/{path}", params=params)
                assert got.status_code == 422, (path, params)
        assert (
            await gm.get(f"/tenants/{t}/locations", params={"tied_calendar": chart, "tied_year": 1})
        ).status_code == 404
    finally:
        await w.clean_up()
