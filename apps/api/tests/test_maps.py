"""Maps and their placements (ADR 0336 to 0338)."""

import pathlib
import uuid
from typing import Any

from _admin_db import admin_session_factory
from sqlalchemy import func, select, text
from test_locations import place
from test_placement import entry
from test_story_sessions import world

from lorenzo_api.models import AuditLog, Map, MapPlacement

SYSTEM = {"format": "lorenzo.map-system/1", "kind": "plane", "extent": [0, 0, 1000, 800]}


def pin(x: float, y: float) -> dict[str, Any]:
    return {"format": "lorenzo.geometry/1", "parts": [{"shape": "point", "at": [x, y]}]}


def line(*points: tuple[float, float]) -> dict[str, Any]:
    return {
        "format": "lorenzo.geometry/1",
        "parts": [{"shape": "polyline", "pts": [list(p) for p in points]}],
    }


def square(x: float, y: float, size: float) -> dict[str, Any]:
    ring = [[x, y], [x + size, y], [x + size, y + size], [x, y + size]]
    return {"format": "lorenzo.geometry/1", "parts": [{"shape": "polygon", "rings": [ring]}]}


async def make_map(actor: Any, t: Any, name: str = "Sword Coast", **fields: Any) -> dict[str, Any]:
    response = await actor.post(
        f"/tenants/{t}/maps", json={"name": name, "system": SYSTEM, **fields}
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def draw(actor: Any, t: Any, chart: str, who: str, geometry: dict[str, Any], **fields: Any):
    return await actor.put(
        f"/tenants/{t}/maps/{chart}/placements/{who}", json={"geometry": geometry, **fields}
    )


async def read(actor: Any, t: Any, chart: str, **params: Any) -> dict[str, Any]:
    response = await actor.get(f"/tenants/{t}/maps/{chart}/placements", params=params)
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def ids(page: dict[str, Any]) -> list[str]:
    return [row["id"] for row in page["items"]]


async def test_a_map_is_made_read_listed_and_changed(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        town = await place(gm, t, "Neverwinter", is_public=True)
        made = await make_map(gm, t, is_public=True, subject_entity_id=town["id"], slug="coast")
        assert made["kinds"] == ["map"] and made["slug"] == "coast"
        assert made["system"] == SYSTEM and made["subject"]["name"] == "Neverwinter"
        assert made["can_manage"] is True and made["is_public"] is True
        header = await gm.get(f"/tenants/{t}/maps/{made['id']}")
        assert header.headers["etag"] and header.json() == made
        # A reader sees it, without the manager's field.
        seen = await player.get(f"/tenants/{t}/maps/{made['id']}")
        assert seen.status_code == 200 and seen.json()["can_manage"] is False
        assert seen.json()["is_public"] is None and seen.json()["subject"]["name"] == "Neverwinter"
        listed = await player.get(f"/tenants/{t}/maps", params={"q": "COAST"})
        assert [row["name"] for row in listed.json()["items"]] == ["Sword Coast"]
        # The entry routes see the kind.
        entity = await gm.get(f"/tenants/{t}/entities/{made['id']}")
        assert entity.json()["kinds"] == ["map"]
        # PUT needs the version, and a stale one fails.
        url = f"/tenants/{t}/maps/{made['id']}"
        body = {"system": {**SYSTEM, "kind": "outline"}, "subject_entity_id": None}
        assert (await gm.client.put(url, headers=gm.headers, json=body)).status_code == 428
        stale = await gm.client.put(
            url, headers={**gm.headers, "If-Match": 'W/"2000-01-01T00:00:00Z"'}, json=body
        )
        assert stale.status_code == 412
        saved = await gm.client.put(
            url, headers={**gm.headers, "If-Match": header.headers["etag"]}, json=body
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["system"]["kind"] == "outline" and saved.json()["subject"] is None
        assert saved.headers["etag"] != header.headers["etag"]
        # A player may not write.
        assert (
            await player.client.put(
                url, headers={**player.headers, "If-Match": saved.headers["etag"]}, json=body
            )
        ).status_code == 403
        assert (
            await player.post(f"/tenants/{t}/maps", json={"name": "X", "system": SYSTEM})
        ).status_code == 403
    finally:
        await w.clean_up()


async def test_a_map_document_the_validator_refuses_is_a_422(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        for system in (
            {"format": "lorenzo.map-system/1", "kind": "sphere", "extent": [0, 0, 1, 1]},
            {"format": "lorenzo.map-system/1", "kind": "plane", "extent": [0, 0, 0, 1]},
            {"kind": "plane"},
        ):
            refused = await gm.post(f"/tenants/{t}/maps", json={"name": "Bad", "system": system})
            assert refused.status_code == 422, refused.text
        # A subject that is no Location, or that is missing, is the generic 404.
        thing = await entry(gm, t, "Thing")
        for subject in (thing, str(uuid.uuid4())):
            missing = await gm.post(
                f"/tenants/{t}/maps",
                json={"name": "M", "system": SYSTEM, "subject_entity_id": subject},
            )
            assert missing.status_code == 404, missing.text
        # A Map is never made by POST /entities, and the kind route takes its system.
        refused = await gm.post(f"/tenants/{t}/entities", json={"name": "M", "kinds": ["map"]})
        assert refused.status_code == 422
        plain = await entry(gm, t, "Plain")
        assert (await gm.put(f"/tenants/{t}/entities/{plain}/kinds/map")).status_code == 422
        added = await gm.put(f"/tenants/{t}/entities/{plain}/kinds/map", json={"system": SYSTEM})
        assert added.status_code in (200, 201), added.text
        assert (await gm.get(f"/tenants/{t}/maps/{plain}")).status_code == 200
        wrong = await gm.put(f"/tenants/{t}/entities/{thing}/kinds/item", json={"system": SYSTEM})
        assert wrong.status_code == 422
    finally:
        await w.clean_up()


async def test_a_hidden_map_and_a_missing_one_answer_alike(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        hidden = await make_map(gm, t, "Secret chart")
        thing = await entry(gm, t, "Thing")
        answers = []
        for target in (hidden["id"], str(uuid.uuid4()), thing):
            for path in ("", "/placements"):
                response = await player.get(f"/tenants/{t}/maps/{target}{path}")
                answers.append((response.status_code, response.json().get("detail")))
        assert {status for status, _ in answers} == {404}
        assert len({detail for _, detail in answers}) == 1
        assert (await player.get(f"/tenants/{t}/maps")).json()["items"] == []
    finally:
        await w.clean_up()


async def test_placements_are_drawn_redrawn_and_removed(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, is_public=True))["id"]
        keep = await place(gm, t, "Waterdeep", is_public=True)
        drawn = await draw(gm, t, chart, keep["id"], pin(10, 20), role="site", z=3)
        assert drawn.status_code == 200, drawn.text
        assert drawn.json()["role"] == "site" and drawn.json()["z"] == 3
        header = await gm.get(f"/tenants/{t}/maps/{chart}")
        # Redrawing replaces, and moves the Map's version.
        again = await draw(
            gm, t, chart, keep["id"], line((0, 0), (5, 5)), style={"stroke": "dashed"}
        )
        assert again.status_code == 200, again.text
        page = await read(gm, t, chart)
        assert [(r["name"], r["role"], r["style"], r["z"]) for r in page["items"]] == [
            ("Waterdeep", None, {"stroke": "dashed"}, 0)
        ]
        assert page["items"][0]["kinds"] == ["location"]
        assert (await gm.get(f"/tenants/{t}/maps/{chart}")).headers["etag"] != header.headers[
            "etag"
        ]
        async with admin_session_factory() as session:
            stored = await session.get(MapPlacement, (uuid.UUID(chart), uuid.UUID(keep["id"])))
            assert stored is not None
            assert (stored.minx, stored.miny, stored.maxx, stored.maxy) == (0, 0, 5, 5)
            assert stored.bytes > 0
        # What the validator refuses.
        for geometry, extra in (
            ({"format": "lorenzo.geometry/1", "parts": []}, {}),
            (pin(1, 2), {"role": "dragon"}),
            (pin(1, 2), {"style": {"stroke": "wavy"}}),
            (pin(1, 2), {"z": 101}),
            (
                {
                    "format": "lorenzo.geometry/1",
                    "parts": [
                        {
                            "shape": "polygon",
                            "rings": [[[0, 0], [10, 10], [10, 0], [0, 10]]],
                        }
                    ],
                },
                {},
            ),
        ):
            refused = await draw(gm, t, chart, keep["id"], geometry, **extra)
            assert refused.status_code == 422, (geometry, extra, refused.text)
        # An unknown entry, a hidden one for a writer who cannot see it, and a missing Map.
        assert (await draw(gm, t, chart, str(uuid.uuid4()), pin(1, 1))).status_code == 404
        assert (await draw(gm, t, str(uuid.uuid4()), keep["id"], pin(1, 1))).status_code == 404
        removed = await gm.delete(f"/tenants/{t}/maps/{chart}/placements/{keep['id']}")
        assert removed.status_code == 204
        assert (await read(gm, t, chart))["items"] == []
        # Removing again is quiet.
        assert (
            await gm.delete(f"/tenants/{t}/maps/{chart}/placements/{keep['id']}")
        ).status_code == 204
        # A player may not draw.
        denied = await draw(w.outsider, t, chart, keep["id"], pin(1, 1))
        assert denied.status_code == 403
    finally:
        await w.clean_up()


async def test_pages_follow_the_drawing_order_and_the_filters_narrow_them(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, is_public=True))["id"]
        made = {}
        for name, geometry, extra in (
            ("Road", line((0, 0), (400, 0)), {"role": "route", "z": 1}),
            ("Lake", square(100, 100, 100), {"role": "water", "z": -1}),
            ("Inn", pin(300, 300), {"role": "site", "z": 1}),
            ("Hut", pin(900, 700), {"role": "site", "z": 1}),
            ("Moor", square(500, 500, 10), {"role": "ground", "z": 1}),
        ):
            made[name] = await entry(gm, t, name)
            assert (await draw(gm, t, chart, made[name], geometry, **extra)).status_code == 200
        full = await read(gm, t, chart)
        assert full["next_cursor"] is None
        order = ids(full)
        assert order[0] == made["Lake"]
        assert order[1:] == sorted(order[1:])  # z ties break on the entry id
        # Pages of two walk the same order without a gap or repeat.
        walked: list[str] = []
        cursor = None
        pages = 0
        while True:
            page = await read(gm, t, chart, limit=2, **({"cursor": cursor} if cursor else {}))
            walked += ids(page)
            pages += 1
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert walked == order and pages == 3
        # Filters.
        assert set(ids(await read(gm, t, chart, bbox="0,0,400,400"))) == {
            made["Road"],
            made["Lake"],
            made["Inn"],
        }
        assert set(ids(await read(gm, t, chart, role=["route", "water"]))) == {
            made["Road"],
            made["Lake"],
        }
        assert set(ids(await read(gm, t, chart, min_diag=50))) == {made["Road"], made["Lake"]}
        for bad in ("1,2,3", "a,b,c,d", "5,0,1,1", "0,0,nan,1"):
            assert (
                await gm.get(f"/tenants/{t}/maps/{chart}/placements", params={"bbox": bad})
            ).status_code == 422
        assert (
            await gm.get(f"/tenants/{t}/maps/{chart}/placements", params={"cursor": "nonsense"})
        ).status_code == 422
        assert (
            await gm.get(f"/tenants/{t}/maps/{chart}/placements", params={"limit": 201})
        ).status_code == 422
    finally:
        await w.clean_up()


async def test_a_hidden_entry_leaves_no_row_gap_or_count(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        with_hidden = (await make_map(gm, t, "With", is_public=True))["id"]
        without = (await make_map(gm, t, "Without", is_public=True))["id"]
        shown = [await place(gm, t, f"Shown {i}", is_public=True) for i in range(3)]
        secret = await place(gm, t, "Secret")
        for i, one in enumerate(shown):
            for chart in (with_hidden, without):
                assert (await draw(gm, t, chart, one["id"], pin(i, i), z=i)).status_code == 200
        assert (await draw(gm, t, with_hidden, secret["id"], pin(9, 9), z=1)).status_code == 200
        # A page of the reader with a hidden placement equals one for whom it does not exist,
        # across the page boundary too.
        for limit in (200, 1, 2):
            walked = {}
            for chart in (with_hidden, without):
                rows: list[Any] = []
                cursor = None
                while True:
                    params: dict[str, Any] = {"limit": limit}
                    if cursor:
                        params["cursor"] = cursor
                    page = (
                        await player.get(f"/tenants/{t}/maps/{chart}/placements", params=params)
                    ).json()
                    rows += [(r["name"], r["z"]) for r in page["items"]]
                    cursor = page["next_cursor"]
                    if cursor is None:
                        break
                walked[chart] = rows
            assert walked[with_hidden] == walked[without] and len(walked[without]) == 3
        # The manager sees all four.
        assert len(ids(await read(gm, t, with_hidden))) == 4
        one = await player.get(f"/tenants/{t}/maps/{with_hidden}/placements")
        assert set(one.json()) == {"items", "next_cursor"}
    finally:
        await w.clean_up()


async def test_the_placements_etag_answers_304(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        chart = (await make_map(gm, t, is_public=True))["id"]
        one = await place(gm, t, "Keep", is_public=True)
        await draw(gm, t, chart, one["id"], pin(1, 1))
        url = f"/tenants/{t}/maps/{chart}/placements"
        first = await player.get(url)
        assert first.headers["cache-control"] == "private, no-cache"
        token = first.headers["etag"]
        same = await player.client.get(url, headers={**player.headers, "If-None-Match": token})
        assert same.status_code == 304 and same.content == b""
        await draw(gm, t, chart, one["id"], pin(2, 2))
        moved = await player.client.get(url, headers={**player.headers, "If-None-Match": token})
        assert moved.status_code == 200 and moved.headers["etag"] != token
        # A manager who sees more has another tag.
        assert (await gm.get(url)).headers["etag"] == moved.headers["etag"]
        secret = await place(gm, t, "Secret")
        await draw(gm, t, chart, secret["id"], pin(3, 3))
        assert (await gm.get(url)).headers["etag"] != (await player.get(url)).headers["etag"]
    finally:
        await w.clean_up()


async def test_the_limits_of_a_map_and_a_library(raw_client, fake_jwks_server, monkeypatch):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        import lorenzo_api.maps as limits

        monkeypatch.setattr(limits, "MAX_MAPS_PER_LIBRARY", 1)
        monkeypatch.setattr(limits, "MAX_PLACEMENTS_PER_MAP", 1)
        chart = (await make_map(gm, t, is_public=True))["id"]
        over = await gm.post(f"/tenants/{t}/maps", json={"name": "Two", "system": SYSTEM})
        assert over.status_code == 422
        first, second = await entry(gm, t, "One"), await entry(gm, t, "Two")
        assert (await draw(gm, t, chart, first, pin(1, 1))).status_code == 200
        assert (await draw(gm, t, chart, second, pin(2, 2))).status_code == 422
        # Redrawing the one that is there is not growth.
        assert (await draw(gm, t, chart, first, pin(3, 3))).status_code == 200
    finally:
        await w.clean_up()


async def test_deleting_what_a_map_draws_or_shows_leaves_the_map(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        town = await place(gm, t, "Town", is_public=True)
        chart = (await make_map(gm, t, is_public=True, subject_entity_id=town["id"]))["id"]
        thing = await entry(gm, t, "Thing")
        await draw(gm, t, chart, thing, pin(1, 1))
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM entity WHERE id = :id AND tenant_id = :t"),
                {"id": thing, "t": t},
            )
            await session.commit()
        assert (await read(gm, t, chart))["items"] == []
        async with admin_session_factory() as session:
            count = await session.scalar(
                select(func.count()).select_from(MapPlacement).where(MapPlacement.tenant_id == t)
            )
            assert count == 0
            assert await session.get(Map, uuid.UUID(chart)) is not None
    finally:
        await w.clean_up()


def test_no_reach_code_reads_a_map_placement():
    source = pathlib.Path(__file__).parents[1] / "src" / "lorenzo_api"
    for module in ("entity_access.py", "information_visibility.py", "campaign_access.py"):
        text = (source / module).read_text()
        assert "MapPlacement" not in text and "map_placement" not in text, module


async def test_a_copy_carries_a_map_and_its_placements_and_drops_what_is_not_valid() -> None:
    """The planner revalidates each placement, keeps the derived columns, and a placement whose
    entry is not copied is not in the copy."""
    from datetime import UTC, datetime

    from _repository_fixtures import seed_every_content_table

    from lorenzo_api.models import RepositorySubscription, Tenant, TenantKind
    from lorenzo_api.repository_copying import plan_copy

    async with admin_session_factory() as session:
        repository = Tenant(name="Faerûn maps", kind=TenantKind.REPOSITORY)
        library = Tenant(name="My Table maps")
        session.add_all([repository, library])
        await session.flush()
        await seed_every_content_table(session, repository.id)
        session.add(
            RepositorySubscription(
                repository_tenant_id=repository.id, subscriber_tenant_id=library.id
            )
        )
        repository.published_at = datetime.now(UTC)
        await session.commit()
        repository_id, library_id = repository.id, library.id
    try:
        async with admin_session_factory() as session:
            await session.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(library_id)}
            )
            plan = await plan_copy(
                session,
                tenant_id=library_id,
                repository_id=repository_id,
                user_id=uuid.uuid4(),
                resolutions=[],
            )
        (chart,) = plan.rows["map"]
        assert chart["system"]["kind"] == "plane" and chart["subject_entity_id"] is None
        assert chart["theme_hint"] == "plain"
        assert chart["view"] == {"grid": {"kind": "square", "cell": {"size": 2}}}
        (placed,) = plan.rows["map_placement"]
        assert placed["map_entity_id"] == chart["entity_id"] and placed["role"] == "site"
        assert (placed["minx"], placed["miny"], placed["maxx"], placed["maxy"]) == (1, 2, 1, 2)
        assert placed["bytes"] > 0 and placed["tenant_id"] == library_id
        # The picture under the Map goes with its Information, keeping the review fingerprint.
        import hashlib

        (layer,) = plan.rows["map_layer"]
        backdrop = next(i for i in plan.rows["information"] if i["title"] == "Backdrop")
        assert layer["map_entity_id"] == chart["entity_id"] and layer["position"] == 0
        assert layer["information_id"] == backdrop["id"] and layer["opacity"] == 0.5
        assert layer["calibration"]["anchors"][1]["at"] == [10, 10]
        assert layer["reviewed_sha256"] == hashlib.sha256(b"\x89PNG").digest()
    finally:
        async with admin_session_factory() as session:
            for tenant_id in (library_id, repository_id):
                await session.delete(await session.get_one(Tenant, tenant_id))
            await session.commit()


async def test_a_theme_name_is_written_read_and_refused_when_unknown(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        made = await make_map(gm, t, is_public=True, theme_hint="plain")
        assert made["theme_hint"] == "plain"
        assert (await make_map(gm, t, "Plain one"))["theme_hint"] is None
        refused = await gm.post(
            f"/tenants/{t}/maps", json={"name": "X", "system": SYSTEM, "theme_hint": "tube"}
        )
        assert refused.status_code == 422, refused.text
        url = f"/tenants/{t}/maps/{made['id']}"
        header = await gm.get(url)
        assert header.json()["theme_hint"] == "plain"
        body = {"system": SYSTEM, "subject_entity_id": None, "theme_hint": "default"}
        saved = await gm.client.put(
            url, headers={**gm.headers, "If-Match": header.headers["etag"]}, json=body
        )
        assert saved.status_code == 200 and saved.json()["theme_hint"] == "default"
        cleared = await gm.client.put(
            url,
            headers={**gm.headers, "If-Match": saved.headers["etag"]},
            json={"system": SYSTEM},
        )
        assert cleared.json()["theme_hint"] is None
        # A name this version does not know is kept as it is.
        async with admin_session_factory() as session:
            row = await session.get(Map, uuid.UUID(made["id"]))
            assert row is not None
            row.theme_hint = "tube"
            await session.commit()
        assert (await gm.get(url)).json()["theme_hint"] == "tube"
    finally:
        await w.clean_up()


async def batch(actor: Any, t: Any, chart: str, **body: Any):
    return await actor.post(f"/tenants/{t}/maps/{chart}/placements/batch", json=body)


async def test_a_batch_draws_redraws_and_removes_as_one(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        chart = (await make_map(gm, t, is_public=True))["id"]
        one = await entry(gm, t, "One")
        two = await entry(gm, t, "Two")
        three = await entry(gm, t, "Three")
        elsewhere = await entry(gm, t, "Elsewhere")
        before = await gm.get(f"/tenants/{t}/maps/{chart}")
        made = await batch(
            gm,
            t,
            chart,
            put=[
                {"entry_id": one, "geometry": pin(1, 1), "role": "site"},
                {"entry_id": two, "geometry": square(10, 10, 5), "z": 2},
                {"entry_id": three, "geometry": pin(3, 3)},
            ],
        )
        assert made.status_code == 200 and made.json() == {"put": 3, "removed": 0}
        assert len(ids(await read(gm, t, chart))) == 3
        # One touch for the whole batch, and one activity entry.
        after = await gm.get(f"/tenants/{t}/maps/{chart}")
        assert after.headers["etag"] != before.headers["etag"]
        async with admin_session_factory() as session:
            logged = await session.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.tenant_id == t, AuditLog.action == "map.placements_changed")
            )
            assert logged == 1
        # Redraw one, remove one and one that is not there, in one go.
        mixed = await batch(
            gm,
            t,
            chart,
            put=[{"entry_id": one, "geometry": pin(9, 9), "role": "marker"}],
            remove=[two, elsewhere],
        )
        assert mixed.json() == {"put": 1, "removed": 1}
        page = await read(gm, t, chart)
        assert {r["name"]: (r["role"], r["geometry"]["parts"][0]["at"]) for r in page["items"]} == {
            "One": ("marker", [9, 9]),
            "Three": (None, [3, 3]),
        }
        # An empty batch changes nothing, and a player may not write.
        assert (await batch(gm, t, chart)).json() == {"put": 0, "removed": 0}
        assert (await batch(player, t, chart, remove=[one])).status_code == 403
    finally:
        await w.clean_up()


async def test_a_batch_that_is_refused_writes_nothing(raw_client, fake_jwks_server, monkeypatch):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, is_public=True))["id"]
        one, two = await entry(gm, t, "One"), await entry(gm, t, "Two")
        third = await entry(gm, t, "Third")
        bad = {"format": "lorenzo.geometry/1", "parts": []}
        refused = await batch(
            gm,
            t,
            chart,
            put=[{"entry_id": one, "geometry": pin(1, 1)}, {"entry_id": two, "geometry": bad}],
        )
        assert refused.status_code == 422 and "put[1]" in refused.json()["detail"]
        assert (await read(gm, t, chart))["items"] == []
        # The same entry twice, an entry that is missing, and a batch that is too big.
        twice = await batch(
            gm, t, chart, put=[{"entry_id": one, "geometry": pin(1, 1)}], remove=[one]
        )
        assert twice.status_code == 422
        missing = await batch(
            gm,
            t,
            chart,
            put=[
                {"entry_id": one, "geometry": pin(1, 1)},
                {"entry_id": str(uuid.uuid4()), "geometry": pin(2, 2)},
            ],
        )
        assert missing.status_code == 404
        assert (await read(gm, t, chart))["items"] == []
        many = [{"entry_id": str(uuid.uuid4()), "geometry": pin(1, 1)} for _ in range(101)]
        assert (await batch(gm, t, chart, put=many)).status_code == 422
        # The placement cap counts only the rows a batch adds.
        import lorenzo_api.maps as limits

        monkeypatch.setattr(limits, "MAX_PLACEMENTS_PER_MAP", 2)
        assert (await draw(gm, t, chart, one, pin(1, 1))).status_code == 200
        over = await batch(
            gm,
            t,
            chart,
            put=[
                {"entry_id": two, "geometry": pin(2, 2)},
                {"entry_id": third, "geometry": pin(3, 3)},
            ],
        )
        assert over.status_code == 422
        fits = await batch(
            gm,
            t,
            chart,
            put=[
                {"entry_id": one, "geometry": pin(5, 5)},
                {"entry_id": two, "geometry": pin(2, 2)},
            ],
        )
        assert fits.json() == {"put": 2, "removed": 0}
    finally:
        await w.clean_up()


EXTENT = [0, 0, 1000, 800]
GRIDS = {
    "square": {
        "format": "lorenzo.map-system/1",
        "kind": "square",
        "extent": EXTENT,
        "cell": {"size": 50},
    },
    "rect": {
        "format": "lorenzo.map-system/1",
        "kind": "rect",
        "extent": EXTENT,
        "cell": {"width": 60, "height": 40},
    },
    "pointy": {
        "format": "lorenzo.map-system/1",
        "kind": "hex",
        "orientation": "pointy",
        "extent": EXTENT,
        "cell": {"size": 58},
    },
    "flat": {
        "format": "lorenzo.map-system/1",
        "kind": "hex",
        "orientation": "flat",
        "extent": EXTENT,
        "cell": {"size": 58},
    },
}


async def test_a_map_may_be_a_grid_and_a_plane_may_draw_one(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        for name, system in GRIDS.items():
            made = await gm.post(
                f"/tenants/{t}/maps", json={"name": f"Grid {name}", "system": system}
            )
            assert made.status_code == 201, made.text
            assert made.json()["system"]["kind"] == system["kind"] and made.json()["view"] is None
            assert made.json()["warnings"] == []
        for refused in (
            {**GRIDS["pointy"], "orientation": None},
            {k: v for k, v in GRIDS["pointy"].items() if k != "orientation"},
            {**GRIDS["square"], "cell": {"size": 0}},
            {**GRIDS["square"], "extent": [0, 0, 100000, 100000], "cell": {"size": 10}},
        ):
            assert (
                await gm.post(f"/tenants/{t}/maps", json={"name": "No", "system": refused})
            ).status_code == 422
        # A visual grid over a plane; a grid system draws its own.
        view = {
            "grid": {
                "kind": "hex",
                "orientation": "flat",
                "cell": {"size": 40},
                "sub": {"aperture": 4},
            }
        }
        over = await gm.post(
            f"/tenants/{t}/maps", json={"name": "Over", "system": SYSTEM, "view": view}
        )
        assert over.status_code == 201 and over.json()["view"] == view
        again = await gm.get(f"/tenants/{t}/maps/{over.json()['id']}")
        assert again.json()["view"] == view and again.json()["warnings"] == []
        refused = await gm.post(
            f"/tenants/{t}/maps", json={"name": "Two", "system": GRIDS["square"], "view": view}
        )
        assert refused.status_code == 422
        # The kind API takes the same system.
        plain = await entry(gm, t, "Plain")
        added = await gm.put(
            f"/tenants/{t}/entities/{plain}/kinds/map", json={"system": GRIDS["rect"]}
        )
        assert added.status_code in (200, 201), added.text
    finally:
        await w.clean_up()


async def replace(actor: Any, t: Any, chart: str, system: dict[str, Any], **fields: Any):
    url = f"/tenants/{t}/maps/{chart}"
    current = await actor.get(url)
    return await actor.client.put(
        url,
        headers={**actor.headers, "If-Match": current.headers["etag"]},
        json={"system": system, **fields},
    )


async def test_changing_the_hexes_under_placements_is_refused_and_other_changes_warn(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, "Hexes", is_public=True))["id"]
        # With nothing placed any change is fine, a hex grid included.
        free = await replace(gm, t, chart, GRIDS["pointy"])
        assert free.status_code == 200 and free.json()["warnings"] == []
        one = await entry(gm, t, "One")
        assert (await draw(gm, t, chart, one, pin(10, 10))).status_code == 200
        # Turning the hexes, and leaving or entering hex, would move every place.
        for refused in (GRIDS["flat"], SYSTEM, GRIDS["square"]):
            answer = await replace(gm, t, chart, refused)
            assert answer.status_code == 409, answer.text
        # The cell, the extent and a sub-grid are allowed, with a warning.
        wider = await replace(
            gm, t, chart, {**GRIDS["pointy"], "cell": {"size": 80}, "extent": [0, 0, 2000, 800]}
        )
        assert wider.status_code == 200
        assert any("cell" in line for line in wider.json()["warnings"])
        assert any("sheet" in line for line in wider.json()["warnings"])
        assert (await gm.get(f"/tenants/{t}/maps/{chart}")).json()["warnings"] == []
        # A plane may become a square grid with places on it, and says so.
        flat = (await make_map(gm, t, "Flat", is_public=True))["id"]
        other = await entry(gm, t, "Other")
        assert (await draw(gm, t, flat, other, pin(1, 1))).status_code == 200
        became = await replace(gm, t, flat, GRIDS["square"])
        assert became.status_code == 200 and became.json()["warnings"]
        # Nothing moved.
        assert len(ids(await read(gm, t, flat))) == 1
    finally:
        await w.clean_up()


SPHERE = {"format": "lorenzo.map-system/1", "kind": "sphere", "extent": [-180, -90, 180, 90]}
GLOBE = {"projection": {"kind": "orthographic", "centre": [10, 20]}}


async def test_a_sphere_has_a_projection_and_its_places_are_longitudes_and_latitudes(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        made = await gm.post(
            f"/tenants/{t}/maps",
            json={
                "name": "Aeris",
                "system": {**SPHERE, "radius": {"value": 6371, "unit": "km"}},
                "view": GLOBE,
            },
        )
        assert made.status_code == 201, made.text
        chart = made.json()["id"]
        assert made.json()["system"]["radius"] == {"value": 6371, "unit": "km"}
        assert made.json()["view"] == GLOBE
        for refused in (
            {**SPHERE, "extent": [0, 0, 360, 180]},
            {**SPHERE, "scale": {"per_unit": 1, "unit": "km"}},
            {**SPHERE, "radius": {"value": 0, "unit": "km"}},
        ):
            assert (
                await gm.post(f"/tenants/{t}/maps", json={"name": "No", "system": refused})
            ).status_code == 422
        # A projection is for a sphere, and a sphere draws its own lines.
        for system, view in (
            (SYSTEM, GLOBE),
            (SPHERE, {"projection": {"kind": "mercator", "centre": [0, 0]}}),
            (SPHERE, {"grid": {"kind": "square", "cell": {"size": 5}}}),
        ):
            assert (
                await gm.post(
                    f"/tenants/{t}/maps", json={"name": "No", "system": system, "view": view}
                )
            ).status_code == 422
        # Places are held to their ranges and to the shapes a sphere draws, on every way in.
        town, river = await entry(gm, t, "Town"), await entry(gm, t, "River")
        assert (await draw(gm, t, chart, town, pin(-12.5, 41.25))).status_code == 200
        assert (await draw(gm, t, chart, river, line((-10, 20), (30, 45)))).status_code == 200
        for bad in (
            pin(181, 0),
            pin(0, -90.5),
            line((0, 0), (0, 100)),
            {
                "format": "lorenzo.geometry/1",
                "parts": [{"shape": "circle", "at": [0, 0], "r": 5}],
            },
        ):
            assert (await draw(gm, t, chart, town, bad)).status_code == 422
        refused = await batch(gm, t, chart, put=[{"entry_id": town, "geometry": pin(200, 0)}])
        assert refused.status_code == 422 and "put[0]" in refused.json()["detail"]
        assert len(ids(await read(gm, t, chart))) == 2
        # The same numbers are fine on a plane.
        flat = (await make_map(gm, t, "Flat"))["id"]
        assert (await draw(gm, t, flat, town, pin(900, 700))).status_code == 200
    finally:
        await w.clean_up()


async def test_a_sphere_cannot_be_entered_or_left_under_placements(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, "Globe"))["id"]
        # With nothing placed any change is fine.
        free = await replace(gm, t, chart, SPHERE, view=GLOBE)
        assert free.status_code == 200 and free.json()["view"] == GLOBE
        one = await entry(gm, t, "One")
        assert (await draw(gm, t, chart, one, pin(10, 10))).status_code == 200
        for refused in (SYSTEM, GRIDS["pointy"]):
            answer = await replace(gm, t, chart, refused)
            assert answer.status_code == 409, answer.text
        # The projection and the radius are only drawn or said, and change nothing under places.
        turned = await replace(
            gm,
            t,
            chart,
            {**SPHERE, "radius": {"value": 3389.5, "unit": "km"}},
            view={"projection": {"kind": "mercator"}},
        )
        assert turned.status_code == 200 and turned.json()["view"] == {
            "projection": {"kind": "mercator"}
        }
        assert len(ids(await read(gm, t, chart))) == 1
        # A plane with places cannot become a sphere either.
        flat = (await make_map(gm, t, "Flat"))["id"]
        assert (await draw(gm, t, flat, one, pin(1, 1))).status_code == 200
        assert (await replace(gm, t, flat, SPHERE)).status_code == 409
    finally:
        await w.clean_up()
