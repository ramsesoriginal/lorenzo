"""ADR 0433, RFC 0051 H3: a protected repository.

A is the Armoury of the release tests, made protected by its Owner. B is a bridge that copied it
and is made public over it, which the stack rule allows because a protected repository is reached.
A library copies B and gets A as a step of that copy; it never reads A alone and never copies it
alone, and what it holds of A ends with the last public repository it holds that lists it.
Every flip, release, copy and update goes through the HTTP API; the delisting and the retiring are
written straight in the database, which their own tests cover as routes.
"""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import release_world
from _repository_actors import Actor, make_actor
from httpx import AsyncClient
from sqlalchemy import func, select, update
from test_repository_include import W, _bridge, _copy, _entries, _include, _library, _make_public

from lorenzo_api.config import get_settings
from lorenzo_api.models import (
    Entity,
    Item,
    RepositoryCopy,
    RepositoryProfile,
    RepositorySubscription,
    Tenant,
)
from lorenzo_api.repository_reach import PROTECTED_NAME


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def _protect(actor: Actor, repository: uuid.UUID, **body: Any) -> Any:
    return await actor.put(f"/tenants/{repository}/protected", json=body)


async def _world(raw_client: AsyncClient, jwks: FakeJwksServer, *, public_b: bool = True) -> W:
    """A is protected (and has made its release), B copied it and is public over it."""
    base = await release_world(raw_client, jwks)
    protected = await _protect(base.author, base.repository, label="p1")
    assert protected.status_code == 200, protected.text
    b, ids = await _bridge(base, "Bridge")
    w = W(base, b, ids)
    if public_b:
        made = await _make_public(base.author, b)
        assert made.status_code == 200, made.text
    return w


async def _visitor(
    raw_client: AsyncClient, jwks: FakeJwksServer, w: W, name: str = "visitor"
) -> Actor:
    actor = await make_actor(raw_client, jwks, name, roles=())
    w.actors.append(actor)
    return actor


async def _subscription(library: uuid.UUID, repository: uuid.UUID) -> str | None:
    async with admin_session_factory() as session:
        row = await session.get(RepositorySubscription, (repository, library))
        return row.source if row else None


async def _closed(actor: Actor, urls: list[str]) -> list[int]:
    return [(await actor.get(url)).status_code for url in urls]


def _alone(repository: uuid.UUID) -> list[str]:
    """What a visitor may ask of a repository by its address."""
    base = f"/repositories/{repository}"
    return [
        f"{base}/profile",
        f"{base}/profile/cover",
        f"{base}/releases",
        f"{base}/entities",
        f"{base}/stat-groups",
        f"{base}/dependencies",
        f"{base}/preview",
        f"/discover/repositories/{repository}",
    ]


# --- The flips ----------------------------------------------------------------------------------


async def test_private_to_protected_is_atomic_with_the_first_release_and_needs_nothing_else(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server, published=False)
    try:
        check = (await base.author.get(f"/tenants/{base.repository}/flip-check")).json()
        assert check["visibility"] == "private" and check["has_summary"] is False
        # No summary, no terms line, no preview: nothing says what it is to anybody who does not
        # hold it.
        done = await _protect(base.author, base.repository, label="1.0")
        assert done.status_code == 200, done.text
        assert done.json()["release"]["label"] == "1.0" and done.json()["turned"] == 0
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, base.repository)
            tenant = await session.get_one(Tenant, base.repository)
            assert (profile.visibility, profile.release_label, profile.listed) == (
                "protected",
                "1.0",
                True,
            )
            assert tenant.published_at is not None
            # It reaches nothing but itself: it is protected, so no library goes through it.
            assert (tenant.released_public, tenant.released_over) == (False, [])
        assert (await _protect(base.author, base.repository)).json()["type"] == (
            "repository-already-protected"
        )
        # A member who is not an Owner cannot.
        assert (await _protect(base.gm, base.repository)).status_code in (403, 404)
        assert (await base.author.get(f"/tenants/{base.repository}/profile")).json()[
            "visibility"
        ] == "protected"
    finally:
        await base.done()


