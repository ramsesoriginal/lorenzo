"""Frames and axes (ADR 0369, 0370): who is a frame, who is on one, and what the GM's address and
reads say of them."""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import delete, select, text
from test_locations import place
from test_placement import contain, entry, put_at
from test_story_sessions import world

from lorenzo_api import frames as frames_module
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Entity, EntityFrame, Frame


async def designate(actor: Any, t: Any, who: str, axis: str = "plane"):
    return await actor.put(f"/tenants/{t}/entities/{who}/frame-axes/{axis}")


async def put_on(actor: Any, t: Any, who: str, frame: str, axis: str = "plane"):
    return await actor.put(
        f"/tenants/{t}/entities/{who}/frames/{axis}", json={"frame_entity_id": frame}
    )


async def own(actor: Any, t: Any, who: str) -> dict[str, Any]:
    response = await actor.get(f"/tenants/{t}/entities/{who}/frames")
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def address(actor: Any, t: Any, who: str) -> list[dict[str, Any]]:
    response = await actor.get(f"/tenants/{t}/entities/{who}/address")
    assert response.status_code == 200, response.text
    steps: list[dict[str, Any]] = response.json()["segments"]
    return steps


def frames_in(steps: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [(s["axis"], s["name"]) for s in steps if s["via"] == "frame"]


async def a_frame(actor: Any, t: Any, name: str, *axes: str) -> str:
    made = await entry(actor, t, name)
    for axis in axes or ("plane",):
        assert (await designate(actor, t, made, axis)).status_code == 200
    return made


async def test_an_entry_is_a_frame_and_another_is_on_it(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        ethereal = await entry(gm, t, "Ethereal")
        prime = await a_frame(gm, t, "Prime Material")
        elf = await entry(gm, t, "Elf")
        first = await designate(gm, t, ethereal)
        again = await designate(gm, t, ethereal)
        assert first.status_code == again.status_code == 200
        assert first.json() == {"entity_id": ethereal, "axis": "plane"}
        assert await own(gm, t, ethereal) == {"frame_axes": ["plane"], "frames": []}

        put = await put_on(gm, t, elf, ethereal)
        assert put.status_code == 200
        assert put.json() == {"entity_id": elf, "axis": "plane", "frame_entity_id": ethereal}
        mine = await own(gm, t, elf)
        assert mine["frame_axes"] == []
        assert [(r["axis"], r["frame"]["name"]) for r in mine["frames"]] == [("plane", "Ethereal")]
        assert mine["frames"][0]["frame"]["id"] == ethereal

        listed = (await gm.get(f"/tenants/{t}/frames")).json()
        assert [(i["entry"]["name"], i["axes"]) for i in listed["items"]] == [
            ("Ethereal", ["plane"]),
            ("Prime Material", ["plane"]),
        ]
        assert listed["total"] == 2
        assert (await gm.get(f"/tenants/{t}/frames", params={"axis": "sphere"})).json()[
            "items"
        ] == []
        assert [
            i["entry"]["name"]
            for i in (await gm.get(f"/tenants/{t}/frames", params={"q": "prim"})).json()["items"]
        ] == ["Prime Material"]
        members = (await gm.get(f"/tenants/{t}/entities/{ethereal}/frame-members")).json()
        assert [(m["entry"]["name"], m["axis"]) for m in members["items"]] == [("Elf", "plane")]

        # Putting it on another frame replaces the first.
        assert (await put_on(gm, t, elf, prime)).status_code == 200
        assert (await gm.get(f"/tenants/{t}/entities/{ethereal}/frame-members")).json()[
            "items"
        ] == []
        assert [r["frame"]["name"] for r in (await own(gm, t, elf))["frames"]] == ["Prime Material"]
        # Taking it off, and putting it back and taking the designation away.
        assert (await gm.delete(f"/tenants/{t}/entities/{elf}/frames/plane")).status_code == 204
        assert (await own(gm, t, elf))["frames"] == []
        assert (await put_on(gm, t, elf, prime)).status_code == 200
        gone = await gm.delete(f"/tenants/{t}/entities/{prime}/frame-axes/plane")
        assert gone.status_code == 204
        assert (await own(gm, t, elf))["frames"] == []
        assert (await gm.get(f"/tenants/{t}/entities/{prime}/frame-members")).status_code == 404
    finally:
        await w.clean_up()


async def test_what_makes_no_frame_is_refused(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        ethereal = await a_frame(gm, t, "Ethereal")
        elf = await entry(gm, t, "Elf")
        plain = await entry(gm, t, "Plain")
        secret = await place(gm, t, "Hidden keep")

        assert (await designate(gm, t, plain, "dimension")).status_code == 422
        assert (await put_on(gm, t, elf, ethereal, "dimension")).status_code == 422
        assert (await designate(gm, t, plain, "Plane")).status_code == 422
        # The target must be a frame, on that axis.
        assert (await put_on(gm, t, elf, plain)).status_code == 422
        assert (await put_on(gm, t, elf, ethereal, "sphere")).status_code == 422
        # Nor itself.
        assert (await put_on(gm, t, ethereal, ethereal)).status_code == 422
        # A target that is not there, or that the writer cannot see, is the same 404.
        assert (await put_on(gm, t, elf, str(uuid.uuid4()))).status_code == 404
        assert (await put_on(gm, t, str(uuid.uuid4()), ethereal)).status_code == 404
        assert (await designate(gm, t, str(uuid.uuid4()))).status_code == 404
        assert (
            await gm.put(f"/tenants/{t}/entities/{elf}/frames/plane", json={"extra": 1})
        ).status_code == 422
        # Only those who write Locations read or write any of it.
        for response in (
            await designate(player, t, plain),
            await put_on(player, t, elf, ethereal),
            await player.get(f"/tenants/{t}/frames"),
            await player.get(f"/tenants/{t}/entities/{elf}/frames"),
            await player.get(f"/tenants/{t}/entities/{ethereal}/frame-members"),
            await player.delete(f"/tenants/{t}/entities/{elf}/frames/plane"),
        ):
            assert response.status_code == 403, response.text
        assert secret["id"]
    finally:
        await w.clean_up()


async def test_a_chain_of_frames_has_no_loop_and_a_limit(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        chain = [await a_frame(gm, t, f"Plane {n}") for n in range(10)]
        # Eight frames of one axis in a chain is the most: each is on the one above.
        for below, above in reversed(list(zip(chain[:8], chain[1:9], strict=True))):
            assert (await put_on(gm, t, below, above)).status_code == 200
        loop = await put_on(gm, t, chain[8], chain[0])
        assert loop.status_code == 422 and "loop" in loop.json()["detail"]
        too_long = await put_on(gm, t, chain[9], chain[0])
        assert too_long.status_code == 422 and "at most 8" in too_long.json()["detail"]
        # Another axis is its own chain.
        assert (await designate(gm, t, chain[1], "universe")).status_code == 200
        assert (await designate(gm, t, chain[0], "universe")).status_code == 200
        assert (await put_on(gm, t, chain[1], chain[0], "universe")).status_code == 200
    finally:
        await w.clean_up()


async def test_the_nearest_explicit_row_wins_along_the_address(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        city = await place(gm, t, "Neverwinter", is_public=True)
        tavern = await place(gm, t, "Rusty Tankard", is_public=True, parent_id=city["id"])
        cellar = await place(gm, t, "Cellar", is_public=True, parent_id=tavern["id"])
        pack = await entry(gm, t, "Backpack")
        sword = await entry(gm, t, "Sword")
        await contain(t, sword, pack)
        assert (await put_at(gm, t, pack, tavern["id"])).status_code == 200
        first = await a_frame(gm, t, "Prime Material")
        second = await a_frame(gm, t, "Shadowfell")
        third = await a_frame(gm, t, "Feywild")

        # No row, no frame step, and no key on any other step.
        before = await address(gm, t, sword)
        assert frames_in(before) == [] and all("axis" not in step for step in before)

        # The city's frame reaches what is at its Locations, through the place and its ancestors.
        assert (await put_on(gm, t, city["id"], first)).status_code == 200
        assert frames_in(await address(gm, t, sword)) == [("plane", "Prime Material")]
        found = await address(gm, t, sword)
        assert [s["via"] for s in found] == ["contained_in", "at", "part_of", "frame"]
        assert found[-1]["entity_id"] == first

        # A nearer row beats it: the tavern's over the city's, then the container's own.
        assert (await put_on(gm, t, tavern["id"], second)).status_code == 200
        assert frames_in(await address(gm, t, sword)) == [("plane", "Shadowfell")]
        assert (await put_on(gm, t, pack, third)).status_code == 200
        assert frames_in(await address(gm, t, sword)) == [("plane", "Feywild")]
        assert (await put_on(gm, t, sword, first)).status_code == 200
        assert frames_in(await address(gm, t, sword)) == [("plane", "Prime Material")]

        # A Location takes its frame from the Locations above it.
        assert frames_in(await address(gm, t, cellar["id"])) == [("plane", "Shadowfell")]
        # Axes are independent, and are listed in the order the platform names them.
        sphere = await a_frame(gm, t, "Realmspace", "sphere", "universe")
        assert (await put_on(gm, t, city["id"], sphere, "universe")).status_code == 200
        assert (await put_on(gm, t, city["id"], sphere, "sphere")).status_code == 200
        assert frames_in(await address(gm, t, cellar["id"])) == [
            ("plane", "Shadowfell"),
            ("sphere", "Realmspace"),
            ("universe", "Realmspace"),
        ]
        # Nothing comes through a prototype.
        child = (
            await gm.post(
                f"/tenants/{t}/entities",
                json={"name": "Copy of sword", "kinds": ["item"], "prototypes": [sword]},
            )
        ).json()["id"]
        assert frames_in(await address(gm, t, child)) == []
    finally:
        await w.clean_up()


async def test_a_frame_on_a_frame_goes_on_up_and_a_loop_of_raw_rows_ends_quietly(
    raw_client, fake_jwks_server
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        prime = await a_frame(gm, t, "Prime Material")
        ethereal = await a_frame(gm, t, "Ethereal")
        elf = await entry(gm, t, "Elf")
        assert (await put_on(gm, t, ethereal, prime)).status_code == 200
        assert (await put_on(gm, t, elf, ethereal)).status_code == 200
        assert frames_in(await address(gm, t, elf)) == [
            ("plane", "Ethereal"),
            ("plane", "Prime Material"),
        ]
        # A loop only a repository could make: rows, not a write.
        async with admin_session_factory() as session:
            session.add(
                EntityFrame(
                    entity_id=uuid.UUID(prime),
                    axis="plane",
                    frame_entity_id=uuid.UUID(ethereal),
                    tenant_id=t,
                )
            )
            await session.commit()
        assert frames_in(await address(gm, t, elf)) == [
            ("plane", "Ethereal"),
            ("plane", "Prime Material"),
        ]
    finally:
        await w.clean_up()


async def test_a_frame_the_reader_cannot_see_is_no_row(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        open_frame = await place(gm, t, "Open sky", is_public=True)
        closed_frame = await place(gm, t, "Closed vault")
        for frame in (open_frame["id"], closed_frame["id"]):
            assert (await designate(gm, t, frame)).status_code == 200
        near = await place(gm, t, "Near room", is_public=True)
        far = await place(gm, t, "Far hall", is_public=True, parent_id=near["id"])
        assert (await put_on(gm, t, near["id"], open_frame["id"])).status_code == 200
        assert (await put_on(gm, t, far["id"], closed_frame["id"])).status_code == 200

        async with admin_session_factory() as session:
            seen = await resolve_information_visibility(
                session, user_id=w.outsider.user_id, tenant_id=t
            )
            chain = [uuid.UUID(far["id"]), uuid.UUID(near["id"])]
            as_player = await frames_module.frames_along(session, seen, tenant_id=t, chain=chain)
        # The nearer row is a frame the reader cannot see: it is absent, and the next one speaks.
        assert as_player == {"plane": [uuid.UUID(open_frame["id"])]}
        assert frames_in(await address(gm, t, far["id"])) == [("plane", "Closed vault")]
        assert player
    finally:
        await w.clean_up()


async def test_no_player_read_changes_and_no_reach_code_names_a_frame(raw_client, fake_jwks_server):
    import pathlib

    w, _, pid = await world(raw_client, fake_jwks_server)
    try:
        t, gm, player = w.tenant_id, w.author, w.outsider
        city = await place(gm, t, "Neverwinter", is_public=True)
        sword = await entry(gm, t, "Sword")
        assert (await put_at(gm, t, sword, city["id"])).status_code == 200
        reads = [
            f"/tenants/{t}/entities/{sword}",
            f"/tenants/{t}/entities/{city['id']}",
            f"/tenants/{t}/locations/{city['id']}",
            f"/tenants/{t}/entities",
        ]
        sky = await entry(gm, t, "Sky")
        before = [(await player.get(path)).content for path in reads]
        for axis in ("plane", "sphere"):
            assert (await designate(gm, t, sky, axis)).status_code == 200
        for who in (city["id"], sword):
            assert (await put_on(gm, t, who, sky)).status_code == 200
        after = [(await player.get(path)).content for path in reads]
        assert before == after
        assert pid

        source = pathlib.Path(frames_module.__file__).parent
        for name in ("entity_access.py", "information_visibility.py", "campaign_access.py"):
            text_of = (source / name).read_text("utf-8")
            assert "EntityFrame" not in text_of and "lorenzo_api.frames" not in text_of
    finally:
        await w.clean_up()


async def test_deleting_an_entry_or_a_designation_removes_its_rows(raw_client, fake_jwks_server):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        sky = await a_frame(gm, t, "Sky")
        elf = await entry(gm, t, "Elf")
        imp = await entry(gm, t, "Imp")
        assert (await put_on(gm, t, elf, sky)).status_code == 200
        assert (await put_on(gm, t, imp, sky)).status_code == 200

        async def rows() -> tuple[int, int]:
            async with admin_session_factory() as session:
                designated = len(
                    (await session.scalars(select(Frame).where(Frame.tenant_id == t))).all()
                )
                members = len(
                    (
                        await session.scalars(select(EntityFrame).where(EntityFrame.tenant_id == t))
                    ).all()
                )
                return designated, members

        assert await rows() == (1, 2)
        async with admin_session_factory() as session:
            await session.execute(delete(Entity).where(Entity.id == uuid.UUID(elf)))
            await session.commit()
        assert await rows() == (1, 1)
        async with admin_session_factory() as session:
            await session.execute(delete(Entity).where(Entity.id == uuid.UUID(sky)))
            await session.commit()
        assert await rows() == (0, 0)
    finally:
        await w.clean_up()


async def test_the_limits_of_a_library_and_the_shape_of_the_tables(
    raw_client, fake_jwks_server, monkeypatch
):
    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t, gm = w.tenant_id, w.author
        monkeypatch.setattr(frames_module, "MAX_FRAMES_PER_LIBRARY", 2)
        monkeypatch.setattr(frames_module, "MAX_MEMBERSHIPS_PER_LIBRARY", 1)
        first = await a_frame(gm, t, "One")
        await a_frame(gm, t, "Two")
        third = await entry(gm, t, "Three")
        refused = await designate(gm, t, third)
        assert refused.status_code == 422 and "at most 2" in refused.json()["detail"]
        # Saying it again is not one more.
        assert (await designate(gm, t, first)).status_code == 200
        elf, imp = await entry(gm, t, "Elf"), await entry(gm, t, "Imp")
        assert (await put_on(gm, t, elf, first)).status_code == 200
        assert (await put_on(gm, t, elf, first)).status_code == 200
        assert (await put_on(gm, t, imp, first)).status_code == 422

        # Neither table has a time, a name, a label or a coordinate (RFC 0048 G2).
        async with admin_session_factory() as session:
            columns = {
                (row[0], row[1])
                for row in await session.execute(
                    text(
                        "SELECT table_name, column_name FROM information_schema.columns "
                        "WHERE table_name IN ('frame', 'entity_frame')"
                    )
                )
            }
        assert columns == {
            ("frame", "entity_id"),
            ("frame", "axis"),
            ("frame", "tenant_id"),
            ("entity_frame", "entity_id"),
            ("entity_frame", "axis"),
            ("entity_frame", "frame_entity_id"),
            ("entity_frame", "tenant_id"),
        }
    finally:
        await w.clean_up()


@pytest.mark.parametrize("axis", ["Plane", "1plane", "plane-x", "", "a" * 33])
async def test_the_database_keeps_the_shape_of_an_axis(raw_client, fake_jwks_server, axis):
    from sqlalchemy.exc import IntegrityError

    w, _, _ = await world(raw_client, fake_jwks_server)
    try:
        t = w.tenant_id
        who = await entry(w.author, t, "Thing")
        async with admin_session_factory() as session:
            session.add(Frame(entity_id=uuid.UUID(who), axis=axis, tenant_id=t))
            with pytest.raises(IntegrityError):
                await session.commit()
    finally:
        await w.clean_up()


async def test_a_copy_carries_frames_and_drops_what_it_cannot() -> None:
    from datetime import UTC, datetime

    from _repository_fixtures import seed_every_content_table

    from lorenzo_api.models import RepositorySubscription, Tenant, TenantKind
    from lorenzo_api.repository_copying import plan_copy

    async with admin_session_factory() as session:
        repository = Tenant(name="Planes", kind=TenantKind.REPOSITORY)
        library = Tenant(name="My Table planes")
        session.add_all([repository, library])
        await session.flush()
        await seed_every_content_table(session, repository.id)
        # An axis this version does not know, as a newer repository might hold.
        fixture = (
            await session.scalars(
                select(Frame).where(Frame.tenant_id == repository.id, Frame.axis == "plane")
            )
        ).one()
        session.add(Frame(entity_id=fixture.entity_id, axis="dimension", tenant_id=repository.id))
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
        (designation,) = plan.rows["frame"]
        (membership,) = plan.rows["entity_frame"]
        assert local[designation["entity_id"]] == "Fixture place"
        assert designation["axis"] == "plane" and designation["tenant_id"] == library_id
        assert local[membership["entity_id"]] == "Fixture room"
        assert membership["frame_entity_id"] == designation["entity_id"]
        dropped = [d for step in plan.steps for d in step.dropped if d.kind == "frame"]
        assert [d.reason for d in dropped] == ["this version does not know the axis dimension"]
    finally:
        async with admin_session_factory() as session:
            for tenant_id in (library_id, repository_id):
                await session.delete(await session.get_one(Tenant, tenant_id))
            await session.commit()
