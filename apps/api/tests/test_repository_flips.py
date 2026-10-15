"""ADR 0289: the rules that hold when a repository goes between private and public, and the
bridge-skew gate on publishing a public one. The flips are functions of a session until the routes
of RFC 0038's D5 call them, so they are called here as the Owner of the repository, as the
restricted app role, with RLS in force; publishing and reading go through the HTTP API.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import Actor, cleanup, make_actor
from _upstream_documents import in_tenant, set_visibility
from httpx import AsyncClient
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from test_repository_attachments import _share, _stack

from lorenzo_api.db import async_session_factory
from lorenzo_api.exceptions import (
    BuiltOnBehindError,
    BuiltOnNotPublicError,
    PublicCopiesWouldBeCutOffError,
    PublicRepositoriesBuiltOnItError,
    RepositoryAlreadyPrivateError,
    RepositoryAlreadyPublicError,
)
from lorenzo_api.models import (
    Membership,
    RepositoryCopy,
    RepositoryProfile,
    RepositoryRelease,
    RepositoryReleaseDocument,
    RepositorySubscription,
    Tenant,
    TenantKind,
)
from lorenzo_api.release_fanout import drain
from lorenzo_api.repository_built_on import built_on_behind, public_dependents
from lorenzo_api.repository_flips import make_private, make_public
from lorenzo_api.schemas.repositories import PublishRequest


@asynccontextmanager
async def _owner(repository: uuid.UUID, user_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """A request of the Owner of `repository`: its tenant context and the user's."""
    async with async_session_factory() as session:
        await in_tenant(session, repository)
        await session.execute(
            text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)}
        )
        yield session


async def _flip_public(owner: Actor, repository: uuid.UUID, **body: Any) -> uuid.UUID:
    """`make_public` as the Owner, committed; the id of the release it made."""
    async with _owner(repository, owner.user_id) as session:
        tenant = await session.get_one(Tenant, repository)
        published = await make_public(
            session, repository=tenant, user_id=owner.user_id, body=PublishRequest(**body)
        )
        release_id = published.release.id
        await session.commit()
    return release_id


async def _visibility(repository: uuid.UUID) -> str:
    async with admin_session_factory() as session:
        return str(
            await session.scalar(
                select(RepositoryProfile.visibility).where(
                    RepositoryProfile.tenant_id == repository
                )
            )
        )


async def _count(model: Any, repository: uuid.UUID) -> int:
    async with admin_session_factory() as session:
        return int(
            await session.scalar(select(func.count()).where(model.tenant_id == repository)) or 0
        )


async def _notices(actor: Actor) -> list[dict[str, Any]]:
    response = await actor.get("/me/notifications")
    assert response.status_code == 200, response.text
    return response.json()["items"]  # type: ignore[no-any-return]


async def _sync(owner: Actor, bridge: uuid.UUID, *upstreams: uuid.UUID) -> None:
    """The bridge takes each upstream's current release (nothing in it to apply)."""
    for upstream in upstreams:
        response = await owner.post(
            f"/tenants/{bridge}/repositories/{upstream}/updates", json={"actions": []}
        )
        assert response.status_code == 200, response.text


# --- Making a repository public ----------------------------------------------------------------


async def test_making_a_repository_public_is_one_action_with_its_first_public_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)  # granted to a library, 1.0, private
    try:
        assert await _visibility(world.repository) == "private"
        told = len(await _notices(world.gm))

        release = await _flip_public(world.author, world.repository, label="2.0")

        assert await _visibility(world.repository) == "public"
        releases = {r["label"]: r for r in await world.releases()}
        assert releases["2.0"]["id"] == str(release)
        assert (releases["2.0"]["current"], releases["2.0"]["kept"]) == (True, True)
        assert releases["1.0"]["kept"] is False  # made while private: no document
        assert await _count(RepositoryReleaseDocument, world.repository) == 1
        # The library that read it live reads the release now, and was told what that means.
        names = await world.gm.get(
            f"/tenants/{world.table}/repositories/{world.repository}/entities"
        )
        assert [e["name"] for e in names.json()["items"]] == ["Dagger", "Longsword", "Orc"]
        # Called as a function, so no response to hint a drain: the announcement is drained here.
        await drain()
        notices = await _notices(world.gm)
        assert len(notices) == told + 1
        assert "release 2.0" in notices[0]["title"]
        assert "It is now public" in notices[0]["body"]
    finally:
        await world.done()