async def test_a_refused_first_release_leaves_the_repository_private(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """It is protected together with its release or not at all: a repository built on one that is
    not reached is refused, and nothing is kept."""
    base = await release_world(raw_client, fake_jwks_server)
    try:
        b, _ = await _bridge(base, "Bridge")
        refused = await _protect(base.author, b)
        assert refused.status_code == 409
        assert refused.json()["type"] == "built-on-not-public"
        assert [r["name"] for r in refused.json()["repositories"]] == ["Armoury"]
        async with admin_session_factory() as session:
            assert (await session.get_one(RepositoryProfile, b)).visibility == "private"
        # Including it is the other way, as for a public repository.
        assert (await _include(base.author, b, base.repository)).status_code == 200
        assert (await _protect(base.author, b)).status_code == 200
        await base.author.delete(f"/tenants/{b}/public")
        base.tenants.append(b)
    finally:
        await base.done()


async def test_the_flips_between_the_three_and_what_each_does(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server, public_b=False)
    try:
        a = w.a
        # Protected to public needs the summary and the terms line, as private to public does, and
        # makes a release of its own.
        refused = await w.author.put(f"/tenants/{a}/public", json={"summary": "Every blade"})
        assert refused.json()["type"] == "terms-not-accepted"
        public = await _make_public(w.author, a, label="2.0")
        assert public.status_code == 200, public.text
        async with admin_session_factory() as session:
            assert (await session.get_one(RepositoryProfile, a)).visibility == "public"
        storefront = await w.author.get(f"/discover/repositories/{a}")
        assert storefront.status_code == 200

        # The Owner leaves it off Discover, and a library copies it by itself: a `public` grant.
        assert (
            await w.author.patch(f"/tenants/{a}/profile", json={"listed": False})
        ).status_code == 200
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, a)).status_code == 201
        assert await _subscription(library, a) == "public"

        # Public to protected: refused until the Owner says they know what the library loses.
        cut = await _protect(w.author, a)
        assert cut.status_code == 409
        assert (
            cut.json()["type"] == "public-copies-would-be-cut-off" and cut.json()["libraries"] == 1
        )
        done = await _protect(w.author, a, acknowledge_revokes=True)
        assert done.status_code == 200, done.text
        assert done.json()["release"] is None and done.json()["turned"] == 1
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, a)
            # No longer public, so no longer unlisted: the check of ADR 0432 holds.
            assert (profile.visibility, profile.listed) == ("protected", True)
        # Ends Discover and the visitors' reads, and the library's grant reads nothing alone.
        visitor = await _visitor(raw_client, fake_jwks_server, w)
        assert set(await _closed(visitor, _alone(a))) == {404}
        assert await _subscription(library, a) == "protected"
        assert (
            await reader.get(f"/tenants/{library}/repositories/{a}/entities")
        ).status_code == 404
        copy_alone = await reader.get(f"/tenants/{library}/repositories/{a}/copy-plan")
        assert copy_alone.status_code == 409 and copy_alone.json()["type"] == "repository-protected"
        # The library was told, once.
        told = (await reader.get("/me/notifications")).json()["items"]
        assert [n["title"] for n in told if "no longer public" in n["title"]] == [
            "Armoury is no longer public"
        ]

        # Protected to private is allowed while nobody is built on it that shows it: B is, and is
        # not public here, but it is a copy of A, so nothing stops it; only a public or protected
        # repository does.
        assert (await w.author.delete(f"/tenants/{a}/public")).status_code == 200
        async with admin_session_factory() as session:
            assert (await session.get_one(RepositoryProfile, a)).visibility == "private"
            # The rows the library wrote for it went with it.
        assert await _subscription(library, a) is None
        assert (await w.author.delete(f"/tenants/{a}/public")).json()["type"] == (
            "repository-already-private"
        )
    finally:
        await w.done()


