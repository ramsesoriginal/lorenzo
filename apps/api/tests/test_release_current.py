"""ADR 0288: the release a library reads is the repository's current one. A publish makes its
release current, an earlier release whose document is still kept can be made current again (the
rollback), the released rows follow, and the documents of old releases are dropped by retention.
"""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import cleanup, make_actor
from _upstream_documents import set_visibility
from httpx import AsyncClient
from sqlalchemy import func, select
from test_api_release_digest import _removed, _rename
from test_api_repository_releases import _add_orga, _notices
from test_repository_release_documents import _delete, _release, _repository

from lorenzo_api.config import get_settings
from lorenzo_api.models import (
    RepositoryRelease,
    RepositoryReleaseBlob,
    RepositoryReleaseDocument,
    Tenant,
)
from lorenzo_api.release_document_store import (
    kept_documents,
    prune_release_documents,
    store_release_document,
)
from lorenzo_api.repository_content import load_content


async def _public_world(
    raw_client: AsyncClient, jwks: FakeJwksServer, *, copied: bool = False
) -> ReleaseWorld:
    """Armoury, public, with release 1.0 (its document written)."""
    world = await release_world(raw_client, jwks, published=False, copied=False)
    await set_visibility([world.repository], "public")
    await world.publish(label="1.0")
    if copied:
        await world.copy()
    return world


async def _put_current(world: ReleaseWorld, release_id: str, **body: Any) -> Any:
    return await world.author.put(
        f"/tenants/{world.repository}/releases/{release_id}/current", json=body or None
    )


async def _by_label(world: ReleaseWorld) -> dict[str, dict[str, Any]]:
    return {r["label"]: r for r in await world.releases()}


async def _library_names(world: ReleaseWorld) -> list[str]:
    response = await world.gm.get(
        f"/tenants/{world.table}/repositories/{world.repository}/entities"
    )
    assert response.status_code == 200, response.text
    return [e["name"] for e in response.json()["items"]]


async def _pointer(repository: uuid.UUID) -> uuid.UUID | None:
    async with admin_session_factory() as session:
        return await session.scalar(
            select(Tenant.current_release_id).where(Tenant.id == repository)
        )


# --- A publish makes its release current -------------------------------------------------------


async def test_a_publish_makes_its_release_current_and_a_library_reads_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        first = (await _by_label(world))["1.0"]
        assert (first["current"], first["kept"]) == (True, True)
        assert await _pointer(world.repository) == uuid.UUID(first["id"])

        await _rename(world)
        second = await world.publish(label="2.0")
        assert (second["current"], second["kept"]) == (True, True)

        releases = await _by_label(world)
        assert [releases[label]["current"] for label in ("1.0", "2.0")] == [False, True]
        assert await _pointer(world.repository) == uuid.UUID(second["id"])
        # What a library lists is told the same, without who published it.
        listed = await world.gm.get(
            f"/tenants/{world.table}/repositories/{world.repository}/releases"
        )
        assert {r["label"]: r["current"] for r in listed.json()["items"]} == {
            "1.0": False,
            "2.0": True,
        }
    finally:
        await world.done()


async def test_a_private_repository_keeps_no_document_and_its_newest_release_is_current(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)  # 1.0, private
    try:
        await world.publish(label="2.0")
        releases = await _by_label(world)
        assert (releases["2.0"]["current"], releases["2.0"]["kept"]) == (True, False)
        assert releases["1.0"]["current"] is False
    finally:
        await world.done()


# --- Making an earlier release current ---------------------------------------------------------


