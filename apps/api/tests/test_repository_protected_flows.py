"""ADR 0433: what the flips of a protected repository do to what libraries hold, and what its Owner
sees of them. The world is the one of test_repository_protected.
"""

import uuid

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import release_world
from _repository_actors import make_actor
from httpx import AsyncClient
from sqlalchemy import func, select, update
from test_repository_include import _copy, _entries, _include, _library, _make_public
from test_repository_protected import (
    _closed_to_updates,
    _delist,
    _protect,
    _subscription,
    _world,
)

from lorenzo_api.config import get_settings
from lorenzo_api.models import RepositoryCopy, RepositoryProfile, Tenant
from lorenzo_api.repository_reach import reach_of


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def test_a_repository_that_stops_being_a_way_to_a_protected_one_takes_the_rows_with_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A0 is protected; A is public over it; a library copies A and holds A0 through it. A becomes
    protected: it no longer lets a library read A0, and the row the library wrote for A0 goes."""
    w = await _world(raw_client, fake_jwks_server, public_b=False)
    try:
        # B is the one built on the protected repository; A0 is the world's. B goes public, and a
        # library copies it and holds A0 through it.
        assert (await _make_public(w.author, w.b)).status_code == 200
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201
        assert await _subscription(library, w.a) == "protected"
        assert await _closed_to_updates(reader, library, w.a) == 200

        cut = await _protect(w.author, w.b)
        assert cut.status_code == 409 and cut.json()["type"] == "public-copies-would-be-cut-off"
        done = await _protect(w.author, w.b, acknowledge_revokes=True)
        assert done.status_code == 200, done.text
        async with admin_session_factory() as session:
            tenant = await session.get_one(Tenant, w.b)
            # It lists what it was built on and lets nobody through it.
            assert (tenant.released_public, tenant.released_over) == (False, [w.a])
        # The library keeps B as a repository it holds and A0 no more.
        assert await _subscription(library, w.a) is None
        assert await _subscription(library, w.b) == "protected"
        assert await _closed_to_updates(reader, library, w.a) == 404
        assert await _entries(reader, library) == ["Bridge Blade", "Dagger", "Longsword", "Orc"]

        # B is protected over a protected repository, which is reached; and public again, it lets
        # the library read A0 again, with a row of its own to list it.
        assert (await _make_public(w.author, w.b, label="again")).status_code == 200
        async with admin_session_factory() as session:
            assert (await session.get_one(Tenant, w.b)).released_public is True
        assert await _subscription(library, w.b) == "public"
        assert await _closed_to_updates(reader, library, w.a) == 200
    finally:
        await w.done()


async def test_the_owner_counts_the_libraries_that_hold_it_through_another(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201
        summary = (await w.author.get(f"/tenants/{w.a}/subscribers/summary")).json()
        # The world's table and B were invited and are named; the library that holds it through B is
        # counted and not named, as one that copied a public repository is (ADR 0299).
        assert summary == {"named": 2, "public_copies": 1}
        named = (await w.author.get(f"/tenants/{w.a}/subscribers")).json()["items"]
        assert sorted(s["name"] for s in named) == ["Bridge", "My Table"]
        # B shows in the dependents list of A as a repository that copied it and carries it `show`.
        assert {s["name"]: s["inclusion"] for s in named}["Bridge"] == "show"
        # And the library that A's Owner invites in the end stands as it did: an invitation
        # outranks the row the library wrote for itself, and the answer says nothing of it.
        invited = await w.author.put(f"/tenants/{w.a}/subscribers/{library}")
        assert invited.status_code == 201
        assert await _subscription(library, w.a) == "invited"
        assert await _closed_to_updates(reader, library, w.a) == 200
        # A library cannot give an invitation up as one it wrote itself, and its Owner can.
        assert (await w.author.delete(f"/tenants/{w.a}/subscribers/{library}")).status_code == 204
        assert await _subscription(library, w.a) is None
        # It reads A through B all the same: the rule is B's release, not the row.
        assert await _closed_to_updates(reader, library, w.a) == 200
    finally:
        await w.done()


async def test_a_repository_that_is_delisted_or_retired_cannot_be_made_protected(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    try:
        await _delist(base.repository, on=True)
        refused = await _protect(base.author, base.repository)
        assert refused.status_code == 409 and refused.json()["type"] == "repository-delisted"
        await _delist(base.repository, on=False)
        retired = await base.author.put(
            f"/tenants/{base.repository}/deprecation", json={"message": "Old"}
        )
        assert retired.status_code == 200, retired.text
        refused = await _protect(base.author, base.repository)
        assert refused.status_code == 409 and refused.json()["type"] == "repository-deprecated"
        # Nothing was kept of either.
        check = (await base.author.get(f"/tenants/{base.repository}/flip-check")).json()
        assert check["visibility"] == "private"
    finally:
        await base.done()


async def test_a_protected_repository_is_not_unpublished_and_its_release_is_made_as_ever(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server, public_b=False)
    try:
        refused = await w.author.delete(f"/tenants/{w.a}/published")
        assert refused.status_code == 409
        assert refused.json()["type"] == "public-repository-cannot-be-unpublished"
        # A release of it is a release of a document, and the profile says what it lists.
        released = await w.author.put(f"/tenants/{w.a}/published", json={"label": "p2"})
        assert released.status_code == 200, released.text
        profile = (await w.author.get(f"/tenants/{w.a}/profile")).json()
        assert (profile["visibility"], profile["listed"]) == ("protected", True)
        # And never on a visitor's profile, where a protected one is not.
        visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
        w.actors.append(visitor)
        assert (await visitor.get(f"/repositories/{w.a}/profile")).status_code == 404
        # Its Owner reads its releases as ever.
        releases = (await w.author.get(f"/tenants/{w.a}/releases")).json()["items"]
        assert releases[0]["label"] == "p2"
    finally:
        await w.done()


# --- What the tenant row keeps is what the profile says ------------------------------------------


async def _reach_is_the_profiles(repository: uuid.UUID) -> tuple[bool, list[uuid.UUID]]:
    """What `tenant` keeps of a repository's reach against what `reach_of` makes of its profile and
    its copy records: the two have to be the same after any step (the function reads the first)."""
    async with admin_session_factory() as session:
        tenant = await session.get_one(Tenant, repository)
        profile = await session.get_one(RepositoryProfile, repository)
        copied = list(
            await session.scalars(
                select(RepositoryCopy.repository_tenant_id).where(
                    RepositoryCopy.tenant_id == repository
                )
            )
        )
        over, public = reach_of(profile.visibility, profile.release_sources, copied)
        assert tenant.released_public is public
        assert sorted(tenant.released_over, key=str) == over
        return public, over


async def test_the_reach_on_the_tenant_row_follows_every_step_of_the_profile(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server, public_b=False)
    try:
        assert await _reach_is_the_profiles(w.b) == (False, [])
        assert (await _make_public(w.author, w.b)).status_code == 200
        assert await _reach_is_the_profiles(w.b) == (True, [w.a])
        assert (
            await w.author.put(f"/tenants/{w.b}/published", json={"label": "r2"})
        ).status_code == 200
        assert await _reach_is_the_profiles(w.b) == (True, [w.a])
        assert (await _protect(w.author, w.b, acknowledge_revokes=True)).status_code == 200
        assert await _reach_is_the_profiles(w.b) == (False, [w.a])
        assert (await _make_public(w.author, w.b, label="r3")).status_code == 200
        assert await _reach_is_the_profiles(w.b) == (True, [w.a])
        assert (await _include(w.author, w.b, w.a)).status_code == 200
        done = await w.author.put(
            f"/tenants/{w.b}/published", json={"label": "r4", "acknowledge_breaking": True}
        )
        assert done.status_code == 200, done.text
        assert await _reach_is_the_profiles(w.b) == (True, [])
        gone = await w.author.delete(f"/tenants/{w.b}/public", params={"acknowledge_revokes": True})
        assert gone.status_code == 200
        assert await _reach_is_the_profiles(w.b) == (False, [])
        # A repository that never made a public release reaches nothing, whatever it copied.
        assert await _reach_is_the_profiles(w.a) == (False, [])
    finally:
        await w.done()


def test_what_a_repository_reaches_by_what_it_is_and_what_its_release_listed() -> None:
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    recorded = [
        {"id": str(b), "inclusion": "show"},
        {"id": str(a), "inclusion": "include"},
        {"id": str(c), "inclusion": "show"},
    ]

    # A private repository reaches nothing; a protected one lists what it did not include and lets
    # nobody through; a public one lets through what it listed.
    assert reach_of("private", recorded, [a, b]) == ([], False)
    assert reach_of("protected", recorded, [a, b]) == (sorted([b, c], key=str), False)
    assert reach_of("public", recorded, [a, b]) == (sorted([b, c], key=str), True)
    # A release made before the record existed was built on what the repository had copied.
    assert reach_of("public", None, [b, a]) == (sorted([a, b], key=str), True)
    assert reach_of("public", [], [a]) == ([], True)


# --- Every reader against every state ------------------------------------------------------------


async def _state(repository: uuid.UUID, *, visibility: str, retired: bool, delisted: bool) -> None:
    """The repository's state, written straight in the database: every route that reads it is
    tested through its own flip elsewhere."""
    async with admin_session_factory() as session:
        await session.execute(
            update(RepositoryProfile)
            .where(RepositoryProfile.tenant_id == repository)
            .values(visibility=visibility)
        )
        await session.execute(
            update(Tenant)
            .where(Tenant.id == repository)
            .values(
                deprecated_at=func.now() if retired else None,
                delisted_at=func.now() if delisted else None,
                delist_reason="Abusive" if delisted else None,
            )
        )
        await session.commit()


# What each reader gets of A's profile (or, for a library that holds it through B, of its update
# check, since the browse of such a library is closed by design), by A's state: private, protected,
# public, protected and retired, protected and delisted, public and retired.
_MATRIX = {
    # state: (visitor, operator, invited library, library through B, member)
    ("private", False, False): (404, 404, 200, 404, 200),
    ("protected", False, False): (404, 404, 200, 200, 200),
    ("public", False, False): (200, 200, 200, 200, 200),
    ("protected", True, False): (404, 404, 200, 200, 200),
    ("protected", False, True): (404, 404, 404, 404, 200),
    # Written straight in the database, the library's row is still the `protected` one a flip would
    # have turned into a public grant, which a retired public repository does not read.
    ("public", True, False): (404, 404, 200, 404, 200),
    ("public", False, True): (404, 404, 404, 404, 200),
}


async def test_every_reader_against_every_state_of_a_protected_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _world(raw_client, fake_jwks_server)
    try:
        operator = await make_actor(
            raw_client, fake_jwks_server, "operator", roles=("platform-operator",)
        )
        visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
        w.actors.extend([operator, visitor])
        reader, library = await _library(raw_client, fake_jwks_server, w)
        assert (await _copy(reader, library, w.b)).status_code == 201
        table, gm = w.base.table, w.base.gm
        for (visibility, retired, delisted), expected in _MATRIX.items():
            await _state(w.a, visibility=visibility, retired=retired, delisted=delisted)
            got = (
                (await visitor.get(f"/repositories/{w.a}/profile")).status_code,
                (await operator.get(f"/repositories/{w.a}/profile")).status_code,
                (await gm.get(f"/tenants/{table}/repositories/{w.a}/profile")).status_code,
                await _closed_to_updates(reader, library, w.a),
                (await w.author.get(f"/tenants/{w.a}/profile")).status_code,
            )
            assert got == expected, (visibility, retired, delisted)
        # The same states for what a library copies: a plan of the public repository built on it
        # either reaches it as a step or does not, by the same rule.
        for (visibility, retired, delisted), reached in (
            (("protected", False, False), True),
            (("private", False, False), False),
            (("protected", False, True), False),
        ):
            await _state(w.a, visibility=visibility, retired=retired, delisted=delisted)
            other, other_library = await _library(raw_client, fake_jwks_server, w, "Plan")
            plan = await other.get(f"/tenants/{other_library}/repositories/{w.b}/copy-plan")
            assert plan.status_code == 200, (visibility, plan.text)
            [first, *_] = plan.json()["steps"]
            assert first["protected"] is reached, (visibility, retired, delisted)
    finally:
        await w.done()