async def test_protected_to_private_is_refused_while_a_public_repository_shows_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        refused = await w.author.delete(f"/tenants/{w.a}/public")
        assert refused.status_code == 409
        assert refused.json()["type"] == "public-repositories-built-on-it"
        assert [r["name"] for r in refused.json()["repositories"]] == ["Bridge"]
        check = (await w.author.get(f"/tenants/{w.a}/flip-check")).json()
        assert [d["name"] for d in check["public_dependents"]] == ["Bridge"]
        assert check["visibility"] == "protected"
    finally:
        await w.done()


async def test_it_may_go_private_once_every_repository_built_on_it_includes_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server, public_b=False)
    try:
        assert (await _include(w.author, w.b, w.a)).status_code == 200
        assert (await _make_public(w.author, w.b)).status_code == 200
        async with admin_session_factory() as session:
            tenant = await session.get_one(Tenant, w.b)
            # An included source is not a dependency: its release does not list it.
            assert (tenant.released_public, tenant.released_over) == (True, [])
        done = await w.author.delete(f"/tenants/{w.a}/public")
        assert done.status_code == 200, done.text
        # B is public over A, which is private and which it includes: a library copies B and
        # never reads A.
        reader, library = await _library(raw_client, fake_jwks_server, w)
        copied = await _copy(reader, library, w.b)
        assert copied.status_code == 201, copied.text
        assert [s["name"] for s in copied.json()["steps"]] == ["Bridge"]
    finally:
        await w.done()


# --- Who reads it: every reader against every state -------------------------------------------


async def test_a_visitor_reads_nothing_of_a_protected_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        visitor = await _visitor(raw_client, fake_jwks_server, w)
        assert set(await _closed(visitor, _alone(w.a))) == {404}
        # The same as an id that is nobody's, and as a private repository.
        assert set(await _closed(visitor, _alone(uuid.uuid4()))) == {404}
        # B is open, and says nothing of A: its dependencies leave a protected one out, and it
        # includes nothing.
        assert (await visitor.get(f"/discover/repositories/{w.b}")).status_code == 200
        assert (await visitor.get(f"/repositories/{w.b}/dependencies")).json() == []
        assert (await visitor.get(f"/repositories/{w.b}/profile")).json()["includes"] == []
        discover = (await visitor.get("/discover/repositories", params={"q": "Armoury"})).json()
        assert [i["name"] for i in discover["items"]] == []
        listed = (await visitor.get("/discover/repositories", params={"q": "Bridge"})).json()
        assert [i["name"] for i in listed["items"]] == ["Bridge"]
        # No signed-in user with no library reads it as an operator either: ADR 0057 has no
        # God-mode read.
        operator = await make_actor(
            raw_client, fake_jwks_server, "operator", roles=("platform-operator",)
        )
        w.actors.append(operator)
        assert set(await _closed(operator, _alone(w.a))) == {404}
    finally:
        await w.done()


