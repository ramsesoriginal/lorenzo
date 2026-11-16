"""Relationships: entries that tie two entries (ADR 0399)."""

import pathlib
import re
import uuid
from typing import Any

from test_distance_read import definition, give
from test_locations import place
from test_placement import entry
from test_story_sessions import world

from lorenzo_api import relationships as limits


async def tie(actor: Any, t: Any, end_a: str, end_b: str, name: str = "Ally of", **fields: Any):
    return await actor.post(
        f"/tenants/{t}/relationships",
        json={"name": name, "end_a": end_a, "end_b": end_b, **fields},
    )


async def made(actor: Any, t: Any, end_a: str, end_b: str, name: str = "Ally of", **fields: Any):
    response = await tie(actor, t, end_a, end_b, name, **fields)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def listing(actor: Any, t: Any, **params: Any) -> list[dict[str, Any]]:
    response = await actor.get(f"/tenants/{t}/relationships", params=params)
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


async def everywhere(actor: Any, t: Any) -> dict[str, set[str]]:
    """The names an actor reads relationships under, by every read that can show one."""
    by_kind = await actor.get(f"/tenants/{t}/entities", params={"kind": "relationship"})
    assert by_kind.status_code == 200, by_kind.text
    by_name = await actor.get(f"/tenants/{t}/entities", params={"q": ""})
    assert by_name.status_code == 200, by_name.text
    return {
        "own": {row["name"] for row in await listing(actor, t)},
        "entities by kind": {row["name"] for row in by_kind.json()["items"]},
        "entities by name": {
            row["name"] for row in by_name.json()["items"] if "relationship" in row["kinds"]
        },
    }


