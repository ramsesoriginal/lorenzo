"""ADR 0287: what anyone signed in may read of a public repository, and what copying one does.

A repository is made public in the database, since the API refuses it until the rest of RFC
0038 is built; publishing makes its release, whose document is what is read (ADR 0286).
"""

import uuid

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import cleanup, make_actor
from _upstream_documents import publish_stack, set_visibility
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from test_repository_attachments import _share, _stack

from lorenzo_api.models import (
    Entity,
    Membership,
    MembershipRole,
    RepositoryCopy,
    RepositoryProfile,
    RepositorySubscription,
    Tenant,
)


async def _public_world(
    raw_client: AsyncClient, jwks: FakeJwksServer, *, granted: bool = False
) -> ReleaseWorld:
    """Armoury, public and released as 2.0, and a table of its own that holds no grant to it."""
    world = await release_world(raw_client, jwks, published=False)
    await set_visibility([world.repository], "public")
    await world.publish(label="2.0")
    if not granted:
        async with admin_session_factory() as session:
            await session.execute(
                delete(RepositorySubscription).where(
                    RepositorySubscription.repository_tenant_id == world.repository
                )
            )
            await session.commit()
    return world


async def _sources(repository: uuid.UUID, library: uuid.UUID) -> list[str]:
    async with admin_session_factory() as session:
        return list(
            await session.scalars(
                select(RepositorySubscription.source).where(
                    RepositorySubscription.repository_tenant_id == repository,
                    RepositorySubscription.subscriber_tenant_id == library,
                )
            )
        )


# --- Reading with no library ---------------------------------------------------------------


async def test_a_user_with_no_library_reads_a_public_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    try:
        await world.author.patch(
            f"/tenants/{world.repository}/profile", json={"summary": "Every blade there is"}
        )
        base = f"/repositories/{world.repository}"

        profile = (await visitor.get(f"{base}/profile")).json()
        assert profile["summary"] == "Every blade there is"
        assert profile["visibility"] == "public"

        releases = (await visitor.get(f"{base}/releases")).json()
        assert [r["label"] for r in releases["items"]] == ["2.0"]

        entities = (await visitor.get(f"{base}/entities")).json()
        assert [e["name"] for e in entities["items"]] == ["Dagger", "Longsword", "Orc"]
        found = (await visitor.get(f"{base}/entities", params={"q": "sword"})).json()
        assert [e["name"] for e in found["items"]] == ["Longsword"]

        groups = (await visitor.get(f"{base}/stat-groups")).json()
        assert [g["name"] for g in groups] == ["Abilities", "Extras"]

        assert (await visitor.get(f"{base}/dependencies")).json() == []
        # No cover was set: the repository is there and the picture is not. Then it is.
        missing = await visitor.get(f"{base}/profile/cover")
        assert missing.status_code == 404
        assert missing.json()["type"].endswith("profile-picture-not-found")
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 64
        uploaded = await world.author.put(
            f"/tenants/{world.repository}/profile/cover",
            files={"file": ("c.png", png, "image/png")},
        )
        assert uploaded.status_code in (200, 204), uploaded.text
        cover = await visitor.get(f"{base}/profile/cover")
        assert (cover.status_code, cover.content) == (200, png)
    finally:
        await world.done()
        await cleanup([], [visitor])