async def test_a_library_reads_it_only_as_a_step_of_the_copy_of_the_repository_that_lists_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, w)
        # Before it copies anything it reads nothing of A, and does not know it exists.
        assert (
            await reader.get(f"/tenants/{library}/repositories/{w.a}/copy-plan")
        ).status_code == 404
        assert (
            await reader.get(f"/tenants/{library}/repositories/{w.a}/entities")
        ).status_code == 404

        # The plan of B has A as a step: marked protected, readable, and not named.
        plan = (await reader.get(f"/tenants/{library}/repositories/{w.b}/copy-plan")).json()
        assert [(s["name"], s["protected"], s["public"]) for s in plan["steps"]] == [
            (PROTECTED_NAME, True, False),
            ("Bridge", False, True),
        ]
        assert plan["steps"][0]["entities"] == 3 and plan["steps"][0]["granted"] is False
        dependencies = (
            await reader.get(f"/tenants/{library}/repositories/{w.b}/dependencies")
        ).json()
        assert [(d["name"], d["protected"], d["published"]) for d in dependencies] == [
            (PROTECTED_NAME, True, True)
        ]

        copied = await _copy(reader, library, w.b)
        assert copied.status_code == 201, copied.text
        assert [s["name"] for s in copied.json()["steps"]] == [PROTECTED_NAME, "Bridge"]
        # Both are the library's: A's rows and B's own, in one action.
        assert await _entries(reader, library) == ["Bridge Blade", "Dagger", "Longsword", "Orc"]
        assert await _subscription(library, w.a) == "protected"
        assert await _subscription(library, w.b) == "public"
        async with admin_session_factory() as session:
            assert set(
                await session.scalars(
                    select(RepositoryCopy.repository_tenant_id).where(
                        RepositoryCopy.tenant_id == library
                    )
                )
            ) == {w.a, w.b}

        # It lists what it holds: A as a protected repository, with no name and no address, and a
        # note that it cannot be copied alone.
        held = {
            r["repository"]["id"]: r
            for r in (await reader.get(f"/tenants/{library}/repositories")).json()["items"]
        }
        assert held[str(w.a)]["protected"] is True
        assert held[str(w.a)]["repository"]["name"] == PROTECTED_NAME
        assert (
            held[str(w.a)]["repository"]["slug"] == ""
            and held[str(w.a)]["repository"]["description"] == ""
        )
        assert held[str(w.a)]["current_release"] is not None
        assert (
            held[str(w.b)]["protected"] is False
            and held[str(w.b)]["repository"]["name"] == "Bridge"
        )

        # Nothing else of it is read: not browsed, not its profile, not its releases, not copied.
        gone = [
            f"/tenants/{library}/repositories/{w.a}/{part}"
            for part in ("entities", "stat-groups", "profile", "releases", "preview")
        ]
        assert set(await _closed(reader, gone)) == {404}
        alone = await reader.get(f"/tenants/{library}/repositories/{w.a}/copy-plan")
        assert alone.status_code == 409 and alone.json()["type"] == "repository-protected"
        again = await _copy(reader, library, w.a)
        assert again.status_code == 409 and again.json()["type"] == "repository-protected"
        # A visitor in the same library reads nothing of it either.
        assert set(await _closed(reader, _alone(w.a))) == {404}
    finally:
        await w.done()


async def test_a_library_with_an_invitation_reads_it_as_a_private_one_and_does_not_copy_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        # The table of the world was invited to A, as its Owner does, before it was protected.
        table, gm = w.base.table, w.base.gm
        entities = await gm.get(f"/tenants/{table}/repositories/{w.a}/entities")
        assert entities.status_code == 200 and len(entities.json()["items"]) >= 3
        assert (await gm.get(f"/tenants/{table}/repositories/{w.a}/profile")).status_code == 200
        # Read through its release, not its rows: the same as the repository's current release.
        plan = await gm.get(f"/tenants/{table}/repositories/{w.a}/copy-plan")
        assert plan.status_code == 409 and plan.json()["type"] == "repository-protected"
        assert (await _copy(gm, table, w.a)).status_code == 409
        # And it has no `protected` row: the invitation is its grant.
        assert await _subscription(table, w.a) == "invited"
        # A visitor's route does not know the invitation.
        assert set(await _closed(gm, _alone(w.a))) == {404}
    finally:
        await w.done()