async def test_a_repository_that_is_already_public_cannot_be_made_public_again(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        await _flip_public(world.author, world.repository)
        with pytest.raises(RepositoryAlreadyPublicError):
            await _flip_public(world.author, world.repository)
        assert await _count(RepositoryRelease, world.repository) == 2
    finally:
        await world.done()


async def test_a_repository_built_on_a_private_one_is_not_made_public_and_nothing_is_written(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        await set_visibility([stack.equipment], "public")
        releases = await _count(RepositoryRelease, stack.bridge)
        # The Owner of the bridge no longer owns the rules, only the equipment.
        async with admin_session_factory() as session:
            await session.execute(
                delete(Membership).where(
                    Membership.tenant_id == stack.rules,
                    Membership.user_id == stack.author.user_id,
                )
            )
            await session.commit()

        with pytest.raises(BuiltOnNotPublicError) as refused:
            await _flip_public(stack.author, stack.bridge)

        assert refused.value.extras["repositories"] == [
            {"id": str(stack.rules), "name": "D&D 5e", "owned": False}
        ]
        assert await _visibility(stack.bridge) == "private"
        assert await _count(RepositoryRelease, stack.bridge) == releases
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_a_stack_is_made_public_upstream_first_and_the_bridge_must_catch_up(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        await _flip_public(stack.author, stack.equipment)
        await _flip_public(stack.author, stack.rules)

        # Each upstream made a release of its own as it went public, and the bridge took the
        # releases before: a library copying the bridge would get rows made against the older
        # ones. The whole flip is refused, the visibility with it.
        with pytest.raises(BuiltOnBehindError) as refused:
            await _flip_public(stack.author, stack.bridge)
        assert [r["name"] for r in refused.value.extras["repositories"]] == [
            "Common Equipment",
            "D&D 5e",
        ]
        assert await _visibility(stack.bridge) == "private"
        assert await _count(RepositoryReleaseDocument, stack.bridge) == 0

        await _sync(stack.author, stack.bridge, stack.equipment, stack.rules)
        await _flip_public(stack.author, stack.bridge)
        assert await _visibility(stack.bridge) == "public"
        assert await _count(RepositoryReleaseDocument, stack.bridge) == 1
    finally:
        await cleanup(stack.tenants, stack.actors)


# --- The bridge-skew gate -----------------------------------------------------------------------


async def test_a_public_bridge_cannot_publish_while_a_repository_it_is_built_on_moved_on(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        await set_visibility([stack.equipment, stack.rules, stack.bridge], "public")
        for repository in (stack.equipment, stack.rules):
            assert (
                await stack.author.put(f"/tenants/{repository}/published", json={})
            ).status_code == 200
        await _sync(stack.author, stack.bridge, stack.equipment, stack.rules)
        assert (
            await stack.author.put(f"/tenants/{stack.bridge}/published", json={})
        ).status_code == 200

        # The equipment releases again.
        assert (
            await stack.author.put(f"/tenants/{stack.equipment}/published", json={})
        ).status_code == 200

        preview = await stack.author.get(f"/tenants/{stack.bridge}/release-preview")
        assert preview.json()["built_on_blocks_publish"] is True
        assert [b["name"] for b in preview.json()["built_on_behind"]] == ["Common Equipment"]

        refused = await stack.author.put(f"/tenants/{stack.bridge}/published", json={})
        assert refused.status_code == 409, refused.text
        problem = refused.json()
        assert problem["type"].endswith("built-on-behind")
        behind = problem["repositories"][0]
        assert behind["name"] == "Common Equipment"
        assert (behind["taken"]["label"], behind["current"]["label"]) == ("2", "3")
        assert await _count(RepositoryRelease, stack.bridge) == 2

        await _sync(stack.author, stack.bridge, stack.equipment)
        assert (
            await stack.author.put(f"/tenants/{stack.bridge}/published", json={})
        ).status_code == 200
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_a_private_bridge_is_warned_and_not_stopped(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        assert (
            await stack.author.put(f"/tenants/{stack.equipment}/published", json={})
        ).status_code == 200
        preview = (await stack.author.get(f"/tenants/{stack.bridge}/release-preview")).json()
        assert preview["built_on_blocks_publish"] is False
        assert [b["name"] for b in preview["built_on_behind"]] == ["Common Equipment"]
        assert (
            await stack.author.put(f"/tenants/{stack.bridge}/published", json={})
        ).status_code == 200
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_a_repository_built_on_something_it_cannot_read_is_behind() -> None:
    """Unpublished, or no longer granted: nothing can be told, and a library could not copy it."""
    async with admin_session_factory() as session:
        upstream = Tenant(name="Upstream", kind=TenantKind.REPOSITORY)
        bridge = Tenant(name="Bridge", kind=TenantKind.REPOSITORY)
        session.add_all([upstream, bridge])
        await session.flush()
        session.add(RepositoryCopy(tenant_id=bridge.id, repository_tenant_id=upstream.id))
        await session.commit()
        upstream_id, bridge_id = upstream.id, bridge.id
    try:
        async with _owner(bridge_id, uuid.uuid4()) as session:
            behind = await built_on_behind(session, bridge_id)
        assert [(b.name, b.readable) for b in behind] == [("Upstream", False)]
    finally:
        async with admin_session_factory() as session:
            await session.execute(delete(Tenant).where(Tenant.id.in_([upstream_id, bridge_id])))
            await session.commit()


# --- Making a repository private ----------------------------------------------------------------


async def _public_world(raw_client: AsyncClient, jwks: FakeJwksServer) -> ReleaseWorld:
    """A public repository, and its library holding a grant of its own from copying it, as well
    as a second library the Owner invited."""
    world = await release_world(raw_client, jwks, published=False)
    async with admin_session_factory() as session:
        await session.execute(
            delete(RepositorySubscription).where(
                RepositorySubscription.repository_tenant_id == world.repository
            )
        )
        await session.commit()
    await _flip_public(world.author, world.repository, label="1.0")
    await world.copy()  # the library's own grant, source public
    return world


async def _sources(repository: uuid.UUID) -> dict[uuid.UUID, str]:
    async with admin_session_factory() as session:
        return {
            s: source
            for s, source in await session.execute(
                select(
                    RepositorySubscription.subscriber_tenant_id, RepositorySubscription.source
                ).where(RepositorySubscription.repository_tenant_id == repository)
            )
        }


async def test_making_a_repository_private_revokes_the_grants_libraries_gave_themselves(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    invited = await make_actor(raw_client, fake_jwks_server, "invited")
    library = await invited.create_tenant("Invited table")
    world.tenants.append(library)
    world.actors.append(invited)
    try:
        await _share(world.author, world.repository, library)
        assert await _sources(world.repository) == {world.table: "public", library: "invited"}

        # Told how many, and nothing changes until the Owner says so.
        async with _owner(world.repository, world.author.user_id) as session:
            tenant = await session.get_one(Tenant, world.repository)
            with pytest.raises(PublicCopiesWouldBeCutOffError) as warned:
                await make_private(
                    session,
                    repository=tenant,
                    user_id=world.author.user_id,
                    acknowledge_revokes=False,
                )
        assert warned.value.extras["libraries"] == 1
        assert await _visibility(world.repository) == "public"

        told = len(await _notices(world.gm))
        async with _owner(world.repository, world.author.user_id) as session:
            tenant = await session.get_one(Tenant, world.repository)
            made = await make_private(
                session, repository=tenant, user_id=world.author.user_id, acknowledge_revokes=True
            )
            await session.commit()

        assert made.revoked == 1
        assert await _visibility(world.repository) == "private"
        # The invitation stays and reads it live again; the library that copied it is cut off,
        # keeps what it copied, and was told.
        assert await _sources(world.repository) == {library: "invited"}
        assert (
            await invited.get(f"/tenants/{library}/repositories/{world.repository}/entities")
        ).status_code == 200
        gone = await world.gm.get(
            f"/tenants/{world.table}/repositories/{world.repository}/entities"
        )
        assert gone.status_code == 404
        listed = await world.gm.get(f"/tenants/{world.table}/repositories")
        assert [
            (r["repository"]["id"], r["granted_at"], r["copied_at"] is not None)
            for r in listed.json()["items"]
        ] == [(str(world.repository), None, True)]
        # Called as a function, so no response to hint a drain: the announcement is drained here.
        await drain()
        notices = await _notices(world.gm)
        assert len(notices) == told + 1
        assert notices[0]["type"] == "repository_revoked"
        # Its documents are kept under retention, and nothing reads them: the release it went
        # public with, and the one the invitation published.
        assert await _count(RepositoryReleaseDocument, world.repository) == 2
    finally:
        await world.done()
        await cleanup([], [invited])


async def test_a_repository_with_no_public_copies_is_made_private_without_asking(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        await _flip_public(world.author, world.repository)
        async with _owner(world.repository, world.author.user_id) as session:
            tenant = await session.get_one(Tenant, world.repository)
            made = await make_private(
                session, repository=tenant, user_id=world.author.user_id, acknowledge_revokes=False
            )
            await session.commit()
        assert made.revoked == 0
        assert await _visibility(world.repository) == "private"
        async with _owner(world.repository, world.author.user_id) as session:
            tenant = await session.get_one(Tenant, world.repository)
            with pytest.raises(RepositoryAlreadyPrivateError):
                await make_private(
                    session,
                    repository=tenant,
                    user_id=world.author.user_id,
                    acknowledge_revokes=True,
                )
    finally:
        await world.done()


async def test_a_repository_a_public_one_is_built_on_cannot_be_made_private(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        await set_visibility([stack.equipment, stack.rules, stack.bridge], "public")
        for repository in (stack.equipment, stack.rules, stack.bridge):
            await stack.author.put(f"/tenants/{repository}/published", json={})

        async with _owner(stack.equipment, stack.author.user_id) as session:
            assert [d["name"] for d in await public_dependents(session, stack.equipment)] == [
                "D&D Equipment"
            ]
            tenant = await session.get_one(Tenant, stack.equipment)
            with pytest.raises(PublicRepositoriesBuiltOnItError) as refused:
                await make_private(
                    session,
                    repository=tenant,
                    user_id=stack.author.user_id,
                    acknowledge_revokes=True,
                )
        assert [d["name"] for d in refused.value.extras["repositories"]] == ["D&D Equipment"]
        assert await _visibility(stack.equipment) == "public"

        # The dependent goes private first, and then the equipment may.
        await set_visibility([stack.bridge], "private")
        async with _owner(stack.equipment, stack.author.user_id) as session:
            tenant = await session.get_one(Tenant, stack.equipment)
            await make_private(
                session, repository=tenant, user_id=stack.author.user_id, acknowledge_revokes=True
            )
            await session.commit()
        assert await _visibility(stack.equipment) == "private"
    finally:
        await cleanup(stack.tenants, stack.actors)
