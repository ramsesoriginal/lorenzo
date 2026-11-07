"""ADR 0435, RFC 0051 H4: the choice `hide`, A's third term, and what a release records of it.

A is the Armoury of the release tests, protected (or public, where the test says so); B is a bridge
built on it. Everything goes through the HTTP API; the database is read where the test says so.
"""

import pytest
from _admin_db import admin_session_factory
from _author_world import add_member
from _fake_jwks import FakeJwksServer
from _hidden_world import choose, protect, world
from _release_world import release_world
from _repository_actors import make_actor
from httpx import AsyncClient
from sqlalchemy import select
from test_repository_include import (
    W,
    _bridge,
    _copy,
    _document,
    _library,
    _make_public,
)

from lorenzo_api.config import get_settings
from lorenzo_api.models import RepositoryCopy, RepositoryProfile
from lorenzo_api.repository_inclusion import (
    Terms,
    default_may_be_hidden,
    terms_of,
)


@pytest.fixture(autouse=True)
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def _protected_world(raw_client: AsyncClient, jwks: FakeJwksServer) -> W:
    """A is protected and B copied it and is not public yet; both are one Owner's."""
    base = await release_world(raw_client, jwks)
    assert (await protect(base.author, base.repository, label="p1")).status_code == 200
    b, ids = await _bridge(base, "Bridge")
    return W(base, b, ids)


# --- The choice ------------------------------------------------------------------------------


async def test_hide_is_kept_on_the_copy_record_listed_and_recorded_in_the_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _protected_world(raw_client, fake_jwks_server)
    try:
        chosen = await choose(w.author, w.b, w.a, "hide")
        assert chosen.status_code == 200, chosen.text
        body = chosen.json()
        assert body["inclusion"] == "hide" and body["breaking_next_release"] is False
        assert body["hidable"] == {"allowed": True, "by": "owner"}
        async with admin_session_factory() as session:
            assert (await session.get_one(RepositoryCopy, (w.b, w.a))).inclusion == "hide"
        listed = (await w.author.get(f"/tenants/{w.b}/repositories")).json()["items"]
        assert listed[0]["inclusion"] == "hide"
        assert listed[0]["hidable"] == {"allowed": True, "by": "owner"}
        check = (await w.author.get(f"/tenants/{w.b}/flip-check")).json()
        source = check["built_on"][0]
        assert (source["inclusion"], source["hidable"]["allowed"], source["may_be_hidden"]) == (
            "hide",
            True,
            True,
        )
        # A hidden source is carried separate, so it is reached, and the stack rule is met.
        assert check["built_on_not_public"] == []
        # A's Owner reads the choice among who built on it.
        named = (await w.author.get(f"/tenants/{w.a}/subscribers")).json()["items"]
        assert {s["name"]: s["inclusion"] for s in named}["Bridge"] == "hide"

        assert (await _make_public(w.author, w.b)).status_code == 200
        document = await _document(w.b)
        assert document.sources[w.a]["inclusion"] == "hide"
        # B is built on A still: a library copying it gets A as a step.
        assert w.a in document.links.copies
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, w.b)
            assert [(s["name"], s["inclusion"]) for s in profile.release_sources or []] == [
                ("Armoury", "hide")
            ]
        # What B includes is named on its storefront; what it hides is not.
        storefront = (await w.author.get(f"/tenants/{w.b}/profile")).json()
        assert storefront["includes"] == []
    finally:
        await w.done()


