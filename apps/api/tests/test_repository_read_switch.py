"""ADR 0286: what a library reads of a repository is its current release's document if the
repository is public, its rows now if it is private. The copy planner, the update engine, the
manifest and the two browse routes answer the same either way, except for what the author has
edited since the release: of that, a public repository shows nothing.
"""

import uuid
from typing import Any

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import cleanup
from _upstream_documents import set_visibility
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from test_repository_attachments import _copy, _stack, _table

from lorenzo_api.models import (
    Entity,
    Item,
    RepositoryCopy,
    RepositoryRelease,
    RepositoryReleaseDocument,
    StatGroup,
)


async def _edit(world: ReleaseWorld) -> None:
    """What the author does after a release: renames Dagger, adds Spear and a stat group."""
    async with admin_session_factory() as session:
        (await session.get_one(Entity, world.ids["Dagger"])).name = "Dirk"
        spear = Entity(tenant_id=world.repository, name="Spear")
        session.add_all([spear, StatGroup(tenant_id=world.repository, name="Combat", priority=5)])
        await session.flush()
        session.add(Item(entity_id=spear.id, tenant_id=world.repository))
        await session.commit()


async def _get(world: ReleaseWorld, path: str) -> Any:
    response = await world.gm.get(f"/tenants/{world.table}/repositories/{world.repository}/{path}")
    assert response.status_code == 200, response.text
    return response.json()


async def _names(world: ReleaseWorld) -> list[str]:
    return [e["name"] for e in (await _get(world, "entities"))["items"]]


