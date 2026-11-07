"""ADR 0432, RFC 0051 H2: a public repository whose Owner left it off Discover.

The repository is the one of the release tests (Armoury), made public through the flip route. What
is pinned: Discover's listing, its facets and its search leave an unlisted repository out; every
read by its address (the storefront, the `/repositories/{id}` reads, the preview) and a copy by
address work for any signed-in user, as for a listed one; only an Owner of a public repository
turns it off or on; a flip back to private puts the flag back; and the three statements of the
rule that says what is listed (the Python statement, the facets' SQL and the `discover_read`
policy) agree on every state a repository can be in.
"""

import itertools
import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _author_world import add_member
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import Actor, make_actor
from httpx import AsyncClient
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from test_public_repository_gate import _as

from lorenzo_api.config import get_settings
from lorenzo_api.dependencies import NO_TENANT
from lorenzo_api.discover import _LISTED_SQL, listed
from lorenzo_api.models import AuditLog, RepositoryProfile, Tenant, TenantKind
from lorenzo_api.repository_access import reading_repository


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def _public(raw_client: AsyncClient, jwks: FakeJwksServer) -> tuple[ReleaseWorld, str]:
    """Armoury, public with a name, a tag and a system of its own that no other repository in the
    database shares, so a listing or a facet shows only this one. Returns the world and the word."""
    word = uuid.uuid4().hex[:10]
    world = await release_world(raw_client, jwks)
    renamed = await world.author.patch(
        f"/tenants/{world.repository}",
        json={"name": f"Armoury {word}"},
    )
    assert renamed.status_code == 200, renamed.text
    profile = await world.author.patch(
        f"/tenants/{world.repository}/profile",
        json={"tags": [f"t{word}"], "system": f"s{word}", "languages": ["en"]},
    )
    assert profile.status_code == 200, profile.text
    flipped = await world.author.put(
        f"/tenants/{world.repository}/public",
        json={"accept_terms": True, "summary": f"Every blade {word}", "preview": "public"},
    )
    assert flipped.status_code == 200, flipped.text
    return world, word


async def _listing(visitor: Actor, word: str, **params: Any) -> list[str]:
    response = await visitor.get("/discover/repositories", params={"q": word} | params)
    assert response.status_code == 200, response.text
    return [i["id"] for i in response.json()["items"]]


async def _facets(visitor: Actor) -> dict[str, dict[str, int]]:
    response = await visitor.get("/discover/facets")
    assert response.status_code == 200, response.text
    body = response.json()
    return {
        key: {f["value"]: f["count"] for f in body[key]} for key in ("tags", "systems", "languages")
    }


async def _set_listed(actor: Actor, repository: uuid.UUID, value: Any) -> Any:
    return await actor.patch(f"/tenants/{repository}/profile", json={"listed": value})


async def _visitor(raw_client: AsyncClient, jwks: FakeJwksServer) -> Actor:
    return await make_actor(raw_client, jwks, "visitor", roles=())


# --- The default and the toggle ------------------------------------------------------------------


