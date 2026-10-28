"""Locations, their part-of tree and what a reader sees of it (ADR 0330, ADR 0331)."""

import pathlib
import uuid
from typing import Any

from _admin_db import admin_session_factory
from conftest import delete_tenant, make_tenant
from httpx import AsyncClient
from test_story_sessions import world

from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import LocationPart


async def place(client: Any, tenant: Any, name: str, **fields: Any) -> dict[str, Any]:
    response = await client.post(f"/tenants/{tenant}/locations", json={"name": name, **fields})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


def names(page: Any) -> list[str]:
    assert page.status_code == 200, page.text
    return [row["name"] for row in page.json()["items"]]


async def test_a_location_has_parts_and_a_nearest_visible_ancestor(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        toril = await place(client, tenant, "Toril", slug="toril", is_public=True)
        assert toril["kinds"] == ["location"] and toril["within"] is None
        assert toril["can_manage"] is True and toril["is_public"] is True
        faerun = await place(
            client, tenant, "Faerun", parent_id=toril["id"], level_ordinal="2", is_public=True
        )
        neverwinter = await place(
            client, tenant, "Neverwinter", parent_id=faerun["id"], is_public=True
        )
        assert neverwinter["within"]["name"] == "Faerun"
        tavern = await place(
            client, tenant, "Tavern", parent_id=toril["id"], level_ordinal="1", is_public=True
        )
        base = f"/tenants/{tenant}/locations"
        assert names(await client.get(base + "?root=true")) == ["Toril"]
        # Sibling order: ordinal first, then name.
        assert names(await client.get(f"{base}/{toril['id']}/parts")) == ["Tavern", "Faerun"]
        assert names(await client.get(base + "?q=ver")) == ["Neverwinter", "Tavern"]
        assert names(await client.get(base + "?q=FAE")) == ["Faerun"]
        detail = await client.get(f"{base}/{tavern['id']}")
        assert detail.json()["within"]["id"] == toril["id"]
        assert detail.json()["level_ordinal"] == "1"
        entity = await client.get(f"/tenants/{tenant}/entities/{toril['id']}")
        assert entity.json()["kinds"] == ["location"]
        # A cycle, a self reference and a move under a descendant are one generic 422.
        for child, parent in [
            (toril["id"], neverwinter["id"]),
            (faerun["id"], faerun["id"]),
            (toril["id"], tavern["id"]),
        ]:
            refused = await client.put(f"{base}/{child}/part-of", json={"parent_entity_id": parent})
            assert refused.status_code == 422, refused.text
            assert child not in refused.text and parent not in refused.text
        moved = await client.put(
            f"{base}/{neverwinter['id']}/part-of", json={"parent_entity_id": toril["id"]}
        )
        assert moved.json()["within"]["name"] == "Toril"
        cleared = await client.delete(f"{base}/{neverwinter['id']}/part-of")
        assert cleared.status_code == 204
        assert sorted(names(await client.get(base + "?root=true"))) == ["Neverwinter", "Toril"]
    finally:
        await delete_tenant(tenant)


async def test_the_tree_has_a_depth_cap(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    try:
        parent: str | None = None
        made = 0
        while made < 50:
            location = await place(
                client, tenant, f"Level {made}", parent_id=parent, is_public=True
            )
            parent = location["id"]
            made += 1
        refused = await client.post(
            f"/tenants/{tenant}/locations", json={"name": "Too deep", "parent_id": parent}
        )
        assert refused.status_code == 422, refused.text
    finally:
        await delete_tenant(tenant)


async def test_a_hidden_level_is_skipped_without_a_trace(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        author, player = w.author, w.outsider
        root = await place(author, t, "Realm", is_public=True)
        # The middle level is restricted: a player cannot see it.
        middle = await place(author, t, "Secret hold", parent_id=root["id"])
        leaf = await place(author, t, "Camp", parent_id=middle["id"], is_public=True)
        # The same shape with no hidden level, to compare against.
        plain_root = await place(author, t, "Realm", is_public=True)
        plain_leaf = await place(author, t, "Camp", parent_id=plain_root["id"], is_public=True)

        def strip(page: Any) -> Any:
            body = page.json()
            for row in body["items"]:
                row.pop("id")
            return body

        hidden = await player.get(f"/tenants/{t}/locations/{root['id']}/parts")
        plain = await player.get(f"/tenants/{t}/locations/{plain_root['id']}/parts")
        assert hidden.status_code == 200 and strip(hidden) == strip(plain)
        assert [row["name"] for row in hidden.json()["items"]] == ["Camp"]
        within = await player.get(f"/tenants/{t}/locations/{leaf['id']}")
        plain_within = await player.get(f"/tenants/{t}/locations/{plain_leaf['id']}")
        assert within.json()["within"]["name"] == plain_within.json()["within"]["name"] == "Realm"
        assert "Secret hold" not in within.text and "Secret hold" not in hidden.text
        # The roots a player sees, and the page counts, hold no trace of the hidden level.
        roots = await player.get(f"/tenants/{t}/locations?root=true")
        assert [row["name"] for row in roots.json()["items"]] == ["Realm", "Realm"]
        everything = await player.get(f"/tenants/{t}/locations")
        assert sorted(row["name"] for row in everything.json()["items"]) == [
            "Camp",
            "Camp",
            "Realm",
            "Realm",
        ]
        assert everything.json()["total"] == 4
        # A hidden Location and a missing one answer the same.
        missing = await player.get(f"/tenants/{t}/locations/{uuid.uuid4()}")
        refused = await player.get(f"/tenants/{t}/locations/{middle['id']}")
        assert refused.status_code == missing.status_code == 404

        def shape(response: Any) -> dict[str, Any]:
            body = dict(response.json())
            body.pop("instance", None)
            return body

        assert shape(refused) == shape(missing)
        # The Author and GM sees all of it, and a hidden target of a write is the same 404.
        assert sorted(names(await author.get(f"/tenants/{t}/locations"))) == [
            "Camp",
            "Camp",
            "Realm",
            "Realm",
            "Secret hold",
        ]
        put = await player.put(
            f"/tenants/{t}/locations/{leaf['id']}/part-of",
            json={"parent_entity_id": middle["id"]},
        )
        assert put.status_code == 403
    finally:
        await w.clean_up()


async def test_who_may_write_locations(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        refused = await w.outsider.post(f"/tenants/{t}/locations", json={"name": "Nope"})
        assert refused.status_code == 403
        made = await place(w.orga, t, "By the organizer")
        assert made["is_public"] is False
        reader = await w.outsider.get(f"/tenants/{t}/locations")
        assert reader.json()["items"] == []
        opened = await w.orga.put(
            f"/tenants/{t}/entities/{made['id']}/audience", json={"is_public": True}
        )
        assert opened.status_code in (200, 412, 428), opened.text
    finally:
        await w.clean_up()


async def test_removing_the_marker_and_deleting_make_the_children_roots(
    client: AsyncClient, test_user_id: uuid.UUID
):
    tenant = await make_tenant(test_user_id)
    try:
        top = await place(client, tenant, "Top", is_public=True)
        middle = await place(client, tenant, "Middle", parent_id=top["id"], is_public=True)
        await place(client, tenant, "Bottom", parent_id=middle["id"], is_public=True)
        base = f"/tenants/{tenant}"
        assert (await client.delete(f"{base}/entities/{middle['id']}")).status_code in (200, 204)
        assert sorted(names(await client.get(f"{base}/locations?root=true"))) == ["Bottom", "Top"]
        another = await place(client, tenant, "Another", is_public=True)
        child = await place(client, tenant, "Child", parent_id=another["id"], is_public=True)
        removed = await client.delete(f"{base}/entities/{another['id']}/kinds/location")
        assert removed.status_code == 200, removed.text
        detail = await client.get(f"{base}/locations/{child['id']}")
        assert detail.json()["within"] is None
    finally:
        await delete_tenant(tenant)


async def test_a_location_may_be_any_other_kind(client: AsyncClient, test_user_id: uuid.UUID):
    tenant = await make_tenant(test_user_id)
    try:
        base = f"/tenants/{tenant}"
        item = (
            await client.post(f"{base}/entities", json={"name": "Bag", "kinds": ["item"]})
        ).json()
        added = await client.put(f"{base}/entities/{item['id']}/kinds/location")
        assert added.status_code == 201 and sorted(added.json()["kinds"]) == ["item", "location"]
        # Nothing about an existing entry changes for those who read it.
        listed = await client.get(f"{base}/locations")
        assert names(listed) == ["Bag"]
        # The other direction: a Location becomes a being, and a fact.
        castle = await place(client, tenant, "Castle", is_public=True)
        being = await client.put(f"{base}/entities/{castle['id']}/kinds/being")
        assert being.status_code == 201 and sorted(being.json()["kinds"]) == ["being", "location"]
        fact = await place(client, tenant, "Lore", is_public=True)
        fact_added = await client.put(f"{base}/entities/{fact['id']}/kinds/fact")
        assert fact_added.status_code == 201, fact_added.text
        # A calendar, a clock and a scene may also be a Location.
        for route, body in [
            (
                "calendars",
                {
                    "name": "Reckoning",
                    "definition": {"segments": [{"key": "m", "name": "M", "days": 30}]},
                },
            ),
            ("clocks", {"name": "Home clock"}),
            ("scenes", {"name": "A scene"}),
        ]:
            made = await client.post(f"{base}/{route}", json=body)
            assert made.status_code == 201, made.text
            identity = made.json().get("entity_id") or made.json()["id"]
            joined = await client.put(f"{base}/entities/{identity}/kinds/location")
            assert joined.status_code == 201, joined.text
            assert "location" in joined.json()["kinds"]
    finally:
        await delete_tenant(tenant)


async def test_the_part_of_tree_never_feeds_gm_reach(raw_client, fake_jwks_server):
    """ADR 0046 reach is the same with part-of rows and without (RFC 0048, G3): the Location
    entries are authored content in a GM's reach, the tree is not a route to anything."""
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        top = await place(w.author, t, "Realm", is_public=True)
        inner = await place(w.author, t, "Hold", is_public=True)
        async with admin_session_factory() as session:
            before = (
                await resolve_information_visibility(session, user_id=w.author.user_id, tenant_id=t)
            ).gm_reachable_entity_ids
        moved = await w.author.put(
            f"/tenants/{t}/locations/{inner['id']}/part-of",
            json={"parent_entity_id": top["id"]},
        )
        assert moved.status_code == 200, moved.text
        async with admin_session_factory() as session:
            after = (
                await resolve_information_visibility(session, user_id=w.author.user_id, tenant_id=t)
            ).gm_reachable_entity_ids
            rows = (await session.execute(LocationPart.__table__.select())).all()
        assert rows and before == after
    finally:
        await w.clean_up()


def test_no_reach_code_reads_the_part_of_table():
    source = pathlib.Path(__file__).parents[1] / "src" / "lorenzo_api"
    for module in ("entity_access.py", "information_visibility.py", "campaign_access.py"):
        text = (source / module).read_text()
        assert "LocationPart" not in text and "location_part" not in text, module


async def test_a_manager_opens_a_location_to_the_library(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        made = await place(w.author, t, "Harbour")
        base = f"/tenants/{t}/entities/{made['id']}/audience"
        assert (await w.outsider.get(f"/tenants/{t}/locations/{made['id']}")).status_code == 404
        current = await w.author.get(base)
        assert current.status_code == 200, current.text
        saved = await w.author.client.put(
            base,
            headers={**w.author.headers, "If-Match": current.headers["etag"]},
            json={**current.json(), "is_public": True},
        )
        assert saved.status_code == 200, saved.text
        read = await w.author.get(f"/tenants/{t}/locations/{made['id']}")
        assert read.json()["is_public"] is True
        assert (await w.outsider.get(f"/tenants/{t}/locations/{made['id']}")).status_code == 200
    finally:
        await w.clean_up()
