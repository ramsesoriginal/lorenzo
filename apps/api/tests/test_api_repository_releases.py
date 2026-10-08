"""ADR 0207 through the real HTTP API: publishing a repository is a release
with a label, notes and a breaking flag; the repository's members and the
tenants granted it read the list; the release rides on the notification, on
the copy's record of what it last took, and in the activity log.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import select, text

from lorenzo_api.db import engine
from lorenzo_api.models import AuditLog, Membership, MembershipRole


async def _item(author: Actor, repository: uuid.UUID, name: str = "Longsword") -> None:
    created = await author.post(
        f"/tenants/{repository}/items",
        json={"name": name, "prototype_ids": [], "in_public_catalog": False},
    )
    assert created.status_code == 201, created.text


async def _publish(
    author: Actor, repository: uuid.UUID, body: dict[str, object] | None = None
) -> dict[str, object]:
    response = await (
        author.put(f"/tenants/{repository}/published", json=body)
        if body is not None
        else author.put(f"/tenants/{repository}/published")
    )
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def _releases(actor: Actor, repository: uuid.UUID) -> list[dict[str, object]]:
    response = await actor.get(f"/tenants/{repository}/releases")
    assert response.status_code == 200, response.text
    return response.json()["items"]  # type: ignore[no-any-return]


async def _notices(actor: Actor) -> list[dict[str, str]]:
    response = await actor.get("/me/notifications")
    assert response.status_code == 200, response.text
    return response.json()["items"]  # type: ignore[no-any-return]


async def _add_orga(tenant: uuid.UUID, actor: Actor) -> None:
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=tenant, user_id=actor.user_id, role=MembershipRole.ORGA))
        await session.commit()


async def test_publishing_without_a_body_makes_a_release_labelled_with_its_number(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    try:
        await _item(author, faerun)
        published = await _publish(author, faerun)

        # The tenant, as before, and the release that was made.
        assert published["id"] == str(faerun)
        assert published["published_at"] is not None
        release = published["release"]
        assert isinstance(release, dict)
        assert (release["number"], release["label"]) == (1, "1")
        assert release["notes"] is None
        assert release["breaking"] is False

        listed = await _releases(author, faerun)
        assert [r["id"] for r in listed] == [release["id"]]
        assert listed[0]["created_by"] == str(author.user_id)
        assert listed[0]["created_at"] is not None

        again = (await _publish(author, faerun))["release"]
        assert isinstance(again, dict)
        assert (again["number"], again["label"]) == (2, "2")
    finally:
        await cleanup([faerun], [author])


async def test_a_release_keeps_its_label_notes_and_breaking_flag_newest_first(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    try:
        await _item(author, faerun)
        await _publish(author, faerun, {"label": "  1.0  ", "notes": "The first cut."})
        await _publish(
            author, faerun, {"label": "Spring errata", "notes": "Fixed prices.", "breaking": True}
        )

        listed = await _releases(author, faerun)
        assert [(r["number"], r["label"], r["notes"], r["breaking"]) for r in listed] == [
            (2, "Spring errata", "Fixed prices.", True),
            (1, "1.0", "The first cut.", False),
        ]
    finally:
        await cleanup([faerun], [author])


async def test_labels_are_unique_in_a_repository_whatever_their_case(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    other = await make_actor(raw_client, fake_jwks_server, "other")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    sembia = await other.create_tenant("Sembia", kind="repository")
    try:
        await _publish(author, faerun, {"label": "Spring"})
        taken = await author.put(f"/tenants/{faerun}/published", json={"label": "SPRING"})
        assert taken.status_code == 409
        assert taken.json()["type"] == "release-label-taken"
        # Nothing was made, and the repository did not move.
        assert [r["label"] for r in await _releases(author, faerun)] == ["Spring"]

        # A default label is a label too: release 2 would be called "2".
        await _publish(author, faerun, {"label": "3"})
        clash = await author.put(f"/tenants/{faerun}/published")
        assert clash.status_code == 409
        assert clash.json()["type"] == "release-label-taken"

        # Another repository has its own labels.
        await _publish(other, sembia, {"label": "Spring"})
    finally:
        await cleanup([faerun, sembia], [author, other])


async def test_a_label_and_notes_must_be_sensible(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    try:
        for body in (
            {"label": ""},
            {"label": "   "},
            {"label": "x" * 81},
            {"notes": "n" * 4001},
        ):
            refused = await author.put(f"/tenants/{faerun}/published", json=body)
            assert refused.status_code == 422, body
        assert await _releases(author, faerun) == []
        assert (await author.get(f"/tenants/{faerun}")).json()["published_at"] is None

        # The limits themselves are fine, and blank notes are no notes.
        await _publish(author, faerun, {"label": "x" * 80, "notes": "   "})
        await _publish(author, faerun, {"label": "y", "notes": "n" * 4000})
        notes = [r["notes"] for r in await _releases(author, faerun)]
        assert notes == ["n" * 4000, None]
    finally:
        await cleanup([faerun], [author])


async def test_only_an_owner_publishes_and_only_members_read_the_list(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    elsewhere = await stranger.create_tenant("Elsewhere")
    await _add_orga(faerun, orga)
    try:
        refused = await orga.put(f"/tenants/{faerun}/published", json={"label": "Mine"})
        assert refused.status_code == 403
        await _publish(author, faerun, {"label": "1.0"})

        assert [r["label"] for r in await _releases(orga, faerun)] == ["1.0"]
        assert (await stranger.get(f"/tenants/{faerun}/releases")).status_code in (403, 404)

        # A play tenant has no releases.
        assert (await stranger.get(f"/tenants/{elsewhere}/releases")).status_code == 409
    finally:
        await cleanup([elsewhere, faerun], [author, orga, stranger])


async def test_a_granted_library_reads_the_releases_of_a_published_repository_only(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    sembia = await author.create_tenant("Sembia", kind="repository")
    table = await gm.create_tenant("My Table")
    elsewhere = await stranger.create_tenant("Elsewhere")
    try:
        await _item(author, faerun)
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        # Invited, not published: nothing, as for every read of a draft.
        draft = await gm.get(f"/tenants/{table}/repositories/{faerun}/releases")
        assert draft.status_code == 404
        assert draft.json()["type"] == "repository-not-found"

        await _publish(author, faerun, {"label": "1.0", "notes": "Hello."})
        await _publish(author, faerun, {"label": "1.1", "breaking": True})
        seen = await gm.get(f"/tenants/{table}/repositories/{faerun}/releases")
        assert seen.status_code == 200, seen.text
        items = seen.json()["items"]
        assert [(r["number"], r["label"], r["notes"], r["breaking"]) for r in items] == [
            (2, "1.1", None, True),
            (1, "1.0", "Hello.", False),
        ]
        # Who published is for the repository's own people.
        assert all("created_by" not in r for r in items)

        # Not a repository this library is granted, one that is not published,
        # and somebody else's library: all the same answer.
        await _publish(author, sembia)
        for who, library, repository in (
            (gm, table, sembia),
            (stranger, elsewhere, faerun),
            (stranger, table, faerun),
        ):
            response = await who.get(f"/tenants/{library}/repositories/{repository}/releases")
            assert response.status_code in (403, 404), (library, repository)

        # And the library cannot read them as if they were its own.
        assert (await gm.get(f"/tenants/{faerun}/releases")).status_code in (403, 404)
    finally:
        await cleanup([table, elsewhere, faerun, sembia], [author, gm, stranger])


async def test_the_release_rides_on_the_notification(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        await author.put(f"/tenants/{faerun}/subscribers/{table}")

        await _publish(author, faerun, {"label": "1.0"})
        first = (await _notices(gm))[0]
        # The first publish keeps its own words.
        assert first["type"] == "repository_published"
        assert first["title"] == "Faerûn is published"

        await _publish(author, faerun, {"label": "1.1", "notes": "Prices fixed."})
        second = (await _notices(gm))[0]
        assert second["type"] == "repository_updated"
        assert second["title"] == "Faerûn published release 1.1"
        assert second["body"] == "Prices fixed."

        await _publish(author, faerun, {"label": "2.0", "notes": "New weapons.", "breaking": True})
        third = (await _notices(gm))[0]
        assert third["title"] == "Faerûn published release 2.0"
        assert third["body"].startswith("New weapons.")
        assert "breaking" in third["body"]
        assert "tenant" not in third["body"].lower()

        # No notes, not breaking: the old line, which is still true.
        await _publish(author, faerun)
        fourth = (await _notices(gm))[0]
        assert fourth["title"] == "Faerûn published release 4"
        assert fourth["body"] == "Check its updates to see what changed."
    finally:
        await cleanup([table, faerun], [author, gm])


async def test_long_notes_are_cut_on_the_notification_and_not_on_the_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    notes = " ".join(f"word{i}" for i in range(200))
    try:
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await _publish(author, faerun)
        await _publish(author, faerun, {"label": "Long", "notes": notes})

        body = (await _notices(gm))[0]["body"]
        assert len(body) <= 300
        assert body.endswith("…")
        assert notes.startswith(body.removesuffix("…").rstrip())
        # Cut between words.
        assert not body.removesuffix("…").endswith(("word", "wor", "wo", "w"))
        assert (await _releases(author, faerun))[0]["notes"] == notes
    finally:
        await cleanup([table, faerun], [author, gm])


async def test_the_activity_log_records_the_label(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    try:
        await _publish(author, faerun, {"label": "Spring errata", "breaking": True})
        async with admin_session_factory() as session:
            entry = (
                await session.scalars(
                    select(AuditLog).where(
                        AuditLog.tenant_id == faerun, AuditLog.action == "repository.published"
                    )
                )
            ).one()
        assert entry.detail == "release=1,breaking=true,label=Spring errata"
    finally:
        await cleanup([faerun], [author])


async def test_a_copy_records_the_release_it_last_took(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        await _item(author, faerun)
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await _publish(author, faerun, {"label": "1.0"})
        await _publish(author, faerun, {"label": "1.1"})

        # Invited, not copied: no release.
        before = (await author.get(f"/tenants/{faerun}/subscribers")).json()["items"][0]
        assert before["synced_release"] is None

        copied = await gm.post(f"/tenants/{table}/repositories/{faerun}/copy", json={})
        assert copied.status_code == 201, copied.text
        owner_sees = (await author.get(f"/tenants/{faerun}/subscribers")).json()["items"][0]
        assert owner_sees["synced_release"]["label"] == "1.1"
        assert owner_sees["synced_release"]["number"] == 2
        library_sees = (await gm.get(f"/tenants/{table}/repositories")).json()["items"][0]
        assert library_sees["synced_release"]["label"] == "1.1"

        # The author moves on and publishes again, and the library has not
        # looked: it is still on 1.1 until it applies updates.
        await _item(author, faerun, "Dagger")
        await _publish(author, faerun, {"label": "1.2"})
        waiting = (await author.get(f"/tenants/{faerun}/subscribers")).json()["items"][0]
        assert waiting["synced_release"]["label"] == "1.1"
        library_waiting = (await gm.get(f"/tenants/{table}/repositories")).json()["items"][0]
        assert library_waiting["synced_release"]["label"] == "1.1"
        assert library_waiting["current_release"]["label"] == "1.2"

        updates = await gm.get(f"/tenants/{table}/repositories/{faerun}/updates")
        assert updates.status_code == 200, updates.text
        actions = [
            {"kind": a["kind"], "source_id": a["source_id"], "action": "add"}
            for a in updates.json()["added"]
        ]
        applied = await gm.post(
            f"/tenants/{table}/repositories/{faerun}/updates", json={"actions": actions}
        )
        assert applied.status_code == 200, applied.text
        moved = (await author.get(f"/tenants/{faerun}/subscribers")).json()["items"][0]
        assert moved["synced_release"]["label"] == "1.2"
    finally:
        await cleanup([table, faerun], [author, gm])


async def test_a_dry_run_of_applying_updates_moves_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        await _item(author, faerun)
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await _publish(author, faerun, {"label": "1.0"})
        await gm.post(f"/tenants/{table}/repositories/{faerun}/copy", json={})
        await _publish(author, faerun, {"label": "1.1"})

        dry = await gm.post(
            f"/tenants/{table}/repositories/{faerun}/updates",
            json={"actions": [], "dry_run": True},
        )
        assert dry.status_code == 200, dry.text
        row = (await author.get(f"/tenants/{faerun}/subscribers")).json()["items"][0]
        assert row["synced_release"]["label"] == "1.0"
    finally:
        await cleanup([table, faerun], [author, gm])


async def test_an_owner_edits_the_label_and_notes_and_nothing_else(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    other = await make_actor(raw_client, fake_jwks_server, "other")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    sembia = await other.create_tenant("Sembia", kind="repository")
    await _add_orga(faerun, orga)
    try:
        first = (await _publish(author, faerun, {"label": "1.0", "notes": "Typo here."}))["release"]
        await _publish(author, faerun, {"label": "1.1"})
        foreign = (await _publish(other, sembia, {"label": "9"}))["release"]
        assert isinstance(first, dict) and isinstance(foreign, dict)
        path = f"/tenants/{faerun}/releases/{first['id']}"

        edited = await author.patch(path, json={"label": "One point oh", "notes": "Fixed."})
        assert edited.status_code == 200, edited.text
        assert edited.json()["label"] == "One point oh"
        assert edited.json()["notes"] == "Fixed."
        assert edited.json()["number"] == 1
        assert edited.json()["breaking"] is False

        # Notes alone; clearing them with null; the label's case alone.
        assert (await author.patch(path, json={"notes": None})).json()["notes"] is None
        assert (await author.patch(path, json={"label": "ONE POINT OH"})).status_code == 200

        # The breaking flag is what was announced: it is not editable.
        assert (await author.patch(path, json={"breaking": True})).status_code == 422
        # Neither is a label another release has.
        taken = await author.patch(path, json={"label": "1.1"})
        assert taken.status_code == 409
        assert taken.json()["type"] == "release-label-taken"
        assert (await author.patch(path, json={"label": ""})).status_code == 422

        # Owner only, and only a release of this repository.
        assert (await orga.patch(path, json={"notes": "Mine"})).status_code == 403
        assert (await other.patch(path, json={"notes": "Mine"})).status_code in (403, 404)
        foreign_path = f"/tenants/{faerun}/releases/{foreign['id']}"
        assert (await author.patch(foreign_path, json={"notes": "x"})).status_code == 404
        missing = f"/tenants/{faerun}/releases/{uuid.uuid4()}"
        assert (await author.patch(missing, json={"notes": "x"})).status_code == 404

        assert [(r["label"], r["notes"]) for r in await _releases(author, faerun)] == [
            ("1.1", None),
            ("ONE POINT OH", None),
        ]
        async with admin_session_factory() as session:
            actions = (
                await session.scalars(
                    select(AuditLog.action)
                    .where(AuditLog.tenant_id == faerun)
                    .order_by(AuditLog.created_at)
                )
            ).all()
        assert actions.count("repository.release_edited") == 3
    finally:
        await cleanup([faerun, sembia], [author, orga, other])


async def test_numbers_continue_after_the_repository_goes_back_to_draft(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    try:
        await _publish(author, faerun, {"label": "1.0"})
        assert (await author.delete(f"/tenants/{faerun}/published")).status_code == 200
        # The ledger is the repository's history: unpublishing does not touch it.
        assert [r["number"] for r in await _releases(author, faerun)] == [1]
        again = (await _publish(author, faerun, {"label": "1.1"}))["release"]
        assert isinstance(again, dict)
        assert again["number"] == 2
    finally:
        await cleanup([faerun], [author])


async def test_the_database_shows_a_tenant_only_its_own_releases(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The table's own policies, as the restricted app role (ADR 0021): the
    repository sees its releases and another tenant sees none of them, with
    no grant, with a grant but no gated read, and with the gated read but no
    grant; a granted tenant sees them only inside the gated read of a
    published repository (ADR 0118)."""
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    elsewhere = await gm.create_tenant("Elsewhere")

    async def seen(*, tenant: uuid.UUID, reading: uuid.UUID | None) -> int:
        async with engine.connect() as conn, conn.begin():
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)}
            )
            await conn.execute(
                text("SELECT set_config('app.repository_tenant_id', :r, true)"),
                {"r": str(reading) if reading else ""},
            )
            count = await conn.execute(
                text("SELECT count(*) FROM repository_release WHERE tenant_id = :t"),
                {"t": faerun},
            )
            return int(count.scalar_one())

    try:
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await _publish(author, faerun, {"label": "1.0"})
        await _publish(author, faerun, {"label": "1.1"})

        assert await seen(tenant=faerun, reading=None) == 2
        assert await seen(tenant=table, reading=None) == 0
        assert await seen(tenant=elsewhere, reading=faerun) == 0
        assert await seen(tenant=table, reading=faerun) == 2

        # Back to a draft, the gated read shows nothing.
        await author.delete(f"/tenants/{faerun}/published")
        assert await seen(tenant=table, reading=faerun) == 0
        assert await seen(tenant=faerun, reading=None) == 2
    finally:
        await cleanup([table, elsewhere, faerun], [author, gm])