async def test_a_public_repository_is_listed_until_its_owner_leaves_it_off(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world, word = await _public(raw_client, fake_jwks_server)
    visitor = await _visitor(raw_client, fake_jwks_server)
    world.actors.append(visitor)
    repo = world.repository
    try:
        profile = (await world.author.get(f"/tenants/{repo}/profile")).json()
        assert profile["listed"] is True
        assert await _listing(visitor, word) == [str(repo)]
        facets = await _facets(visitor)
        assert facets["tags"][f"t{word}"] == 1 and facets["systems"][f"s{word}"] == 1

        off = await _set_listed(world.author, repo, False)
        assert off.status_code == 200, off.text
        assert off.json()["listed"] is False
        assert (await world.author.get(f"/tenants/{repo}/profile")).json()["listed"] is False
        # The visibility card reads it from the flip check.
        check = (await world.author.get(f"/tenants/{repo}/flip-check")).json()
        assert (check["visibility"], check["listed"]) == ("public", False)

        # Off Discover: the listing (by its word, its name, its tag, its system), the facets and
        # a page past it.
        assert await _listing(visitor, word) == []
        assert await _listing(visitor, word, tag=f"t{word}") == []
        assert await _listing(visitor, word, system=f"s{word}") == []
        assert await _listing(visitor, word, sort="released") == []
        assert str(repo) not in await _listing(visitor, "", size=50, sort="released")
        total = (await visitor.get("/discover/repositories", params={"q": word})).json()["total"]
        assert total == 0
        facets = await _facets(visitor)
        assert f"t{word}" not in facets["tags"] and f"s{word}" not in facets["systems"]
        # A library's own Owner sees the same listing: it is no tenant's view.
        gm_listing = await world.gm.get("/discover/repositories", params={"q": word})
        assert gm_listing.json()["items"] == []

        # And back.
        on = await _set_listed(world.author, repo, True)
        assert on.status_code == 200, on.text
        assert on.json()["listed"] is True
        check = (await world.author.get(f"/tenants/{repo}/flip-check")).json()
        assert check["listed"] is True
        assert await _listing(visitor, word) == [str(repo)]
        assert (await _facets(visitor))["tags"][f"t{word}"] == 1
    finally:
        await world.done()


async def test_an_unlisted_repository_is_open_by_its_address_to_any_signed_in_user(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world, word = await _public(raw_client, fake_jwks_server)
    visitor = await _visitor(raw_client, fake_jwks_server)
    world.actors.append(visitor)
    repo = world.repository
    try:
        assert (await _set_listed(world.author, repo, False)).status_code == 200

        storefront = await visitor.get(f"/discover/repositories/{repo}")
        assert storefront.status_code == 200, storefront.text
        body = storefront.json()
        assert body["item"]["id"] == str(repo)
        assert body["item"]["name"] == f"Armoury {word}"
        assert body["item"]["publishers"], "who published it is still said"
        assert body["profile"]["listed"] is False
        assert body["profile"]["visibility"] == "public"
        assert body["profile"]["summary"] == f"Every blade {word}"

        for path in ("profile", "releases", "entities", "stat-groups", "dependencies", "preview"):
            response = await visitor.get(f"/repositories/{repo}/{path}")
            assert response.status_code == 200, (path, response.text)
        names = (await visitor.get(f"/repositories/{repo}/entities")).json()["items"]
        assert sorted(e["name"] for e in names) == ["Dagger", "Longsword", "Orc"]
        # A visitor's profile says it is not listed, and says nothing a private repository would.
        assert (await visitor.get(f"/repositories/{repo}/profile")).json()["listed"] is False
    finally:
        await world.done()


async def test_a_library_copies_an_unlisted_repository_by_its_address_and_updates_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world, _ = await _public(raw_client, fake_jwks_server)
    reader = await make_actor(raw_client, fake_jwks_server, "reader")
    world.actors.append(reader)
    library = await reader.create_tenant("Reader's table")
    world.tenants.append(library)
    repo = world.repository
    try:
        assert (await _set_listed(world.author, repo, False)).status_code == 200

        plan = await reader.get(f"/tenants/{library}/repositories/{repo}/copy-plan")
        assert plan.status_code == 200, plan.text
        copied = await reader.post(f"/tenants/{library}/repositories/{repo}/copy", json={})
        assert copied.status_code == 201, copied.text
        entities = await reader.get(f"/tenants/{library}/entities", params={"size": 100})
        assert sorted(e["name"] for e in entities.json()["items"]) == ["Dagger", "Longsword", "Orc"]

        # A release of it reaches the library as for any public repository.
        released = await world.author.put(
            f"/tenants/{repo}/published", json={"label": "1.1", "acknowledge_breaking": True}
        )
        assert released.status_code == 200, released.text
        updates = await reader.get(f"/tenants/{library}/repositories/{repo}/updates")
        assert updates.status_code == 200, updates.text
        # The library holds it as a copy of a public repository, which its Owner learns as a number.
        summary = (await world.author.get(f"/tenants/{repo}/subscribers/summary")).json()
        assert summary["public_copies"] == 1
    finally:
        await world.done()


async def test_the_gates_of_a_public_repository_stand_for_an_unlisted_one(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Retired and delisted stay closed to a visitor, listed or not; a release still needs to be
    made through the same gates."""
    world, _ = await _public(raw_client, fake_jwks_server)
    visitor = await _visitor(raw_client, fake_jwks_server)
    world.actors.append(visitor)
    repo = world.repository
    try:
        assert (await _set_listed(world.author, repo, False)).status_code == 200
        async with admin_session_factory() as session:
            await session.execute(
                update(Tenant)
                .where(Tenant.id == repo)
                .values(delisted_at=datetime.now(UTC), delist_reason="Abusive")
            )
            await session.commit()
        for path in (f"/discover/repositories/{repo}", f"/repositories/{repo}/profile"):
            assert (await visitor.get(path)).status_code == 404, path
        async with admin_session_factory() as session:
            await session.execute(
                update(Tenant).where(Tenant.id == repo).values(delisted_at=None, delist_reason=None)
            )
            await session.commit()
        assert (await visitor.get(f"/discover/repositories/{repo}")).status_code == 200
        async with admin_session_factory() as session:
            await session.execute(
                update(Tenant)
                .where(Tenant.id == repo)
                .values(deprecated_at=datetime.now(UTC), deprecated_message=None)
            )
            await session.commit()
        assert (await visitor.get(f"/discover/repositories/{repo}")).status_code == 404
    finally:
        await world.done()


# --- Who may, and when ---------------------------------------------------------------------------


async def test_only_an_owner_turns_listing_off_or_on(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world, word = await _public(raw_client, fake_jwks_server)
    orga = await make_actor(raw_client, fake_jwks_server, "orga", roles=())
    author = await make_actor(raw_client, fake_jwks_server, "author-too", roles=())
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger", roles=())
    world.actors += [orga, author, stranger]
    repo = world.repository
    try:
        await add_member(world.author, repo, orga, "orga")
        await add_member(world.author, repo, author, "author")
        for who in (orga, author):
            refused = await _set_listed(who, repo, False)
            assert refused.status_code == 403, refused.text
        assert (await _set_listed(stranger, repo, False)).status_code in (403, 404)
        assert (await world.author.get(f"/tenants/{repo}/profile")).json()["listed"] is True

        assert (await _set_listed(world.author, repo, False)).status_code == 200
        # Every member reads it; nobody but an Owner puts it back.
        for who in (orga, author):
            assert (await who.get(f"/tenants/{repo}/profile")).json()["listed"] is False
            assert (await _set_listed(who, repo, True)).status_code == 403
        assert (await _set_listed(world.author, repo, True)).status_code == 200
        assert await _listing(world.gm, word) == [str(repo)]
    finally:
        await world.done()


async def test_a_repository_that_is_not_public_cannot_be_left_off_discover(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)  # private, released
    repo = world.repository
    try:
        refused = await world.author.patch(
            f"/tenants/{repo}/profile", json={"listed": False, "summary": "Not kept"}
        )
        assert refused.status_code == 409, refused.text
        assert refused.json()["type"] == "repository-not-public"
        assert "tenant" not in (refused.json()["title"] + refused.json()["detail"]).lower()
        profile = (await world.author.get(f"/tenants/{repo}/profile")).json()
        # Nothing was kept, not even what was asked beside it.
        assert (profile["listed"], profile["summary"]) == (True, "")

        # Saying what it already is changes nothing and is not logged.
        same = await world.author.patch(f"/tenants/{repo}/profile", json={"listed": True})
        assert same.status_code == 200 and same.json()["listed"] is True
        async with admin_session_factory() as session:
            logged = list(
                await session.scalars(
                    select(AuditLog.detail).where(
                        AuditLog.tenant_id == repo, AuditLog.action == "repository.profile_updated"
                    )
                )
            )
        assert logged == []

        # null is not an answer.
        assert (await _set_listed(world.author, repo, None)).status_code == 422
        assert (await _set_listed(world.author, repo, "banana")).status_code == 422
    finally:
        await world.done()


async def test_changing_listing_is_logged_by_field_name(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world, _ = await _public(raw_client, fake_jwks_server)
    repo = world.repository
    try:
        assert (await _set_listed(world.author, repo, False)).status_code == 200
        # The same again is not a change.
        assert (await _set_listed(world.author, repo, False)).status_code == 200
        async with admin_session_factory() as session:
            logged = list(
                await session.scalars(
                    select(AuditLog.detail).where(
                        AuditLog.tenant_id == repo, AuditLog.action == "repository.profile_updated"
                    )
                )
            )
        # The tags, system and languages of the set-up, then listing: names, never values.
        assert logged.count("fields=listed") == 1
    finally:
        await world.done()


async def test_making_a_repository_private_lists_it_again_and_the_database_holds_the_two_together(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world, word = await _public(raw_client, fake_jwks_server)
    visitor = await _visitor(raw_client, fake_jwks_server)
    world.actors.append(visitor)
    repo = world.repository
    try:
        assert (await _set_listed(world.author, repo, False)).status_code == 200
        down = await world.author.delete(
            f"/tenants/{repo}/public", params={"acknowledge_revokes": "true"}
        )
        assert down.status_code == 200, down.text
        profile = (await world.author.get(f"/tenants/{repo}/profile")).json()
        assert (profile["visibility"], profile["listed"]) == ("private", True)

        # Public again: on Discover, as a repository made public always is.
        up = await world.author.put(
            f"/tenants/{repo}/public",
            json={"accept_terms": True, "summary": f"Every blade {word}"},
        )
        assert up.status_code == 200, up.text
        assert await _listing(visitor, word) == [str(repo)]

        # The database refuses a private repository that is not listed.
        async with admin_session_factory() as session:
            with pytest.raises(IntegrityError, match="repository_profile_listed"):
                await session.execute(
                    update(RepositoryProfile)
                    .where(RepositoryProfile.tenant_id == repo)
                    .values(visibility="private", listed=False)
                )
    finally:
        await world.done()


# --- The rule that says what is listed, in its three statements ---------------------------------


async def _matrix_row(
    *,
    visibility: str,
    released: bool,
    published: bool,
    delisted: bool,
    deprecated: bool,
    is_listed: bool,
    word: str,
) -> uuid.UUID:
    async with admin_session_factory() as session:
        now = datetime.now(UTC)
        tenant = Tenant(
            name=f"Matrix {word}",
            kind=TenantKind.REPOSITORY,
            published_at=now if published else None,
            delisted_at=now if delisted else None,
            delist_reason="Abusive" if delisted else None,
            deprecated_at=now if deprecated else None,
        )
        session.add(tenant)
        await session.flush()
        session.add(
            RepositoryProfile(
                tenant_id=tenant.id,
                visibility=visibility,
                listed=is_listed,
                tags=[word],
                release_label="1.0" if released else None,
                released_at=now if released else None,
            )
        )
        await session.commit()
        return tenant.id


async def test_the_python_statement_the_facets_sql_and_the_policy_say_the_same_thing() -> None:
    """Every combination of what the rule reads, written straight in the database: the listing's
    statement, the facets' SQL and `discover_read` (as the restricted role, in no tenant and in a
    library) list exactly the same repositories, and only the one that is public, released,
    published, not delisted, not retired and not left off is among them."""
    word = uuid.uuid4().hex[:10]
    ids: dict[uuid.UUID, tuple[bool, ...]] = {}
    library = None
    try:
        for combo in itertools.product((True, False), repeat=6):
            public, released, published, delisted, deprecated, is_listed = combo
            if not public and not is_listed:
                continue  # the check forbids it, tested above
            ids[
                await _matrix_row(
                    visibility="public" if public else "private",
                    released=released,
                    published=published,
                    delisted=delisted,
                    deprecated=deprecated,
                    is_listed=is_listed,
                    word=word,
                )
            ] = combo
        async with admin_session_factory() as session:
            library = Tenant(name=f"Library {word}")
            session.add(library)
            await session.commit()
            library_id = library.id

        expected = {
            i
            for i, (public, released, published, delisted, deprecated, is_listed) in ids.items()
            if public and released and published and not delisted and not deprecated and is_listed
        }
        assert len(expected) == 1

        async with admin_session_factory() as session:
            python = {
                p.tenant_id
                for p, _ in (
                    await session.execute(listed().where(RepositoryProfile.tags.any(word)))
                ).all()
            }
            sql = set(
                await session.scalars(
                    text(f"SELECT p.tenant_id {_LISTED_SQL} AND :w = ANY(p.tags)").bindparams(
                        w=word
                    )
                )
            )
        assert python == sql == expected

        for reader in (NO_TENANT, library_id):
            async with _as(reader) as session:
                seen = set(
                    await session.scalars(
                        select(RepositoryProfile.tenant_id).where(
                            RepositoryProfile.tenant_id.in_(list(ids)),
                            RepositoryProfile.tags.any(word),
                        )
                    )
                )
            assert seen == expected, reader
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM tenant WHERE id = ANY(:ids) OR name = :n").bindparams(
                    ids=list(ids), n=f"Library {word}"
                )
            )
            await session.commit()


async def test_an_unlisted_repository_is_read_through_the_gate_and_by_its_own_tenant() -> None:
    """The restricted role: `discover_read` does not show an unlisted profile to a visitor or a
    library, the gated read still does (it is public), and the repository's own tenant reads its
    own profile."""
    word = uuid.uuid4().hex[:10]
    repository = await _matrix_row(
        visibility="public",
        released=True,
        published=True,
        delisted=False,
        deprecated=False,
        is_listed=False,
        word=word,
    )
    async with admin_session_factory() as session:
        other = Tenant(name=f"Other {word}")
        session.add(other)
        await session.commit()
        other_id = other.id
    try:
        for reader in (NO_TENANT, other_id):
            async with _as(reader) as session:
                assert (
                    await session.scalar(
                        select(RepositoryProfile.tenant_id).where(
                            RepositoryProfile.tenant_id == repository
                        )
                    )
                ) is None
            async with _as(reader) as session, reading_repository(session, repository) as allowed:
                assert allowed is True
                found = await session.scalar(
                    select(RepositoryProfile.tenant_id).where(
                        RepositoryProfile.tenant_id == repository
                    )
                )
                assert found == repository
        async with _as(repository) as session:
            assert (
                await session.scalar(
                    select(RepositoryProfile.tenant_id).where(
                        RepositoryProfile.tenant_id == repository
                    )
                )
            ) == repository
    finally:
        async with admin_session_factory() as session:
            await session.execute(
                text("DELETE FROM tenant WHERE id = ANY(:ids)").bindparams(
                    ids=[repository, other_id]
                )
            )
            await session.commit()
