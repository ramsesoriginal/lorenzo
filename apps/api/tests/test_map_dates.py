"""The date lens on the Maps list (ADR 0371, 0372): tied, untied or tied to other dates, as the
reader sees it."""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from sqlalchemy import func, select
from test_calendars import make_calendar
from test_maps import make_map
from test_story_sessions import world

from lorenzo_api.models import EntryCalendarPeriod


async def open_up(actor: Any, t: Any, who: str) -> None:
    base = f"/tenants/{t}/entities/{who}/audience"
    current = await actor.get(base)
    assert current.status_code == 200, current.text
    opened = await actor.client.put(
        base,
        headers={**actor.headers, "If-Match": current.headers["etag"]},
        json={**current.json(), "is_public": True},
    )
    assert opened.status_code == 200, opened.text


async def period(actor: Any, t: Any, calendar: str, **date: Any) -> str:
    response = await actor.post(f"/tenants/{t}/calendars/{calendar}/periods", json=date)
    assert response.status_code == 200, response.text
    return str(response.json()["entity_id"])


async def tie(actor: Any, t: Any, who: str, *periods: str) -> None:
    current = await actor.get(f"/tenants/{t}/entities/{who}")
    response = await actor.client.put(
        f"/tenants/{t}/entities/{who}/dates",
        headers={**actor.headers, "If-Match": current.headers["etag"]},
        json={"period_ids": list(periods)},
    )
    assert response.status_code == 200, response.text