async def test_a_visitor_and_a_library_are_not_shown_the_entries_a_repository_hides(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The browse, the preview and the counts of B leave out what it carries hidden, so the
    storefront does not give away what the libraries are not shown."""
    h = await world(raw_client, fake_jwks_server, copy=False)
    try:
        shown = await h.w.author.patch(f"/tenants/{h.b}/profile", json={"preview": "public"})
        assert shown.status_code == 200, shown.text
        listed = (await h.reader.get(f"/repositories/{h.b}/entities", params={"size": 100})).json()
        assert [e["name"] for e in listed["items"]] == ["Bridge Blade"]
        async with admin_session_factory() as session:
            profile = await session.get_one(RepositoryProfile, h.b)
            assert profile.entry_count == 1
        # B's Owner sees the same in its preview: a hidden entry is not previewed.
        for name, entity_id in sorted(h.w.ids.items()):
            if name in ("Longsword", "Dagger"):
                entry = await h.reader.get(f"/repositories/{h.b}/entities/{entity_id}")
                assert entry.status_code == 404, name
        # What A's Owner shows is still what its own members and its dependents read.
        owner = (await h.w.author.get(f"/tenants/{h.a}/profile")).json()
        assert owner["visibility"] == "protected"
    finally:
        await h.done()


async def test_changing_the_choice_after_a_public_release_makes_the_next_release_breaking(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    w = await _protected_world(raw_client, fake_jwks_server)
    try:
        assert (await _make_public(w.author, w.b)).status_code == 200
        changed = await choose(w.author, w.b, w.a, "hide")
        assert changed.status_code == 200
        assert changed.json()["breaking_next_release"] is True
        assert changed.json()["inclusion_in_release"] == "show"
        refused = await w.author.put(f"/tenants/{w.b}/published", json={"label": "2"})
        assert refused.status_code == 409
        assert refused.json()["type"] == "release-has-breaking-changes"
        assert [(c["before"], c["after"]) for c in refused.json()["inclusion_changes"]] == [
            ("show", "hide")
        ]
        done = await w.author.put(
            f"/tenants/{w.b}/published", json={"label": "2", "acknowledge_breaking": True}
        )
        assert done.status_code == 200, done.text
        assert done.json()["release"]["breaking"] is True
        # And back to show, once more breaking.
        back = await choose(w.author, w.b, w.a, "show")
        assert back.json()["breaking_next_release"] is True
    finally:
        await w.done()


async def test_a_public_source_can_be_hidden_and_a_private_one_cannot_be_reached_that_way(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """Hiding a public repository is cosmetic and allowed (anyone can copy it); hiding does not
    make a private one reachable, which only including it does."""
    base = await release_world(raw_client, fake_jwks_server)
    b, _ = await _bridge(base, "Bridge")
    w = W(base, b, {})
    try:
        assert (await choose(base.author, b, base.repository, "hide")).status_code == 200
        check = (await base.author.get(f"/tenants/{b}/flip-check")).json()
        assert [s["name"] for s in check["built_on_not_public"]] == ["Armoury"]
        refused = await _make_public(base.author, b)
        assert refused.status_code == 409 and refused.json()["type"] == "built-on-not-public"
        # A public A is reached: hidden over it, B is public.
        assert (await _make_public(base.author, base.repository)).status_code == 200
        # B takes the release A made as it became public, which the skew gate asks of it.
        taken = await base.author.post(
            f"/tenants/{b}/repositories/{base.repository}/updates", json={"actions": []}
        )
        assert taken.status_code == 200, taken.text
        assert (await _make_public(base.author, b)).status_code == 200
        # A public repository cannot say it may not be hidden, however it is asked.
        said = await base.author.patch(
            f"/tenants/{base.repository}/profile", json={"terms": {"may_be_hidden": False}}
        )
        assert said.status_code == 409 and said.json()["type"] == "repository-not-protected"
    finally:
        await w.done()


# --- A's terms ------------------------------------------------------------------------------


async def test_a_protected_repository_can_say_it_may_not_be_hidden(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    base = await release_world(raw_client, fake_jwks_server)
    owner_b = await make_actor(raw_client, fake_jwks_server, "owner-b")
    # A private repository cannot say no; nothing is stored.
    refused = await base.author.patch(
        f"/tenants/{base.repository}/profile", json={"terms": {"may_be_hidden": False}}
    )
    assert refused.status_code == 409 and refused.json()["type"] == "repository-not-protected"
    assert (await protect(base.author, base.repository, label="p1")).status_code == 200
    b, _ = await _bridge(base, "Other Bridge", owner=owner_b)
    w = W(base, b, {}, [], [owner_b])
    try:
        terms = (await base.author.get(f"/tenants/{base.repository}/profile")).json()["terms"]
        assert (terms["may_be_hidden"], terms["may_be_hidden_is_default"]) == (True, True)
        said = await base.author.patch(
            f"/tenants/{base.repository}/profile", json={"terms": {"may_be_hidden": False}}
        )
        assert said.status_code == 200, said.text
        assert (said.json()["terms"]["may_be_hidden"], said.json()["terms"]["is_default"]) == (
            False,
            True,
        )
        # Another Owner may not keep it separate and hidden, and is told what is left; A's Owner is
        # not held to it.
        refused = await choose(owner_b, b, base.repository, "hide")
        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-not-hidable"
        assert refused.json()["repositories"] == [{"id": str(base.repository), "name": "Armoury"}]
        listed = (await owner_b.get(f"/tenants/{b}/repositories")).json()["items"]
        assert listed[0]["hidable"] == {"allowed": False, "by": None}
        assert listed[0]["showable"]["allowed"] is True
        async with admin_session_factory() as session:
            assert (await session.get_one(RepositoryCopy, (b, base.repository))).inclusion == "show"
        # The terms of the screen's two presets are switches that say the same.
        await add_member(owner_b, b, base.author, "owner")
        own = await choose(base.author, b, base.repository, "hide")
        assert own.status_code == 200 and own.json()["hidable"]["by"] == "owner"
        await choose(base.author, b, base.repository, "show")

        # Taken back, it is the default again and the other Owner may.
        back = await base.author.patch(
            f"/tenants/{base.repository}/profile", json={"terms": {"may_be_hidden": None}}
        )
        assert back.json()["terms"]["may_be_hidden_is_default"] is True
        allowed = await choose(owner_b, b, base.repository, "hide")
        assert allowed.status_code == 200 and allowed.json()["hidable"]["by"] == "terms"
        assert (await _make_public(owner_b, b)).status_code == 200

        # And said again, the next release is refused, naming A, and keeps nothing.
        assert (
            await base.author.patch(
                f"/tenants/{base.repository}/profile", json={"terms": {"may_be_hidden": False}}
            )
        ).status_code == 200
        again = await owner_b.put(f"/tenants/{b}/published", json={"label": "1.1"})
        assert again.status_code == 409
        assert again.json()["type"] == "repository-not-hidable"
        assert [r["name"] for r in again.json()["repositories"]] == ["Armoury"]
    finally:
        await w.done()


async def test_the_terms_of_a_repository_are_read_by_the_functions_that_say_them() -> None:
    assert default_may_be_hidden("private") and default_may_be_hidden("public")
    assert terms_of(None) == Terms(may_be_included=False, may_be_shown=True, may_be_hidden=True)

    def profile(visibility: str, hidden: bool | None) -> RepositoryProfile:
        return RepositoryProfile(visibility=visibility, may_be_hidden=hidden)

    # Only a protected repository's `no` counts; what an Owner said while it was protected waits.
    assert terms_of(profile("protected", False)).may_be_hidden is False
    assert terms_of(profile("public", False)).may_be_hidden is True
    assert terms_of(profile("private", False)).may_be_hidden is True
    assert terms_of(profile("protected", None)).may_be_hidden is True


async def test_a_library_that_copies_the_repository_hides_nothing_of_a_source_it_shows(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The control: the same world with the source shown holds, and shows, every entry."""
    h = await world(raw_client, fake_jwks_server, choice="show")
    try:
        names = (await h.get("/entities", params={"size": 100})).json()["items"]
        assert sorted(e["name"] for e in names) == ["Bridge Blade", "Dagger", "Longsword", "Orc"]
        reader, library = await _library(raw_client, fake_jwks_server, h.w, "Other")
        assert (await _copy(reader, library, h.b)).status_code == 201
        async with admin_session_factory() as session:
            assert (
                await session.scalar(
                    select(RepositoryCopy.carries).where(
                        RepositoryCopy.tenant_id == library,
                        RepositoryCopy.repository_tenant_id == h.b,
                    )
                )
            ) == {str(h.a): "show", str(h.b): "show"}
    finally:
        await h.done()