async def test_making_an_earlier_release_current_changes_what_a_library_reads(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        await _rename(world)  # Longsword -> Long Sword
        await world.publish(label="2.0")
        assert await _library_names(world) == ["Dagger", "Long Sword", "Orc"]

        releases = await _by_label(world)
        response = await _put_current(world, releases["1.0"]["id"])
        assert response.status_code == 200, response.text
        assert (response.json()["label"], response.json()["current"]) == ("1.0", True)

        assert await _library_names(world) == ["Dagger", "Longsword", "Orc"]
        assert await _pointer(world.repository) == uuid.UUID(releases["1.0"]["id"])
        after = await _by_label(world)
        assert [after[label]["current"] for label in ("1.0", "2.0")] == [True, False]

        # "Edited since" compares the live content with the release that is current: the
        # live rows are 2.0's, so against 1.0 one row differs.
        preview = await world.preview()
        assert preview["release"]["label"] == "1.0"
        assert preview["matches"] is False
        assert preview["differing_rows"] == 1

        # Publishing again numbers on from the newest and is current at once.
        third = await world.publish(label="3.0")
        assert (third["number"], third["current"]) == (3, True)
        assert await _library_names(world) == ["Dagger", "Long Sword", "Orc"]
    finally:
        await world.done()


async def test_the_rows_a_release_matches_follow_the_release_made_current(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        await _rename(world)
        await world.publish(label="2.0")
        assert (await world.preview())["matches"] is True

        releases = await _by_label(world)
        await _put_current(world, releases["1.0"]["id"])
        assert (await world.preview())["matches"] is False

        # Back to the release the live content is, and it matches again.
        assert (await _put_current(world, releases["2.0"]["id"])).status_code == 200
        preview = await world.preview()
        assert (preview["release"]["label"], preview["matches"]) == ("2.0", True)
    finally:
        await world.done()


async def test_a_library_on_the_newer_release_sees_the_older_state_as_changes_and_is_told(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        await _rename(world)
        await world.publish(label="2.0")
        await world.copy()  # the library takes 2.0
        updates = await world.updates()
        assert (len(updates["changed"]), updates["release"]["label"]) == (0, "2.0")
        told = len(await _notices(world.gm))

        releases = await _by_label(world)
        await _put_current(world, releases["1.0"]["id"])

        updates = await world.updates()
        assert updates["release"]["label"] == "1.0"
        assert updates["release"]["current"] is True
        assert [c["name"] for c in updates["changed"]] == ["Long Sword"]
        notices = await _notices(world.gm)
        assert len(notices) == told + 1
        newest = notices[0]
        assert newest["type"] == "repository_updated"
        assert "release 1.0 current" in newest["title"]
        assert "later release" in newest["body"]
    finally:
        await world.done()


async def test_making_the_current_release_current_does_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        told = len(await _notices(world.gm))
        current = (await _by_label(world))["1.0"]
        response = await _put_current(world, current["id"])
        assert response.status_code == 200
        assert response.json()["current"] is True
        assert len(await _notices(world.gm)) == told
    finally:
        await world.done()


# --- The detector between the two releases -----------------------------------------------------


async def test_moving_to_a_release_that_breaks_what_libraries_hold_needs_acknowledging(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        await _removed(world)  # Orc goes
        await world.publish(label="2.0", acknowledge_breaking=True)
        releases = await _by_label(world)

        # Back to 1.0, which has Orc: a row more, nothing a library loses.
        assert (await _put_current(world, releases["1.0"]["id"])).status_code == 200

        # Forward to 2.0 again: a library on 1.0 holds Orc, which 2.0 does not.
        refused = await _put_current(world, releases["2.0"]["id"])
        assert refused.status_code == 409
        assert refused.json()["type"].endswith("release-has-breaking-changes")
        assert [(b["kind"], b["name"]) for b in refused.json()["breaking_rows"]] == [
            ("entity", "Orc")
        ]
        assert await _library_names(world) == ["Dagger", "Longsword", "Orc"]  # nothing moved

        accepted = await _put_current(world, releases["2.0"]["id"], acknowledge_breaking=True)
        assert accepted.status_code == 200, accepted.text
        assert await _library_names(world) == ["Dagger", "Longsword"]
    finally:
        await world.done()


# --- What cannot be made current ---------------------------------------------------------------


async def test_a_release_whose_content_is_not_kept_cannot_be_made_current(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        before = await world.publish(label="1.0")  # private: no document
        await set_visibility([world.repository], "public")
        await world.publish(label="2.0")
        refused = await _put_current(world, before["id"])
        assert refused.status_code == 409
        assert refused.json()["type"].endswith("release-not-retained")
        assert (await _by_label(world))["2.0"]["current"] is True
    finally:
        await world.done()


async def test_only_the_owner_makes_a_release_current_and_only_one_of_this_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    try:
        await _add_orga(world.repository, orga)
        release = (await _by_label(world))["1.0"]
        response = await orga.put(f"/tenants/{world.repository}/releases/{release['id']}/current")
        assert response.status_code == 403, response.text
        assert (await _put_current(world, str(uuid.uuid4()))).status_code == 404

        other = await make_actor(raw_client, fake_jwks_server, "other")
        await set_visibility([world.repository], "private")
        elsewhere = await other.create_tenant("Elsewhere", kind="repository")
        world.tenants.append(elsewhere)
        world.actors.append(other)
        # A release of another repository is not found, for its own Owner either.
        crossed = await other.put(f"/tenants/{elsewhere}/releases/{release['id']}/current")
        assert crossed.status_code == 404
        assert (await _by_label(world))["1.0"]["current"] is True
    finally:
        await world.done()
        await cleanup([], [orga])


# --- Retention ---------------------------------------------------------------------------------


async def test_publishing_drops_the_documents_beyond_the_newest_and_keeps_the_ledger(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "release_documents_retained", 2)
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        for label in ("2.0", "3.0", "4.0"):
            await world.publish(label=label)
        releases = await _by_label(world)
        assert {label: r["kept"] for label, r in releases.items()} == {
            "1.0": False,
            "2.0": False,
            "3.0": True,
            "4.0": True,
        }
        # Every release keeps its ledger row, its digest and its counts for good.
        assert all(r["digest"] and r["counts"] is not None for r in releases.values())
        async with admin_session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count()).where(RepositoryRelease.tenant_id == world.repository)
                )
                == 4
            )
            assert (
                await session.scalar(
                    select(func.count()).where(
                        RepositoryReleaseDocument.tenant_id == world.repository
                    )
                )
                == 2
            )
    finally:
        await world.done()


async def test_pruning_keeps_the_current_release_and_the_files_a_kept_document_needs() -> None:
    repository = await _repository()
    first = await _release(repository, 1)
    second = await _release(repository, 2)
    third = await _release(repository, 3)
    orphan = "ff" * 32
    try:
        async with admin_session_factory() as session:
            seeded = len(await kept_documents(session, repository))  # the fixture's own release
            loaded = await load_content(session, repository)
            for release in (first, second, third):
                await store_release_document(
                    session, tenant_id=repository, release_id=release, content=loaded
                )
            session.add(
                RepositoryReleaseBlob(tenant_id=repository, sha256=orphan, data=b"nothing refers")
            )
            await session.commit()

        async def kept() -> tuple[set[uuid.UUID], int]:
            async with admin_session_factory() as session:
                return (
                    await kept_documents(session, repository),
                    int(
                        await session.scalar(
                            select(func.count()).where(
                                RepositoryReleaseBlob.tenant_id == repository
                            )
                        )
                        or 0
                    ),
                )

        files = (await kept())[1] - 1  # what the documents refer to, without the orphan

        # The newest one and the current one stay; the middle one goes; so does the orphan.
        async with admin_session_factory() as session:
            pruned = await prune_release_documents(
                session, tenant_id=repository, keep=1, current_release_id=first
            )
            await session.commit()
        assert (pruned.documents, pruned.files) == (seeded + 1, 1)
        assert await kept() == ({first, third}, files)

        # With nothing current, only the newest stays, and the files it needs.
        async with admin_session_factory() as session:
            await prune_release_documents(
                session, tenant_id=repository, keep=1, current_release_id=None
            )
            await session.commit()
        assert await kept() == ({third}, files)

        # With none kept, the files go too.
        async with admin_session_factory() as session:
            await prune_release_documents(
                session, tenant_id=repository, keep=0, current_release_id=None
            )
            await session.commit()
        assert await kept() == (set(), 0)
    finally:
        await _delete(repository)
