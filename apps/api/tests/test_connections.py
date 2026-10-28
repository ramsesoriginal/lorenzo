"""Connections and the links they give a Map (ADR 0363, 0364)."""

import pathlib
import uuid
from typing import Any

from test_locations import place
from test_maps import draw, make_map, pin
from test_placement import entry
from test_story_sessions import world

from lorenzo_api import connections as limits


async def connect(actor: Any, t: Any, end_a: str, end_b: str, name: str = "Road", **fields: Any):
    return await actor.post(
        f"/tenants/{t}/connections",
        json={"name": name, "end_a": end_a, "end_b": end_b, **fields},
    )


async def made(actor: Any, t: Any, end_a: str, end_b: str, name: str = "Road", **fields: Any):
    response = await connect(actor, t, end_a, end_b, name, **fields)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def listing(actor: Any, t: Any, **params: Any) -> list[dict[str, Any]]:
    response = await actor.get(f"/tenants/{t}/connections", params=params)
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


async def links(actor: Any, t: Any, chart: str) -> dict[str, Any]:
    response = await actor.get(f"/tenants/{t}/maps/{chart}/links")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_a_connection_is_made_read_listed_and_changed(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Hollowmere", is_public=True)
        b = await place(gm, t, "Dunmere", is_public=True)
        c = await place(gm, t, "Brindle", is_public=True)
        road = await entry(gm, t, "Road kind")
        one = await made(
            gm, t, a["id"], b["id"], "King's Road", is_public=True, prototypes=[road], slug="kings"
        )
        assert one["kinds"] == ["connection"] and one["slug"] == "kings"
        assert one["end_a"]["name"] == "Hollowmere" and one["end_b"]["id"] == b["id"]
        assert one["one_way"] is False and one["can_manage"] is True and one["is_public"] is True
        got = await gm.get(f"/tenants/{t}/connections/{one['id']}")
        assert got.status_code == 200 and got.json() == one and got.headers["etag"]
        # Prototypes are the kind of connection it is.
        detail = (await gm.get(f"/tenants/{t}/entities/{one['id']}")).json()
        assert [p["name"] for p in detail["prototypes"]] == ["Road kind"]
        # A reader sees it with both ends, and no flag of who may manage.
        seen = (await player.get(f"/tenants/{t}/connections/{one['id']}")).json()
        assert seen["can_manage"] is False and seen["is_public"] is None
        # Lists: by name, by an end, by a name part.
        two = await made(gm, t, b["id"], c["id"], "Ferry", is_public=True, one_way=True)
        assert two["one_way"] is True
        assert [x["name"] for x in await listing(gm, t)] == ["Ferry", "King's Road"]
        assert [x["name"] for x in await listing(gm, t, end=a["id"])] == ["King's Road"]
        assert [x["name"] for x in await listing(gm, t, end=b["id"])] == ["Ferry", "King's Road"]
        assert [x["name"] for x in await listing(gm, t, q="fer")] == ["Ferry"]
        # The ends are replaced under If-Match.
        url = f"/tenants/{t}/connections/{one['id']}"
        current = await gm.get(url)
        replaced = await gm.client.put(
            url,
            headers={**gm.headers, "If-Match": current.headers["etag"]},
            json={"end_a": c["id"], "end_b": a["id"], "one_way": True},
        )
        assert replaced.status_code == 200, replaced.text
        assert replaced.json()["end_a"]["name"] == "Brindle" and replaced.json()["one_way"] is True
        assert replaced.headers["etag"] != current.headers["etag"]
        stale = await gm.client.put(
            url,
            headers={**gm.headers, "If-Match": current.headers["etag"]},
            json={"end_a": a["id"], "end_b": b["id"]},
        )
        assert stale.status_code == 412
        assert (
            await gm.client.put(url, headers=gm.headers, json={"end_a": a["id"], "end_b": b["id"]})
        ).status_code == 428
    finally:
        await w.clean_up()


async def test_what_makes_no_connection_is_refused(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Hollowmere", is_public=True)
        b = await place(gm, t, "Dunmere", is_public=True)
        assert (await connect(gm, t, a["id"], a["id"])).status_code == 422
        assert (await connect(gm, t, a["id"], str(uuid.uuid4()))).status_code == 404
        assert (
            await connect(gm, t, a["id"], b["id"], prototypes=[str(uuid.uuid4())])
        ).status_code == 404
        assert (await connect(gm, t, a["id"], b["id"], one_way="sometimes")).status_code == 422
        # Only those who write Locations make one.
        assert (await connect(player, t, a["id"], b["id"])).status_code == 403
        # An end the writer cannot see is the generic 404.
        secret = await place(gm, t, "Hidden keep")
        assert (await connect(player, t, a["id"], secret["id"])).status_code in (403, 404)
        # A connection has the kind alone.
        one = await made(gm, t, a["id"], b["id"], is_public=True)
        base = f"/tenants/{t}/entities/{one['id']}/kinds"
        assert (await gm.put(f"{base}/item")).status_code == 422
        assert (await gm.put(f"{base}/location")).status_code == 422
        thing = await entry(gm, t, "Thing")
        assert (await gm.put(f"/tenants/{t}/entities/{thing}/kinds/connection")).status_code == 422
        refused = await gm.post(
            f"/tenants/{t}/entities", json={"name": "Wire", "kinds": ["connection"]}
        )
        assert refused.status_code == 422
        # The kind can be taken away once the audience is public, and the entry stays.
        gone = await gm.delete(f"{base}/connection")
        assert gone.status_code == 200 and gone.json()["kinds"] == []
        assert (await gm.get(f"/tenants/{t}/connections/{one['id']}")).status_code == 404
        assert (await gm.get(f"/tenants/{t}/entities/{one['id']}")).status_code == 200
        private = await made(gm, t, a["id"], b["id"], "Secret road")
        again = await gm.delete(f"/tenants/{t}/entities/{private['id']}/kinds/connection")
        assert again.status_code == 422
    finally:
        await w.clean_up()


async def test_a_connection_is_read_only_with_both_ends_and_its_own_audience(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        open_a = await place(gm, t, "Open gate", is_public=True)
        open_b = await place(gm, t, "Open road", is_public=True)
        closed = await place(gm, t, "Closed vault")
        showing = await made(gm, t, open_a["id"], open_b["id"], "Shown", is_public=True)
        hidden_end = await made(gm, t, open_a["id"], closed["id"], "Hidden end", is_public=True)
        hidden_self = await made(gm, t, open_a["id"], open_b["id"], "Hidden itself")
        assert [x["name"] for x in await listing(gm, t)] == ["Hidden end", "Hidden itself", "Shown"]
        assert [x["name"] for x in await listing(player, t)] == ["Shown"]
        page = (await player.get(f"/tenants/{t}/connections")).json()
        assert page["total"] == 1
        # A hidden end, a hidden connection and a missing one answer alike.
        answers = {
            (await player.get(f"/tenants/{t}/connections/{identity}")).status_code
            for identity in (hidden_end["id"], hidden_self["id"], str(uuid.uuid4()))
        }
        bodies = {
            (await player.get(f"/tenants/{t}/connections/{identity}")).json()["detail"]
            for identity in (hidden_end["id"], hidden_self["id"], str(uuid.uuid4()))
        }
        assert answers == {404} and len(bodies) == 1
        # Opening the end shows the connection.
        base = f"/tenants/{t}/entities/{closed['id']}/audience"
        current = await gm.get(base)
        opened = await gm.client.put(
            base,
            headers={**gm.headers, "If-Match": current.headers["etag"]},
            json={**current.json(), "is_public": True},
        )
        assert opened.status_code == 200, opened.text
        assert {x["name"] for x in await listing(player, t)} == {"Shown", "Hidden end"}
        assert showing["id"]
    finally:
        await w.clean_up()


async def test_a_hub_is_a_connection_to_each_spoke_or_nothing(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        shaft = await place(gm, t, "Stair shaft", is_public=True)
        floors = [await place(gm, t, f"Floor {n}", is_public=True) for n in range(3)]
        stairs = await entry(gm, t, "Stairs kind")
        hub = await gm.post(
            f"/tenants/{t}/connections/hub",
            json={
                "hub": shaft["id"],
                "spokes": [
                    {"end": floors[0]["id"]},
                    {"end": floors[1]["id"], "direction": "to_hub"},
                    {"end": floors[2]["id"], "direction": "from_hub", "name": "Chute"},
                ],
                "prototypes": [stairs],
                "is_public": True,
            },
        )
        assert hub.status_code == 201, hub.text
        made_ones = hub.json()
        assert [x["name"] for x in made_ones] == [
            "Stair shaft - Floor 0",
            "Stair shaft - Floor 1",
            "Chute",
        ]
        first, second, third = made_ones
        assert first["one_way"] is False
        assert (second["end_a"]["name"], second["end_b"]["name"], second["one_way"]) == (
            "Floor 1",
            "Stair shaft",
            True,
        )
        assert (third["end_a"]["name"], third["end_b"]["name"], third["one_way"]) == (
            "Stair shaft",
            "Floor 2",
            True,
        )
        assert len(await listing(gm, t, end=shaft["id"])) == 3
        # One bad piece refuses the whole request.
        before = len(await listing(gm, t))
        other = await place(gm, t, "Cellar", is_public=True)
        for bad in (
            [{"end": other["id"]}, {"end": other["id"]}],
            [{"end": shaft["id"]}],
            [{"end": other["id"]}, {"end": str(uuid.uuid4())}],
            [],
            [{"end": other["id"], "direction": "sideways"}],
        ):
            refused = await gm.post(
                f"/tenants/{t}/connections/hub", json={"hub": shaft["id"], "spokes": bad}
            )
            assert refused.status_code in (404, 422), refused.text
        assert len(await listing(gm, t)) == before
        too_many = [{"end": other["id"]}] * (limits.MAX_HUB_SPOKES + 1)
        assert (
            await gm.post(
                f"/tenants/{t}/connections/hub", json={"hub": shaft["id"], "spokes": too_many}
            )
        ).status_code == 422
    finally:
        await w.clean_up()


async def test_a_library_holds_a_limited_number_of_connections(
    raw_client, fake_jwks_server, monkeypatch
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        a = await place(gm, t, "A", is_public=True)
        b = await place(gm, t, "B", is_public=True)
        c = await place(gm, t, "C", is_public=True)
        monkeypatch.setattr(limits, "MAX_CONNECTIONS_PER_LIBRARY", 2)
        await made(gm, t, a["id"], b["id"], "One")
        await made(gm, t, b["id"], c["id"], "Two")
        assert (await connect(gm, t, a["id"], c["id"], "Three")).status_code == 422
        over = await gm.post(
            f"/tenants/{t}/connections/hub", json={"hub": a["id"], "spokes": [{"end": b["id"]}]}
        )
        assert over.status_code == 422
        assert len(await listing(gm, t)) == 2
    finally:
        await w.clean_up()


async def test_deleting_an_end_or_the_entry_leaves_the_right_thing(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        a = await place(gm, t, "Hollowmere", is_public=True)
        b = await place(gm, t, "Dunmere", is_public=True)
        c = await place(gm, t, "Brindle", is_public=True)
        one = await made(gm, t, a["id"], b["id"], "King's Road", is_public=True)
        two = await made(gm, t, b["id"], c["id"], "Ferry", is_public=True)
        # Deleting an end removes the connection and leaves its entry, a plain entry.
        assert (await gm.delete(f"/tenants/{t}/entities/{a['id']}")).status_code == 204
        assert [x["name"] for x in await listing(gm, t)] == ["Ferry"]
        left = await gm.get(f"/tenants/{t}/entities/{one['id']}")
        assert left.status_code == 200 and left.json()["kinds"] == []
        # Deleting the entry removes the connection and no end.
        assert (await gm.delete(f"/tenants/{t}/entities/{two['id']}")).status_code == 204
        assert await listing(gm, t) == []
        assert (await gm.get(f"/tenants/{t}/entities/{b['id']}")).status_code == 200
    finally:
        await w.clean_up()


async def test_a_map_says_where_its_places_lead(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        west = (await make_map(gm, t, "Western Map", is_public=True))["id"]
        east = (await make_map(gm, t, "Eastern Map", is_public=True))["id"]
        vault = (await make_map(gm, t, "Vault Map"))["id"]
        gate = await place(gm, t, "Gate", is_public=True)
        stair = await place(gm, t, "Stair", is_public=True)
        far = await place(gm, t, "Far bank", is_public=True)
        deep = await place(gm, t, "Deep room", is_public=True)
        for chart, who, at in (
            (west, gate["id"], pin(1, 1)),
            (west, stair["id"], pin(5, 5)),
            (east, far["id"], pin(2, 2)),
            (vault, far["id"], pin(3, 3)),
            (east, deep["id"], pin(8, 8)),
        ):
            assert (await draw(gm, t, chart, who, at)).status_code == 200
        bridge = await made(gm, t, gate["id"], far["id"], "Bridge", is_public=True)
        portal = await made(gm, t, far["id"], stair["id"], "Portal", is_public=True, one_way=True)
        wall = await made(gm, t, gate["id"], stair["id"], "Corridor", is_public=True)
        await made(gm, t, deep["id"], far["id"], "Elsewhere", is_public=True)
        found = await links(gm, t, west)
        rows = [
            (r["connection"]["name"], r["here"]["name"], r["other"]["name"], r["direction"])
            for r in found["items"]
        ]
        assert rows == [
            ("Bridge", "Gate", "Far bank", "both"),
            ("Corridor", "Gate", "Stair", "both"),
            ("Portal", "Stair", "Far bank", "in"),
            ("Corridor", "Stair", "Gate", "both"),
        ], rows
        assert found["truncated"] is False
        by_connection = {r["connection"]["name"]: r for r in found["items"]}
        # The Far bank is placed on the Eastern Map, and on one that is hidden from a player.
        names = [m["name"] for m in by_connection["Bridge"]["other_maps"]]
        assert names == ["Eastern Map", "Vault Map"]
        assert [m["name"] for m in (await links(player, t, west))["items"][0]["other_maps"]] == [
            "Eastern Map"
        ]
        # From the Eastern Map the portal leaves the Far bank.
        east_rows = {
            (r["connection"]["name"], r["direction"]) for r in (await links(gm, t, east))["items"]
        }
        assert ("Portal", "out") in east_rows and ("Bridge", "both") in east_rows
        # A hidden Map has no links for a player, and a missing one answers alike.
        assert (await player.get(f"/tenants/{t}/maps/{vault}/links")).status_code == 404
        assert (await player.get(f"/tenants/{t}/maps/{uuid.uuid4()}/links")).status_code == 404
        assert bridge["id"] and portal["id"] and wall["id"]
    finally:
        await w.clean_up()


async def test_links_follow_the_ends_not_the_drawing(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        chart = (await make_map(gm, t, "Coast", is_public=True))["id"]
        a = await place(gm, t, "Hollowmere", is_public=True)
        b = await place(gm, t, "Dunmere", is_public=True)
        secret = await place(gm, t, "Hidden keep")
        road = await made(gm, t, a["id"], b["id"], "Road", is_public=True)
        hidden_end = await made(gm, t, a["id"], secret["id"], "To the keep", is_public=True)
        assert (await draw(gm, t, chart, a["id"], pin(1, 1))).status_code == 200
        before = await links(gm, t, chart)
        # Drawing the road itself changes nothing about the links.
        line = {
            "format": "lorenzo.geometry/1",
            "parts": [{"shape": "polyline", "pts": [[1, 1], [9, 9]]}],
        }
        assert (await draw(gm, t, chart, road["id"], line)).status_code == 200
        assert (await draw(gm, t, chart, road["id"], pin(7, 7))).status_code == 200
        after = await links(gm, t, chart)
        assert after["items"] == before["items"]
        # The hidden end leaves no row and no trace for a player; a manager sees both.
        assert [r["connection"]["name"] for r in after["items"]] == ["Road", "To the keep"]
        assert [r["connection"]["name"] for r in (await links(player, t, chart))["items"]] == [
            "Road"
        ]
        assert hidden_end["id"]
    finally:
        await w.clean_up()


async def test_the_links_are_capped_and_say_so(raw_client, fake_jwks_server, monkeypatch):
    import lorenzo_api.routers.connections as router

    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chart = (await make_map(gm, t, "Coast", is_public=True))["id"]
        hub = await place(gm, t, "Hub", is_public=True)
        assert (await draw(gm, t, chart, hub["id"], pin(1, 1))).status_code == 200
        spokes = [await place(gm, t, f"Spoke {n}", is_public=True) for n in range(3)]
        for spoke in spokes:
            await made(gm, t, hub["id"], spoke["id"], f"To {spoke['name']}", is_public=True)
        monkeypatch.setattr(router, "MAX_LINK_ROWS", 2)
        found = await links(gm, t, chart)
        assert len(found["items"]) == 2 and found["truncated"] is True
    finally:
        await w.clean_up()


def test_no_reach_code_reads_a_connections_ends():
    source = pathlib.Path(__file__).parents[1] / "src" / "lorenzo_api"
    for module in ("entity_access.py", "information_visibility.py", "campaign_access.py"):
        text = (source / module).read_text()
        assert "end_a" not in text and "end_b" not in text, module


async def test_a_copy_carries_a_connection_only_with_both_ends() -> None:
    from datetime import UTC, datetime

    from _admin_db import admin_session_factory
    from _repository_fixtures import seed_every_content_table
    from sqlalchemy import text

    from lorenzo_api.models import RepositorySubscription, Tenant, TenantKind
    from lorenzo_api.repository_copying import plan_copy

    async with admin_session_factory() as session:
        repository = Tenant(name="Faerûn roads", kind=TenantKind.REPOSITORY)
        library = Tenant(name="My Table roads")
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
        (joined,) = plan.rows["connection"]
        local = {row["id"]: row["name"] for row in plan.rows["entity"]}
        assert local[joined["entity_id"]] == "Fixture road"
        assert {local[joined["end_a"]], local[joined["end_b"]]} == {
            "Fixture place",
            "Fixture room",
        }
        assert joined["one_way"] is True and joined["tenant_id"] == library_id
    finally:
        from lorenzo_api.models import Tenant as T

        async with admin_session_factory() as session:
            for tenant_id in (library_id, repository_id):
                await session.delete(await session.get_one(T, tenant_id))
            await session.commit()