async def listing(actor: Any, t: Any, **params: Any) -> dict[str, Any]:
    response = await actor.get(f"/tenants/{t}/maps", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def ties(page: dict[str, Any]) -> list[tuple[str, str]]:
    return [(row["name"], row["tie"]) for row in page["items"]]


async def library(w: Any) -> dict[str, Any]:
    """A calendar, six periods and seven Maps, all public."""
    t, gm = w.tenant_id, w.author
    calendar = (await make_calendar(gm, t)).json()["entity_id"]
    await open_up(gm, t, calendar)
    year = await period(gm, t, calendar, year=3286)
    month = await period(gm, t, calendar, year=3286, segment="first")
    day16 = await period(gm, t, calendar, year=3286, segment="first", day=16)
    day18 = await period(gm, t, calendar, year=3286, segment="first", day=18)
    festival = await period(gm, t, calendar, year=3286, segment="festival", day=1)
    next_year = await period(gm, t, calendar, year=3287)
    for each in (year, month, day16, day18, festival, next_year):
        await open_up(gm, t, each)
    maps = {}
    for name, held in {
        "A year of it": [year],
        "B month of it": [month],
        "C day sixteen": [day16],
        "D day eighteen": [day18],
        "E next year": [next_year],
        "F no date": [],
        "G festival": [festival],
    }.items():
        made = await make_map(gm, t, name, is_public=True)
        maps[name] = made["id"]
        if held:
            await tie(gm, t, made["id"], *held)
    return {"calendar": calendar, "maps": maps}


async def test_a_map_is_tied_untied_or_tied_to_other_dates_and_comes_in_that_order(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        lib = await library(w)
        cal = lib["calendar"]
        for actor in (gm, player):
            # A day is in its month and its year: a Map tied to either is tied to the day.
            day = await listing(
                actor, t, tied_calendar=cal, tied_year=3286, tied_segment="first", tied_day=16
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
            # A month is not in its days: they are tied to other dates.
            month = await listing(actor, t, tied_calendar=cal, tied_year=3286, tied_segment="first")
            assert ties(month) == [
                ("A year of it", "tied"),
                ("B month of it", "tied"),
                ("F no date", "untied"),
                ("C day sixteen", "other"),
                ("D day eighteen", "other"),
                ("E next year", "other"),
                ("G festival", "other"),
            ]
            year = await listing(actor, t, tied_calendar=cal, tied_year=3286)
            assert ties(year)[:1] == [("A year of it", "tied")]
            assert [n for n, c in ties(year) if c == "tied"] == ["A year of it"]
            assert ties(await listing(actor, t, tied_calendar=cal, tied_year=3287))[0] == (
                "E next year",
                "tied",
            )
            # A year with nothing in it ties nothing, and nothing is inferred from a near one.
            empty = await listing(actor, t, tied_calendar=cal, tied_year=1)
            assert [c for _, c in ties(empty)] == ["untied"] + ["other"] * 6
    finally:
        await w.clean_up()


async def test_other_maps_can_be_left_out_before_the_page(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        lib = await library(w)
        asked = {
            "tied_calendar": lib["calendar"],
            "tied_year": 3286,
            "tied_segment": "first",
            "tied_day": 16,
        }
        kept = await listing(gm, t, exclude_other="true", **asked)
        assert ties(kept) == [
            ("A year of it", "tied"),
            ("B month of it", "tied"),
            ("C day sixteen", "tied"),
            ("F no date", "untied"),
        ]
        assert kept["total"] == 4
        first = await listing(gm, t, exclude_other="true", size=2, page=1, **asked)
        second = await listing(gm, t, exclude_other="true", size=2, page=2, **asked)
        assert [n for n, _ in ties(first) + ties(second)] == [n for n, _ in ties(kept)]
        assert first["total"] == second["total"] == 4 and first["pages"] == 2
        # The whole list is longer.
        assert (await listing(gm, t, **asked))["total"] == 7
    finally:
        await w.clean_up()


async def test_without_a_date_the_list_is_what_it_was_and_asking_writes_nothing(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        before_dates = await _links(t)
        lib = await library(w)
        plain = await listing(gm, t)
        assert [row["name"] for row in plain["items"]] == sorted(lib["maps"])
        for row in plain["items"]:
            assert set(row) == {"id", "name", "slug", "kinds"}
        await listing(gm, t, tied_calendar=lib["calendar"], tied_year=3286)
        await listing(player, t, tied_calendar=lib["calendar"], tied_year=3286)
        assert await listing(gm, t) == plain
        assert await _links(t) == before_dates + 6
    finally:
        await w.clean_up()


async def _links(t: Any) -> int:
    async with admin_session_factory() as session:
        return int(
            await session.scalar(
                select(func.count())
                .select_from(EntryCalendarPeriod)
                .where(EntryCalendarPeriod.tenant_id == t)
            )
            or 0
        )


async def test_a_date_the_reader_cannot_see_is_no_date(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        lib = await library(w)
        cal = lib["calendar"]
        # A Map tied only to a period of a calendar the reader may not open, and to one of a
        # public calendar whose period is private.
        closed = (await make_calendar(gm, t, name="Closed calendar")).json()["entity_id"]
        closed_period = await period(gm, t, closed, year=3286)
        await open_up(gm, t, closed_period)
        private_period = await period(gm, t, cal, year=3290)
        in_closed = await make_map(gm, t, "H in a closed calendar", is_public=True)
        in_private = await make_map(gm, t, "I at a private period", is_public=True)
        await tie(gm, t, in_closed["id"], closed_period)
        await tie(gm, t, in_private["id"], private_period)

        asked = {"tied_calendar": cal, "tied_year": 3290}
        for_gm = dict(ties(await listing(gm, t, **asked)))
        for_player = dict(ties(await listing(player, t, **asked)))
        # The GM sees the dates: tied to the private period, and to another calendar's.
        assert for_gm["I at a private period"] == "tied"
        assert for_gm["H in a closed calendar"] == "other"
        # For the player they are not there: not tied to a date.
        assert for_player["I at a private period"] == "untied"
        assert for_player["H in a closed calendar"] == "untied"
        # Nor can they look through the calendar they cannot open.
        refused = await player.get(
            f"/tenants/{t}/maps", params={"tied_calendar": closed, "tied_year": 3286}
        )
        missing = await player.get(
            f"/tenants/{t}/maps", params={"tied_calendar": str(uuid.uuid4()), "tied_year": 3286}
        )
        assert refused.status_code == missing.status_code == 404
        assert refused.json()["detail"] == missing.json()["detail"]
        assert (await listing(gm, t, tied_calendar=closed, tied_year=3286))["total"] == 9
    finally:
        await w.clean_up()


async def test_what_is_not_a_date_is_refused(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        lib = await library(w)
        cal = lib["calendar"]
        chart = next(iter(lib["maps"].values()))

        def get(**params: Any) -> Any:
            return gm.get(f"/tenants/{t}/maps", params=params)

        for params in (
            {"tied_calendar": cal},
            {"tied_calendar": cal, "tied_segment": "first"},
            {"tied_calendar": cal, "tied_year": 1, "tied_day": 3},
            {"tied_calendar": cal, "tied_year": 1, "tied_segment": "First"},
            {"tied_calendar": cal, "tied_year": 1, "tied_segment": "first", "tied_day": 0},
            {"tied_calendar": cal, "tied_year": 2_000_000},
            {"tied_year": 3286},
            {"tied_segment": "first"},
            {"exclude_other": "true"},
        ):
            assert (await get(**params)).status_code == 422, params
        # A Map is not a Calendar.
        assert (await get(tied_calendar=chart, tied_year=1)).status_code == 404
    finally:
        await w.clean_up()