async def test_a_relationship_is_made_read_listed_and_changed(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        mara = await place(gm, t, "Mara", is_public=True)
        wren = await place(gm, t, "Wren", is_public=True)
        dren = await place(gm, t, "Dren", is_public=True)
        parent_of = await entry(gm, t, "Parent of")
        one = await made(
            gm,
            t,
            mara["id"],
            wren["id"],
            "Mara is the parent of Wren",
            is_public=True,
            prototypes=[parent_of],
            slug="mara-wren",
            one_way=True,
        )
        assert one["kinds"] == ["relationship"] and one["slug"] == "mara-wren"
        assert one["end_a"]["name"] == "Mara" and one["end_b"]["id"] == wren["id"]
        assert one["one_way"] is True and one["can_manage"] is True and one["is_public"] is True
        got = await gm.get(f"/tenants/{t}/relationships/{one['id']}")
        assert got.status_code == 200 and got.json() == one and got.headers["etag"]
        # Its type is a prototype.
        detail = (await gm.get(f"/tenants/{t}/entities/{one['id']}")).json()
        assert [p["name"] for p in detail["prototypes"]] == ["Parent of"]
        assert detail["kinds"] == ["relationship"]
        # A reader sees it with both ends, and no flag of who may manage.
        seen = (await player.get(f"/tenants/{t}/relationships/{one['id']}")).json()
        assert seen["can_manage"] is False and seen["is_public"] is None
        # Lists: by name, by an end, by the ends in sets, by a name part and by type.
        two = await made(gm, t, wren["id"], dren["id"], "Rival of", is_public=True)
        assert two["one_way"] is False
        names = [x["name"] for x in await listing(gm, t)]
        assert names == ["Mara is the parent of Wren", "Rival of"]
        assert [x["name"] for x in await listing(gm, t, end=mara["id"])] == [one["name"]]
        assert len(await listing(gm, t, end=wren["id"])) == 2
        assert [x["name"] for x in await listing(gm, t, q="riv")] == ["Rival of"]
        assert [x["name"] for x in await listing(gm, t, end_a_in=[wren["id"], dren["id"]])] == [
            "Rival of"
        ]
        assert [x["name"] for x in await listing(gm, t, end_b_in=[wren["id"]])] == [one["name"]]
        assert [x["name"] for x in await listing(gm, t, type=parent_of)] == [one["name"]]
        # The ends are replaced under If-Match.
        url = f"/tenants/{t}/relationships/{one['id']}"
        current = await gm.get(url)
        replaced = await gm.client.put(
            url,
            headers={**gm.headers, "If-Match": current.headers["etag"]},
            json={"end_a": dren["id"], "end_b": mara["id"], "one_way": False},
        )
        assert replaced.status_code == 200, replaced.text
        assert replaced.json()["end_a"]["name"] == "Dren" and replaced.json()["one_way"] is False
        assert replaced.headers["etag"] != current.headers["etag"]
        stale = await gm.client.put(
            url,
            headers={**gm.headers, "If-Match": current.headers["etag"]},
            json={"end_a": mara["id"], "end_b": wren["id"]},
        )
        assert stale.status_code == 412
        bare = await gm.client.put(
            url, headers=gm.headers, json={"end_a": mara["id"], "end_b": wren["id"]}
        )
        assert bare.status_code == 428
    finally:
        await w.clean_up()


async def test_what_makes_no_relationship_is_refused(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        assert (await tie(gm, t, a["id"], a["id"])).status_code == 422
        assert (await tie(gm, t, a["id"], str(uuid.uuid4()))).status_code == 404
        assert (
            await tie(gm, t, a["id"], b["id"], prototypes=[str(uuid.uuid4())])
        ).status_code == 404
        assert (await tie(gm, t, a["id"], b["id"], one_way="sometimes")).status_code == 422
        # Only those who write Locations make one.
        assert (await tie(player, t, a["id"], b["id"])).status_code == 403
        # An end the writer cannot see is the generic 404.
        secret = await place(gm, t, "Hidden keep")
        assert (await tie(player, t, a["id"], secret["id"])).status_code in (403, 404)
        # An end is never itself a relationship.
        one = await made(gm, t, a["id"], b["id"], is_public=True)
        assert (await tie(gm, t, one["id"], b["id"])).status_code == 422
        assert (await tie(gm, t, a["id"], one["id"])).status_code == 422
        # A relationship has the kind alone.
        base = f"/tenants/{t}/entities/{one['id']}/kinds"
        assert (await gm.put(f"{base}/item")).status_code == 422
        assert (await gm.put(f"{base}/location")).status_code == 422
        assert (await gm.put(f"{base}/connection")).status_code == 422
        thing = await entry(gm, t, "Thing")
        assert (
            await gm.put(f"/tenants/{t}/entities/{thing}/kinds/relationship")
        ).status_code == 422
        refused = await gm.post(
            f"/tenants/{t}/entities", json={"name": "Wire", "kinds": ["relationship"]}
        )
        assert refused.status_code == 422
        # The kind can be taken away once the audience is public, and the entry stays.
        gone = await gm.delete(f"{base}/relationship")
        assert gone.status_code == 200 and gone.json()["kinds"] == []
        assert (await gm.get(f"/tenants/{t}/relationships/{one['id']}")).status_code == 404
        assert (await gm.get(f"/tenants/{t}/entities/{one['id']}")).status_code == 200
        private = await made(gm, t, a["id"], b["id"], "Secret bond")
        again = await gm.delete(f"/tenants/{t}/entities/{private['id']}/kinds/relationship")
        assert again.status_code == 422
    finally:
        await w.clean_up()


async def test_a_relationship_is_read_only_with_both_ends_by_every_read(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        open_a = await place(gm, t, "Open gate", is_public=True)
        open_b = await place(gm, t, "Open road", is_public=True)
        closed = await place(gm, t, "Closed vault")
        await made(gm, t, open_a["id"], open_b["id"], "Shown", is_public=True)
        hidden_end = await made(gm, t, open_a["id"], closed["id"], "Hidden end", is_public=True)
        hidden_self = await made(gm, t, open_a["id"], open_b["id"], "Hidden itself")
        everything = {"Hidden end", "Hidden itself", "Shown"}
        # The GM sees all three, by every read; the player only the one with both ends and its own
        # audience, by every read, the generic ones too (the rule is in the shared clause).
        for read in (await everywhere(gm, t)).values():
            assert read == everything
        for read in (await everywhere(player, t)).values():
            assert read == {"Shown"}
        page = (await player.get(f"/tenants/{t}/relationships")).json()
        assert page["total"] == 1
        # A hidden end, a hidden relationship and a missing one answer alike, whichever way they are
        # read: its own route or the entry route.
        for route in ("relationships", "entities"):
            seen = [
                await player.get(f"/tenants/{t}/{route}/{identity}")
                for identity in (hidden_end["id"], hidden_self["id"], str(uuid.uuid4()))
            ]
            assert {r.status_code for r in seen} == {404}, route
            # (the entry route names the id it was asked for, so the id is taken out)
            said = {re.sub(r"[0-9a-f-]{36}", "ID", r.json()["detail"]) for r in seen}
            assert len(said) == 1, route
        # Opening the end shows the relationship, by every read.
        base = f"/tenants/{t}/entities/{closed['id']}/audience"
        current = await gm.get(base)
        opened = await gm.client.put(
            base,
            headers={**gm.headers, "If-Match": current.headers["etag"]},
            json={**current.json(), "is_public": True},
        )
        assert opened.status_code == 200, opened.text
        for read in (await everywhere(player, t)).values():
            assert read == {"Shown", "Hidden end"}
        assert (await player.get(f"/tenants/{t}/entities/{hidden_end['id']}")).status_code == 200
    finally:
        await w.clean_up()


async def test_the_bulk_stat_read_applies_the_both_ends_rule(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        closed = await place(gm, t, "Closed vault")
        honor = await definition(gm, t, "honor", "int")
        shown = await made(gm, t, a["id"], b["id"], "Shown", is_public=True)
        hidden = await made(gm, t, a["id"], closed["id"], "Hidden end", is_public=True)
        await give(gm, t, shown["id"], honor, 3)
        await give(gm, t, hidden["id"], honor, 9)
        read = await player.get(
            f"/tenants/{t}/entities/effective-stats",
            params={"kind": "relationship", "stat_definition_id": honor},
        )
        assert read.status_code == 200, read.text
        assert [row["name"] for row in read.json()["items"]] == ["Shown"]
        assert read.json()["total"] == 1
    finally:
        await w.clean_up()


async def test_a_relationship_is_restricted_by_default_and_a_pair_may_have_several(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        friend = await entry(gm, t, "Friend of")
        quiet = await made(gm, t, a["id"], b["id"], "Friend, in public", prototypes=[friend])
        assert quiet["is_public"] is False
        assert await listing(player, t) == []
        # Nothing refuses a second relationship of one type between one pair: a refusal would tell
        # a writer that a hidden one exists.
        again = await made(
            gm, t, a["id"], b["id"], "Friend, in secret", prototypes=[friend], is_public=True
        )
        assert [x["name"] for x in await listing(player, t)] == [again["name"]]
        assert len(await listing(gm, t)) == 2
    finally:
        await w.clean_up()


async def test_a_library_holds_a_limited_number_of_relationships(
    raw_client, fake_jwks_server, monkeypatch
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        a = await place(gm, t, "A", is_public=True)
        b = await place(gm, t, "B", is_public=True)
        c = await place(gm, t, "C", is_public=True)
        monkeypatch.setattr(limits, "MAX_RELATIONSHIPS_PER_LIBRARY", 2)
        await made(gm, t, a["id"], b["id"], "One")
        await made(gm, t, b["id"], c["id"], "Two")
        assert (await tie(gm, t, a["id"], c["id"], "Three")).status_code == 422
        assert len(await listing(gm, t)) == 2
    finally:
        await w.clean_up()


async def test_deleting_an_end_or_the_entry_leaves_the_right_thing(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        a = await place(gm, t, "Mara", is_public=True)
        b = await place(gm, t, "Wren", is_public=True)
        c = await place(gm, t, "Dren", is_public=True)
        one = await made(gm, t, a["id"], b["id"], "Ally of", is_public=True)
        two = await made(gm, t, b["id"], c["id"], "Rival of", is_public=True)
        # Deleting an end removes the relationship and leaves its entry, a plain entry.
        assert (await gm.delete(f"/tenants/{t}/entities/{a['id']}")).status_code == 204
        assert [x["name"] for x in await listing(gm, t)] == ["Rival of"]
        left = await gm.get(f"/tenants/{t}/entities/{one['id']}")
        assert left.status_code == 200 and left.json()["kinds"] == []
        # Deleting the entry removes the relationship and no end.
        assert (await gm.delete(f"/tenants/{t}/entities/{two['id']}")).status_code == 204
        assert await listing(gm, t) == []
        assert (await gm.get(f"/tenants/{t}/entities/{b['id']}")).status_code == 200
    finally:
        await w.clean_up()


def test_no_reach_code_reads_a_relationships_ends():
    source = pathlib.Path(__file__).parents[1] / "src" / "lorenzo_api"
    for module in ("entity_access.py", "information_visibility.py", "campaign_access.py"):
        text = (source / module).read_text()
        assert "end_a" not in text and "end_b" not in text, module


def test_maps_read_no_relationship():
    """A Map, its links and the router never read a relationship (RFC 0049 S3)."""
    source = pathlib.Path(__file__).parents[1] / "src" / "lorenzo_api"
    modules = [
        *source.glob("map*.py"),
        *source.glob("routers/map*.py"),
        source / "routing.py",
        source / "routers" / "distance.py",
        source / "routers" / "connections.py",
        source / "connections.py",
    ]
    assert modules
    for module in modules:
        assert not re.search(r"\bRelationship\b", module.read_text()), module.name


async def test_a_copy_carries_a_relationship_only_with_both_ends() -> None:
    from datetime import UTC, datetime

    from _admin_db import admin_session_factory
    from _repository_fixtures import seed_every_content_table
    from sqlalchemy import text

    from lorenzo_api.models import RepositorySubscription, Tenant, TenantKind
    from lorenzo_api.repository_copying import plan_copy

    async with admin_session_factory() as session:
        repository = Tenant(name="Faerûn bonds", kind=TenantKind.REPOSITORY)
        library = Tenant(name="My Table bonds")
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
        local = {row["id"]: row["name"] for row in plan.rows["entity"]}
        by_name = {local[row["entity_id"]]: row for row in plan.rows["relationship"]}
        assert set(by_name) == {"Fixture bond", "Fixture second bond"}
        tied = by_name["Fixture bond"]
        # The chain is copied with its relationships, renumbered from 1 (ADR 0402).
        (step,) = plan.rows["relationship_through"]
        assert local[step["relationship_entity_id"]] == "Fixture bond"
        assert local[step["via_entity_id"]] == "Fixture second bond" and step["step"] == 1
        assert {local[tied["end_a"]], local[tied["end_b"]]} == {"Fixture place", "Fixture room"}
        assert tied["one_way"] is None and tied["tenant_id"] == library_id
    finally:
        from lorenzo_api.models import Tenant as T

        async with admin_session_factory() as session:
            for tenant_id in (library_id, repository_id):
                await session.delete(await session.get_one(T, tenant_id))
            await session.commit()