async def _documents(repository: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return int(
            await session.scalar(
                select(func.count()).where(RepositoryReleaseDocument.tenant_id == repository)
            )
            or 0
        )


# --- Publishing writes the document of a public repository, and only of a public one ----------


async def test_a_public_repository_writes_a_document_at_each_release_and_a_private_one_none(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)  # release 1.0, private
    try:
        assert await _documents(world.repository) == 0

        await set_visibility([world.repository], "public")
        second = await world.publish(label="2.0")
        assert await _documents(world.repository) == 1
        async with admin_session_factory() as session:
            stored = await session.scalar(
                select(RepositoryReleaseDocument.release_id).where(
                    RepositoryReleaseDocument.tenant_id == world.repository
                )
            )
            assert str(stored) == second["id"]

        await set_visibility([world.repository], "private")
        await world.publish(label="3.0")
        assert await _documents(world.repository) == 1
    finally:
        await world.done()


# --- Reading: the release, not the rows --------------------------------------------------------


async def test_browsing_a_public_repository_shows_its_release_and_a_private_one_its_rows(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        await set_visibility([world.repository], "public")
        await world.publish(label="1.0")
        released = (await _get(world, "entities"))["items"]
        released_groups = await _get(world, "stat-groups")
        assert [e["name"] for e in released] == ["Dagger", "Longsword", "Orc"]

        await _edit(world)
        # Public: the edits are nobody's to see until the next release.
        assert await _names(world) == ["Dagger", "Longsword", "Orc"]
        assert await _get(world, "stat-groups") == released_groups

        await world.publish(label="2.0")
        assert await _names(world) == ["Dirk", "Longsword", "Orc", "Spear"]
        assert "Combat" in [g["name"] for g in await _get(world, "stat-groups")]

        # Private again: the rows, whatever the releases say.
        await set_visibility([world.repository], "private")
        async with admin_session_factory() as session:
            (await session.get_one(Entity, world.ids["Orc"])).name = "Goblin"
            await session.commit()
        assert await _names(world) == ["Dirk", "Goblin", "Longsword", "Spear"]
    finally:
        await world.done()


async def test_a_browse_of_a_document_answers_as_a_browse_of_the_rows(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        await world.publish(label="1.0")  # private: no document
        paths = [
            "entities",
            "entities?q=ORC",
            "entities?q=o",
            "entities?q=nothing",
            "entities?size=2",
            "entities?size=2&page=2",
            "stat-groups",
        ]
        from_rows = [await _get(world, p) for p in paths]
        assert from_rows[0]["total"] == 3
        assert [len(r["items"]) for r in from_rows[:6]] == [3, 1, 2, 0, 2, 1]
        assert [d["name"] for g in from_rows[6] for d in g["definitions"]] == [
            "Damage",
            "Mood",
            "Speed",
            "Strength",
        ]

        await set_visibility([world.repository], "public")
        await world.publish(label="2.0")
        assert [await _get(world, p) for p in paths] == from_rows
        # Kinds, parents and an enum's values are in it.
        entities = {e["name"]: e for e in from_rows[0]["items"]}
        assert entities["Orc"]["kinds"] == ["being"]
        assert entities["Dagger"]["prototype_ids"] == [str(world.ids["Longsword"])]
        mood = next(d for g in from_rows[6] for d in g["definitions"] if d["name"] == "Mood")
        assert sorted(mood["enum_values"]) == ["angry", "calm"]
    finally:
        await world.done()


async def test_the_plan_for_a_first_copy_is_the_release_of_a_public_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        await set_visibility([world.repository], "public")
        await world.publish(label="1.0")
        await _edit(world)

        plan = await _get(world, "copy-plan")
        assert [(s["entities"], s["stat_groups"]) for s in plan["steps"]] == [(3, 2)]

        await world.publish(label="2.0")
        plan = await _get(world, "copy-plan")
        assert [(s["entities"], s["stat_groups"]) for s in plan["steps"]] == [(4, 3)]
    finally:
        await world.done()


async def test_a_copy_of_a_public_repository_takes_the_release_and_records_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        await set_visibility([world.repository], "public")
        await world.publish(label="1.0")
        await _edit(world)
        await world.copy()

        async with admin_session_factory() as session:
            copied = set(
                await session.scalars(
                    select(Entity.name).where(
                        Entity.tenant_id == world.table,
                        Entity.name.in_(["Dagger", "Dirk", "Spear", "Longsword", "Orc"]),
                    )
                )
            )
            synced = await session.scalar(
                select(RepositoryCopy.synced_release_id).where(
                    RepositoryCopy.tenant_id == world.table
                )
            )
            release = await session.scalar(
                select(RepositoryRelease.id).where(
                    RepositoryRelease.tenant_id == world.repository,
                    RepositoryRelease.label == "1.0",
                )
            )
        assert copied == {"Dagger", "Longsword", "Orc"}
        assert synced == release
    finally:
        await world.done()


async def test_the_updates_of_a_public_repository_are_those_of_its_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server, copied=True)  # 1.0, taken
    try:
        await set_visibility([world.repository], "public")
        await world.publish(label="1.1")  # nothing changed
        await _edit(world)

        updates = await _get(world, "updates")
        assert (len(updates["changed"]), len(updates["added"]), len(updates["removed"])) == (
            0,
            0,
            0,
        )
        assert updates["release"]["label"] == "1.1"

        await world.publish(label="2.0")
        updates = await _get(world, "updates")
        assert [c["name"] for c in updates["changed"]] == ["Dagger"]
        assert sorted(a["name"] for a in updates["added"]) == ["Combat", "Spear"]
        assert updates["release"]["label"] == "2.0"
    finally:
        await world.done()


# --- The manifest: what a public repository is built on is what its release was built on ------


async def test_a_public_bridge_is_built_on_what_its_release_was_built_on(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm, table = await _table(raw_client, fake_jwks_server, stack, "gm")

    async def steps() -> list[str]:
        response = await gm.get(f"/tenants/{table}/repositories/{stack.bridge}/copy-plan")
        assert response.status_code == 200, response.text
        return [s["name"] for s in response.json()["steps"]]

    try:
        built = ["Common Equipment", "D&D 5e", "D&D Equipment"]
        assert await steps() == built

        await set_visibility([stack.equipment, stack.rules, stack.bridge], "public")
        for repository in (stack.equipment, stack.rules, stack.bridge):
            response = await stack.author.put(f"/tenants/{repository}/published", json={})
            assert response.status_code == 200, response.text
        assert await steps() == built

        # The bridge's own copy records change after the release: a public bridge is still
        # built on what it was built on at the release, a private one on what it is built on now.
        async with admin_session_factory() as session:
            await session.execute(
                delete(RepositoryCopy).where(
                    RepositoryCopy.tenant_id == stack.bridge,
                    RepositoryCopy.repository_tenant_id == stack.rules,
                )
            )
            await session.commit()
        assert await steps() == built
        await set_visibility([stack.bridge], "private")
        assert await steps() == ["Common Equipment", "D&D Equipment"]

        # And the whole stack copies, from the documents.
        await set_visibility([stack.bridge], "public")
        await _copy(gm, table, stack.bridge)
    finally:
        await cleanup(stack.tenants, stack.actors)


# --- A public repository with nothing to read ---------------------------------------------------


async def test_a_public_repository_without_a_release_is_a_conflict_and_not_a_live_read(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)  # release 1.0, no document
    try:
        await set_visibility([world.repository], "public")
        for path in ("entities", "stat-groups", "copy-plan"):
            response = await world.gm.get(
                f"/tenants/{world.table}/repositories/{world.repository}/{path}"
            )
            assert response.status_code == 409, (path, response.text)
            assert response.json()["type"].endswith("public-repository-has-no-release")
        copied = await world.gm.post(
            f"/tenants/{world.table}/repositories/{world.repository}/copy", json={}
        )
        assert copied.status_code == 409

        # No release at all is the same.
        async with admin_session_factory() as session:
            await session.execute(
                delete(RepositoryRelease).where(RepositoryRelease.tenant_id == world.repository)
            )
            await session.commit()
        response = await world.gm.get(
            f"/tenants/{world.table}/repositories/{world.repository}/entities"
        )
        assert response.status_code == 409

        # Released, it reads.
        await world.publish(label="2.0")
        assert await _names(world) == ["Dagger", "Longsword", "Orc"]
    finally:
        await world.done()


async def test_what_a_library_cannot_read_stays_unread_when_the_repository_is_private(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The read switch changes what is read and not who may read it (ADR 0286): a library with
    no grant gets the 404 it got, whatever documents the repository holds. A public repository is
    another matter, and ADR 0287's."""
    world = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        await set_visibility([world.repository], "public")
        await world.publish(label="1.0")
        await set_visibility([world.repository], "private")
        stranger = await world.gm.create_tenant("Stranger")
        world.tenants.append(stranger)
        for path in ("entities", "stat-groups", "copy-plan", "dependencies"):
            response = await world.gm.get(
                f"/tenants/{stranger}/repositories/{world.repository}/{path}"
            )
            assert response.status_code == 404, (path, response.text)
    finally:
        await world.done()