async def test_what_a_user_reads_is_the_release_and_not_what_the_author_edited_since(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    try:
        async with admin_session_factory() as session:
            (await session.get_one(Entity, world.ids["Dagger"])).name = "Dirk"
            await session.commit()
        entities = (await visitor.get(f"/repositories/{world.repository}/entities")).json()
        assert [e["name"] for e in entities["items"]] == ["Dagger", "Longsword", "Orc"]
    finally:
        await world.done()
        await cleanup([], [visitor])


@pytest.mark.parametrize("state", ["private", "draft", "missing"])
async def test_a_repository_that_is_not_public_is_not_found_for_anyone(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, state: str
) -> None:
    world = await _public_world(raw_client, fake_jwks_server, granted=True)
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    try:
        target = world.repository
        if state == "private":
            await set_visibility([world.repository], "private")
        elif state == "draft":
            async with admin_session_factory() as session:
                (await session.get_one(Tenant, world.repository)).published_at = None
                await session.commit()
        else:
            target = uuid.uuid4()
        for who in (visitor, world.gm):
            for path in ("profile", "profile/cover", "releases", "entities", "stat-groups"):
                response = await who.get(f"/repositories/{target}/{path}")
                assert response.status_code == 404, (path, response.text)
                assert response.json()["type"].endswith("repository-not-found"), path
            assert (await who.get(f"/repositories/{target}/dependencies")).status_code == 404
    finally:
        await world.done()
        await cleanup([], [visitor])


async def test_a_public_repository_with_no_release_says_so_and_still_shows_its_profile(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)  # 1.0 made while private
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    try:
        await set_visibility([world.repository], "public")
        base = f"/repositories/{world.repository}"
        assert (await visitor.get(f"{base}/profile")).status_code == 200
        for path in ("entities", "stat-groups"):
            response = await visitor.get(f"{base}/{path}")
            assert response.status_code == 409, path
            assert response.json()["type"].endswith("public-repository-has-no-release")
    finally:
        await world.done()
        await cleanup([], [visitor])


async def test_reading_needs_a_signed_in_user(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        for path in ("profile", "releases", "entities", "stat-groups", "dependencies"):
            response = await raw_client.get(f"/repositories/{world.repository}/{path}")
            assert response.status_code == 401, path
    finally:
        await world.done()


async def test_a_library_with_no_grant_reads_a_public_repository_through_its_own_routes(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        base = f"/tenants/{world.table}/repositories/{world.repository}"
        for path in ("profile", "releases", "entities", "stat-groups", "dependencies", "copy-plan"):
            response = await world.gm.get(f"{base}/{path}")
            assert response.status_code == 200, (path, response.text)
        plan = (await world.gm.get(f"{base}/copy-plan")).json()
        assert [(s["granted"], s["public"], s["published"]) for s in plan["steps"]] == [
            (False, True, True)
        ]
        # A private one is still not found for a library that was never granted it.
        await set_visibility([world.repository], "private")
        for path in ("profile", "entities", "copy-plan"):
            assert (await world.gm.get(f"{base}/{path}")).status_code == 404, path
    finally:
        await world.done()


# --- Copying ----------------------------------------------------------------------------------


async def test_copying_a_public_repository_gives_the_library_a_public_grant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        assert await _sources(world.repository, world.table) == []
        await world.copy()
        assert await _sources(world.repository, world.table) == ["public"]

        # From then on it is an ordinary subscription: listed, updated and given up like one.
        listed = (await world.gm.get(f"/tenants/{world.table}/repositories")).json()["items"]
        assert [(r["repository"]["id"], r["granted_at"] is not None) for r in listed] == [
            (str(world.repository), True)
        ]
        updates = await world.gm.get(
            f"/tenants/{world.table}/repositories/{world.repository}/updates"
        )
        assert updates.status_code == 200
        given_up = await world.gm.delete(f"/tenants/{world.table}/repositories/{world.repository}")
        assert given_up.status_code == 204
        assert await _sources(world.repository, world.table) == []
        async with admin_session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count()).where(
                        Entity.tenant_id == world.table, Entity.name == "Longsword"
                    )
                )
                == 1
            )
    finally:
        await world.done()