async def test_a_repository_built_on_it_copies_it_alone_with_the_invitation_of_its_owner(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The one head a protected repository has: a repository of its own that its Owner invited.
    Building on it takes the grant its Owner gives (RFC 0051, hard invariants): one who was not
    invited does not know it is there."""
    base = await release_world(raw_client, fake_jwks_server)
    try:
        assert (await _protect(base.author, base.repository, label="p1")).status_code == 200
        stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
        base.actors.append(stranger)
        mine = await stranger.create_tenant("Mine", kind="repository")
        base.tenants.append(mine)
        refused = await stranger.post(
            f"/tenants/{mine}/repositories/{base.repository}/copy", json={}
        )
        assert refused.status_code == 404
        assert (
            await base.author.put(f"/tenants/{base.repository}/subscribers/{mine}")
        ).status_code == 201
        allowed = await stranger.post(
            f"/tenants/{mine}/repositories/{base.repository}/copy", json={}
        )
        assert allowed.status_code == 201, allowed.text
        # A's own name is shown to the one it invited.
        assert [s["name"] for s in allowed.json()["steps"]] == ["Armoury"]
    finally:
        await base.done()


async def test_a_library_that_holds_it_through_nothing_reads_nothing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, w)
        other, other_library = await _library(raw_client, fake_jwks_server, w, "Other")
        assert (await _copy(reader, library, w.b)).status_code == 201
        # The second library holds nothing: not even the knowledge that A exists.
        for url in (
            f"/tenants/{other_library}/repositories/{w.a}/copy-plan",
            f"/tenants/{other_library}/repositories/{w.a}/updates",
            f"/tenants/{other_library}/repositories/{w.a}/entities",
        ):
            assert (await other.get(url)).status_code in (404, 409)
        assert (
            await other.get(f"/tenants/{other_library}/repositories/{w.a}/copy-plan")
        ).status_code == 404
        # A member of the first library who is not an Owner reads nothing more than the Owner.
        assert (
            await reader.get(f"/tenants/{library}/repositories/{w.a}/entities")
        ).status_code == 404
    finally:
        await w.done()


# --- States of the repository the library holds it through -------------------------------------


async def _delist(repository: uuid.UUID, *, on: bool) -> None:
    """The platform's operators take it off Discover (or list it again), written straight in the
    database: the routes have their own tests (ADR 0303)."""
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant)
            .where(Tenant.id == repository)
            .values(
                delisted_at=func.now() if on else None,
                delisted_by=None,
                delist_reason="Abusive" if on else None,
            )
        )
        await session.commit()


async def _closed_to_updates(reader: Actor, library: uuid.UUID, repository: uuid.UUID) -> int:
    return (await reader.get(f"/tenants/{library}/repositories/{repository}/updates")).status_code


async def test_a_library_reads_it_while_the_public_repository_is_open_not_once_delisted(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201
        assert await _closed_to_updates(reader, library, w.a) == 200
        assert await _closed_to_updates(reader, library, w.b) == 200

        await _delist(w.b, on=True)
        # B reads as unpublished, and so does what comes with it.
        assert await _closed_to_updates(reader, library, w.b) == 404
        assert await _closed_to_updates(reader, library, w.a) == 404
        # Its rows are the library's own, and A's release still reaches no one else.
        assert await _entries(reader, library) == ["Bridge Blade", "Dagger", "Longsword", "Orc"]

        await _delist(w.b, on=False)
        assert await _closed_to_updates(reader, library, w.a) == 200
    finally:
        await w.done()


async def test_a_library_keeps_reading_it_through_a_repository_its_owner_retired(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, w)
        other, other_library = await _library(raw_client, fake_jwks_server, w, "Other")
        assert (await _copy(reader, library, w.b)).status_code == 201
        retired = await w.author.put(f"/tenants/{w.b}/deprecation", json={"message": "Moved"})
        assert retired.status_code == 200, retired.text
        # The library that holds it keeps its updates, A's among them.
        assert await _closed_to_updates(reader, library, w.b) == 200
        assert await _closed_to_updates(reader, library, w.a) == 200
        # One that does not holds nothing to read it with, and A does not come with it: retired
        # closes the public branch, and a repository the library cannot read is not a step.
        refused = await _copy(other, other_library, w.b)
        assert refused.status_code == 404
        assert (
            await other.get(f"/tenants/{other_library}/repositories/{w.a}/copy-plan")
        ).status_code == 404

        # Retiring A itself: a library that holds it keeps it, and none copies it again.
        assert (
            await w.author.put(f"/tenants/{w.a}/deprecation", json={"message": "Old"})
        ).status_code == 200
        assert await _closed_to_updates(reader, library, w.a) == 200
        third, third_library = await _library(raw_client, fake_jwks_server, w, "Third")
        assert (await _copy(third, third_library, w.b)).status_code == 404
    finally:
        await w.done()


async def test_a_delisted_protected_repository_is_closed_to_the_library_that_holds_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201
        await _delist(w.a, on=True)
        assert await _closed_to_updates(reader, library, w.a) == 404
        # The invited table reads nothing of it either, as of any delisted repository.
        assert (
            await w.base.gm.get(f"/tenants/{w.base.table}/repositories/{w.a}/entities")
        ).status_code == 404
        # And B cannot release over it: it cannot be read, so B counts as behind.
        refused = await w.author.put(f"/tenants/{w.b}/published", json={"label": "9"})
        assert refused.status_code == 409 and refused.json()["type"] == "built-on-behind"
    finally:
        await w.done()


# --- The diamond, the release of A, the skew gate and the revocation ------------------------------


async def test_the_diamond_shares_one_set_of_the_protected_rows(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        c, c_ids = await _bridge(w.base, "Second", own="Second Blade")
        w.tenants.append(c)
        assert (await _make_public(w.author, c)).status_code == 200
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201
        second = await _copy(reader, library, c)
        assert second.status_code == 201, second.text
        # A was copied with the first; the second brings only its own.
        assert [s["name"] for s in second.json()["steps"]] == ["Second"]
        plan_before = sorted(await _entries(reader, library))
        assert plan_before == ["Bridge Blade", "Dagger", "Longsword", "Orc", "Second Blade"]
        # One set of A's rows, and the copy record of A is one.
        async with admin_session_factory() as session:
            records = list(
                await session.scalars(
                    select(RepositoryCopy.repository_tenant_id).where(
                        RepositoryCopy.tenant_id == library
                    )
                )
            )
        assert sorted(records, key=str) == sorted([w.a, w.b, c], key=str)

        # Either of them lists it, and it stays readable while one does.
        async with admin_session_factory() as session:
            assert (await session.get_one(Tenant, w.b)).released_over == [w.a]
            assert (await session.get_one(Tenant, c)).released_over == [w.a]
        assert (
            await w.author.put(f"/tenants/{w.b}/published", json={"label": "unchanged"})
        ).status_code == 200
        assert (
            await w.author.delete(f"/tenants/{w.b}/public", params={"acknowledge_revokes": True})
        ).status_code == 200
        assert await _closed_to_updates(reader, library, w.a) == 200
        assert await _subscription(library, w.a) == "protected"
        # The last one goes private: the row the library wrote for A goes with it, and it reads
        # nothing of A any more.
        assert (
            await w.author.delete(f"/tenants/{c}/public", params={"acknowledge_revokes": True})
        ).status_code == 200
        assert await _subscription(library, w.a) is None
        assert await _closed_to_updates(reader, library, w.a) == 404
        # What it copied stays its own.
        assert await _entries(reader, library) == plan_before
    finally:
        await w.done()


async def test_a_release_of_the_protected_repository_reaches_the_libraries_that_hold_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201
        before = (await reader.get("/me/notifications")).json()["items"]

        # A adds a Spear and releases: the library that holds it is told, and reads the update
        # through B, whose release lists it.
        async with admin_session_factory() as session:
            spear = Entity(tenant_id=w.a, name="Spear")
            session.add(spear)
            await session.flush()
            session.add(Item(entity_id=spear.id, tenant_id=w.a))
            await session.commit()
            spear_id = spear.id
        await w.base.publish(label="2.0")
        after = (await reader.get("/me/notifications")).json()["items"]
        assert len(after) == len(before) + 1
        updates = (await reader.get(f"/tenants/{library}/repositories/{w.a}/updates")).json()
        assert [(a["kind"], a["name"]) for a in updates["added"]] == [("entity", "Spear")]

        # The skew gate: B cannot release until it has taken A's release; and a release of B that
        # waits for it still lists A.
        refused = await w.author.put(f"/tenants/{w.b}/published", json={"label": "2.0"})
        assert refused.status_code == 409 and refused.json()["type"] == "built-on-behind"
        taken = await w.author.post(
            f"/tenants/{w.b}/repositories/{w.a}/updates",
            json={"actions": [{"kind": "entity", "source_id": str(spear_id), "action": "add"}]},
        )
        assert taken.status_code == 200, taken.text
        assert (
            await w.author.put(f"/tenants/{w.b}/published", json={"label": "2.0"})
        ).status_code == 200

        # The library takes A's update, and B's.
        applied = await reader.post(
            f"/tenants/{library}/repositories/{w.a}/updates",
            json={"actions": [{"kind": "entity", "source_id": str(spear_id), "action": "add"}]},
        )
        assert applied.status_code == 200, applied.text
        assert "Spear" in await _entries(reader, library)
        # Taking it did not name the repository: the copy records its name as it was copied.
        async with admin_session_factory() as session:
            copy = await session.get_one(RepositoryCopy, (library, w.a))
            assert copy.repository_name == PROTECTED_NAME
    finally:
        await w.done()


async def test_a_release_of_the_public_repository_that_drops_it_ends_the_way_to_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A release of B that no longer lists A (B includes it now: a breaking release) is the end of
    what libraries that only hold B read of A."""
    w = await _world(raw_client, fake_jwks_server)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201
        assert (await _include(w.author, w.b, w.a)).status_code == 200
        refused = await w.author.put(f"/tenants/{w.b}/published", json={"label": "2.0"})
        assert (
            refused.status_code == 409 and refused.json()["type"] == "release-has-breaking-changes"
        )
        done = await w.author.put(
            f"/tenants/{w.b}/published", json={"label": "2.0", "acknowledge_breaking": True}
        )
        assert done.status_code == 200, done.text
        async with admin_session_factory() as session:
            assert (await session.get_one(Tenant, w.b)).released_over == []
        assert await _closed_to_updates(reader, library, w.a) == 404
    finally:
        await w.done()


# --- The stack rule and A's terms ---------------------------------------------------------------


async def test_the_stack_rule_asks_for_a_source_that_is_reached(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    try:
        b, _ = await _bridge(base, "Bridge")
        base.tenants.append(b)
        refused = await _make_public(base.author, b)
        assert refused.status_code == 409 and refused.json()["type"] == "built-on-not-public"
        # Protected is reached; so is public; private, not included, is not.
        assert (await _protect(base.author, base.repository, label="p")).status_code == 200
        # A is a release ahead of B now: take it first.
        taken = await base.author.post(
            f"/tenants/{b}/repositories/{base.repository}/updates", json={"actions": []}
        )
        assert taken.status_code == 200, taken.text
        assert (await _make_public(base.author, b)).status_code == 200
        check = (await base.author.get(f"/tenants/{b}/flip-check")).json()
        assert check["built_on_not_public"] == []
        [source] = check["built_on"]
        assert (source["protected"], source["public"], source["may_be_shown"]) == (
            True,
            False,
            True,
        )
        assert source["showable"] == {"allowed": True, "by": "owner"}
    finally:
        await base.done()


async def test_a_repository_that_says_stay_hidden_leaves_include_for_the_ones_built_on_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    try:
        assert (await _protect(base.author, base.repository, label="p")).status_code == 200
        owner_b = await make_actor(raw_client, fake_jwks_server, "other-owner")
        base.actors.append(owner_b)
        b, _ = await _bridge(base, "Bridge", owner=owner_b)
        base.tenants.append(b)
        url = f"/tenants/{b}/repositories/{base.repository}/inclusion"

        # Terms: only a protected repository can say no, and only its Owner says it.
        shown = await base.author.patch(
            f"/tenants/{base.repository}/profile", json={"terms": {"may_be_shown": False}}
        )
        assert shown.status_code == 200, shown.text
        assert shown.json()["terms"] == {
            "may_be_included": True,
            "is_default": True,
            "may_be_shown": False,
            "may_be_shown_is_default": False,
        }
        assert (
            await base.gm.patch(
                f"/tenants/{base.repository}/profile", json={"terms": {"may_be_shown": True}}
            )
        ).status_code in (403, 404)

        # B's Owner may not keep A separate and visible, and is told what is left.
        refused = await owner_b.put(url, json={"inclusion": "show"})
        assert refused.status_code == 409 and refused.json()["type"] == "repository-not-showable"
        assert [r["name"] for r in refused.json()["repositories"]] == ["Armoury"]
        check = (await owner_b.get(f"/tenants/{b}/flip-check")).json()
        [source] = check["built_on"]
        assert source["showable"] == {"allowed": False, "by": None}
        assert source["includable"]["allowed"] is True and source["may_be_shown"] is False
        # B shows it, which is what it has until it chooses: a public release of it is refused,
        # whatever was chosen before the terms changed.
        released = await _make_public(owner_b, b)
        assert released.status_code == 409
        assert released.json()["type"] == "repository-not-showable"
        # Include is the way, and A's terms allow it.
        assert (await owner_b.put(url, json={"inclusion": "include"})).status_code == 200
        assert (await owner_b.put(url, json={"inclusion": "show"})).status_code == 409
        made = await _make_public(owner_b, b)
        assert made.status_code == 200, made.text

        # A's Owner is not held to what A said of others: it may keep its own A shown.
        mine, _ = await _bridge(base, "Mine", own="My Blade")
        base.tenants.append(mine)
        assert (
            await base.author.put(
                f"/tenants/{mine}/repositories/{base.repository}/inclusion",
                json={"inclusion": "show"},
            )
        ).status_code == 200

        # `null` is the default again: shown, and the others may.
        reset = await base.author.patch(
            f"/tenants/{base.repository}/profile", json={"terms": {"may_be_shown": None}}
        )
        assert reset.json()["terms"]["may_be_shown"] is True
        assert (await owner_b.put(url, json={"inclusion": "show"})).status_code == 200
    finally:
        await base.done()


async def test_only_a_protected_repository_can_say_it_may_not_be_shown(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    try:
        url = f"/tenants/{base.repository}/profile"
        # Private: a repository read by invitation, so there is no one to forbid it to.
        refused = await base.author.patch(url, json={"terms": {"may_be_shown": False}})
        assert refused.status_code == 409 and refused.json()["type"] == "repository-not-protected"
        # And nothing else in that request was kept.
        ok = await base.author.patch(url, json={"terms": {"may_be_shown": True}})
        assert ok.status_code == 200 and ok.json()["terms"]["may_be_shown"] is True
        # A word that is not a boolean is `422`.
        assert (
            await base.author.patch(url, json={"terms": {"may_be_shown": "maybe"}})
        ).status_code == 422
        # Protected, it can; public again, it reads as shown and keeps what it said.
        assert (await _protect(base.author, base.repository, label="p")).status_code == 200
        assert (await base.author.patch(url, json={"terms": {"may_be_shown": False}})).json()[
            "terms"
        ]["may_be_shown"] is False
        assert (await _make_public(base.author, base.repository, label="q")).status_code == 200
        profile = (await base.author.get(url)).json()
        assert profile["terms"]["may_be_shown"] is True
        assert profile["terms"]["may_be_shown_is_default"] is False
        # The terms are the members' to read: a visitor's profile has none.
        visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
        base.actors.append(visitor)
        assert "terms" not in (await visitor.get(f"/repositories/{base.repository}/profile")).json()
    finally:
        await base.done()


async def test_a_protected_repository_may_be_included_by_default_and_not_when_its_owner_says_no(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    try:
        assert (await _protect(base.author, base.repository, label="p")).status_code == 200
        profile = (await base.author.get(f"/tenants/{base.repository}/profile")).json()
        assert (
            profile["terms"]["may_be_included"] is True and profile["terms"]["is_default"] is True
        )
        owner_b = await make_actor(raw_client, fake_jwks_server, "other-owner")
        base.actors.append(owner_b)
        b, _ = await _bridge(base, "Bridge", owner=owner_b)
        base.tenants.append(b)
        assert (await _include(owner_b, b, base.repository)).status_code == 200
        assert (
            await base.author.patch(
                f"/tenants/{base.repository}/profile", json={"terms": {"may_be_included": False}}
            )
        ).status_code == 200
        refused = await _make_public(owner_b, b)
        assert refused.status_code == 409 and refused.json()["type"] == "repository-not-includable"
    finally:
        await base.done()