async def test_an_invitation_outranks_a_public_copy(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        await _share(world.author, world.repository, world.table)
        assert await _sources(world.repository, world.table) == ["invited"]
        await world.copy()
        assert await _sources(world.repository, world.table) == ["invited"]
    finally:
        await world.done()


async def test_a_dry_run_of_a_public_copy_writes_no_grant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        response = await world.gm.post(
            f"/tenants/{world.table}/repositories/{world.repository}/copy",
            json={"dry_run": True},
        )
        assert response.status_code == 200, response.text
        assert await _sources(world.repository, world.table) == []
    finally:
        await world.done()


async def test_an_author_may_not_copy_a_public_repository_into_a_library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    writer = await make_actor(raw_client, fake_jwks_server, "writer", roles=())
    try:
        async with admin_session_factory() as session:
            session.add(
                Membership(
                    tenant_id=world.table, user_id=writer.user_id, role=MembershipRole.AUTHOR
                )
            )
            await session.commit()
        response = await writer.post(
            f"/tenants/{world.table}/repositories/{world.repository}/copy", json={}
        )
        assert response.status_code == 403, response.text
        assert await _sources(world.repository, world.table) == []
    finally:
        await world.done()
        await cleanup([], [writer])


async def test_a_public_stack_copies_in_one_action_and_the_library_holds_a_grant_to_each(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await gm.create_tenant("A table with no invitation")
    stack.tenants.append(table)
    stack.actors.append(gm)
    repositories = (stack.equipment, stack.rules, stack.bridge)
    try:
        await set_visibility(repositories, "public")
        await publish_stack(stack)
        base = f"/tenants/{table}/repositories/{stack.bridge}"

        dependencies = (await gm.get(f"/repositories/{stack.bridge}/dependencies")).json()
        assert [(d["name"], d["public"]) for d in dependencies] == [
            ("Common Equipment", True),
            ("D&D 5e", True),
        ]
        plan = (await gm.get(f"{base}/copy-plan")).json()
        assert [(s["name"], s["granted"], s["public"]) for s in plan["steps"]] == [
            ("Common Equipment", False, True),
            ("D&D 5e", False, True),
            ("D&D Equipment", False, True),
        ]

        copied = await gm.post(f"{base}/copy", json={})
        assert copied.status_code == 201, copied.text
        assert [s["name"] for s in copied.json()["steps"]] == [
            "Common Equipment",
            "D&D 5e",
            "D&D Equipment",
        ]
        for repository in repositories:
            assert await _sources(repository, table) == ["public"]
        async with admin_session_factory() as session:
            assert (
                await session.scalar(select(func.count()).where(RepositoryCopy.tenant_id == table))
                == 3
            )
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_a_stack_with_a_private_repository_copies_nothing_and_grants_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await gm.create_tenant("A table with no invitation")
    stack.tenants.append(table)
    stack.actors.append(gm)
    try:
        await set_visibility([stack.equipment, stack.bridge], "public")
        await publish_stack(stack)
        base = f"/tenants/{table}/repositories/{stack.bridge}"

        dependencies = (await gm.get(f"/repositories/{stack.bridge}/dependencies")).json()
        assert [(d["name"], d["public"]) for d in dependencies] == [
            ("Common Equipment", True),
            ("D&D 5e", False),
        ]

        refused = await gm.post(f"{base}/copy", json={})
        assert refused.status_code == 409, refused.text
        assert refused.json()["type"].endswith("repository-copy-needs-grants")
        assert [m["name"] for m in refused.json()["missing"]] == ["D&D 5e"]
        async with admin_session_factory() as session:
            assert (
                await session.scalar(
                    select(func.count()).where(RepositorySubscription.subscriber_tenant_id == table)
                )
                == 0
            )
            assert await session.scalar(select(func.count()).where(Entity.tenant_id == table)) == 0

        # The Owner of the private one invites the library: the rest is public, the stack copies,
        # and only the public ones are the library's own grants.
        await _share(stack.author, stack.rules, table)
        assert (await gm.post(f"{base}/copy", json={})).status_code == 201
        assert await _sources(stack.rules, table) == ["invited"]
        assert await _sources(stack.equipment, table) == ["public"]
        assert await _sources(stack.bridge, table) == ["public"]
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_nothing_is_written_to_a_repository_by_being_read_or_copied(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The repository's own rows are never the writer's: reading and copying it leaves its
    profile and entries as they were."""
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        await world.copy()
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, world.repository)
            assert profile.visibility == "public"
            assert (
                await session.scalar(
                    select(func.count()).where(Entity.tenant_id == world.repository)
                )
                == 3
            )
    finally:
        await world.done()
