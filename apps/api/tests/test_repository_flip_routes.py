"""ADR 0290: the flips as routes. `PUT /tenants/{id}/public` makes a repository public with its
first public release, `DELETE` makes it private, `GET /flip-check` says what either would run
into, and a deployment that does not accept public repositories refuses the first.
"""

import uuid
from typing import Any

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import select
from test_repository_attachments import _stack

from lorenzo_api.config import get_settings
from lorenzo_api.models import RepositoryProfile


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def _profile(repository: uuid.UUID) -> RepositoryProfile:
    async with admin_session_factory() as session:
        return await session.get_one(RepositoryProfile, repository)


async def _check(world: ReleaseWorld) -> dict[str, Any]:
    response = await world.author.get(f"/tenants/{world.repository}/flip-check")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def _notices(actor: Any) -> list[dict[str, Any]]:
    response = await actor.get("/me/notifications")
    return response.json()["items"]  # type: ignore[no-any-return]


# --- A deployment that does not accept public repositories --------------------------------------


async def test_a_deployment_without_public_repositories_refuses_the_flip_in_words(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        assert (await _check(world))["available"] is False
        refused = await world.author.put(
            f"/tenants/{world.repository}/public",
            json={"accept_terms": True, "summary": "Every blade there is"},
        )
        assert refused.status_code == 422
        assert refused.json()["type"] == "public-repositories-not-available"
        assert "tenant" not in (refused.json()["title"] + refused.json()["detail"]).lower()
        # Nothing was kept, not even the summary beside it.
        profile = await _profile(world.repository)
        assert (profile.visibility, profile.summary) == ("private", "")
    finally:
        await world.done()


# --- Making a repository public -----------------------------------------------------------------


async def test_the_owner_makes_a_repository_public_with_its_first_public_release(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    world = await release_world(raw_client, fake_jwks_server)  # 1.0, private, granted to a library
    try:
        before = await _check(world)
        assert before["available"] is True
        assert (before["visibility"], before["has_summary"]) == ("private", False)
        assert (before["public_libraries"], before["invited_libraries"]) == (0, 1)
        assert before["built_on_not_public"] == before["public_dependents"] == []

        told = len(await _notices(world.gm))
        response = await world.author.put(
            f"/tenants/{world.repository}/public",
            json={
                "accept_terms": True,
                "label": "2.0",
                "summary": "Every blade there is",
                "preview": "off",
            },
        )
        assert response.status_code == 200, response.text
        release = response.json()["release"]
        assert (release["label"], release["current"], release["kept"]) == ("2.0", True, True)

        profile = await _profile(world.repository)
        assert (profile.visibility, profile.preview, profile.summary) == (
            "public",
            "off",
            "Every blade there is",
        )
        after = await _check(world)
        assert (after["visibility"], after["has_summary"]) == ("public", True)
        # The library that read it live reads the release now, and was told.
        names = await world.gm.get(
            f"/tenants/{world.table}/repositories/{world.repository}/entities"
        )
        assert [e["name"] for e in names.json()["items"]] == ["Dagger", "Longsword", "Orc"]
        notices = await _notices(world.gm)
        assert len(notices) == told + 1
        assert "It is now public" in notices[0]["body"]
        # And any signed-in user reads it, with no library.
        visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
        world.actors.append(visitor)
        assert (await visitor.get(f"/repositories/{world.repository}/entities")).status_code == 200
    finally:
        await world.done()


async def test_a_repository_needs_a_summary_to_go_public_and_the_preview_defaults_to_showcase(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        url = f"/tenants/{world.repository}/public"
        refused = await world.author.put(url, json={"accept_terms": True, "summary": "   "})
        assert refused.status_code == 422
        assert refused.json()["type"] == "public-repository-summary-required"
        assert (await _profile(world.repository)).visibility == "private"

        # One already on the profile counts.
        await world.author.patch(
            f"/tenants/{world.repository}/profile", json={"summary": "Already said"}
        )
        accepted = await world.author.put(url, json={"accept_terms": True})
        assert accepted.status_code == 200, accepted.text
        profile = await _profile(world.repository)
        assert (profile.summary, profile.preview) == ("Already said", "showcase")
        assert (
            await world.author.put(url, json={"accept_terms": True})
        ).status_code == 409  # already public
    finally:
        await world.done()


async def test_a_repository_built_on_a_private_one_is_not_made_public_and_the_check_says_why(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        check = (await stack.author.get(f"/tenants/{stack.bridge}/flip-check")).json()
        assert sorted((r["name"], r["owned"]) for r in check["built_on_not_public"]) == [
            ("Common Equipment", True),
            ("D&D 5e", True),
        ]
        refused = await stack.author.put(
            f"/tenants/{stack.bridge}/public",
            json={"accept_terms": True, "summary": "The 5e armoury"},
        )
        assert refused.status_code == 409
        assert refused.json()["type"] == "built-on-not-public"
        assert len(refused.json()["repositories"]) == 2

        # The Owner makes each public, upstream first, the bridge takes their releases, and then
        # the bridge itself goes public.
        for upstream in (stack.equipment, stack.rules):
            made = await stack.author.put(
                f"/tenants/{upstream}/public", json={"accept_terms": True, "summary": "An upstream"}
            )
            assert made.status_code == 200, made.text
        behind = await stack.author.get(f"/tenants/{stack.bridge}/flip-check")
        assert [b["name"] for b in behind.json()["built_on_behind"]] == [
            "Common Equipment",
            "D&D 5e",
        ]
        for upstream in (stack.equipment, stack.rules):
            taken = await stack.author.post(
                f"/tenants/{stack.bridge}/repositories/{upstream}/updates", json={"actions": []}
            )
            assert taken.status_code == 200, taken.text
        made = await stack.author.put(
            f"/tenants/{stack.bridge}/public",
            json={"accept_terms": True, "summary": "The 5e armoury"},
        )
        assert made.status_code == 200, made.text
    finally:
        await cleanup(stack.tenants, stack.actors)


async def test_only_the_owner_flips_a_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    try:
        for method, path in (
            ("GET", "flip-check"),
            ("PUT", "public"),
            ("DELETE", "public"),
        ):
            response = await stranger.client.request(
                method, f"/tenants/{world.repository}/{path}", headers=stranger.headers
            )
            assert response.status_code == 404, (method, path, response.text)
        assert (await _profile(world.repository)).visibility == "private"
    finally:
        await world.done()
        await cleanup([], [stranger])


# --- Making a repository private ----------------------------------------------------------------


async def _public_world(raw_client: AsyncClient, jwks: FakeJwksServer) -> ReleaseWorld:
    world = await release_world(raw_client, jwks)
    made = await world.author.put(
        f"/tenants/{world.repository}/public",
        json={"accept_terms": True, "summary": "Every blade there is"},
    )
    assert made.status_code == 200, made.text
    return world


async def test_making_a_repository_private_asks_first_and_keeps_the_invited(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    stranger = await make_actor(raw_client, fake_jwks_server, "copier")
    library = await stranger.create_tenant("A table of its own")
    world.tenants.append(library)
    world.actors.append(stranger)
    try:
        copied = await stranger.post(
            f"/tenants/{library}/repositories/{world.repository}/copy", json={}
        )
        assert copied.status_code == 201, copied.text
        check = await _check(world)
        assert (check["public_libraries"], check["invited_libraries"]) == (1, 1)

        url = f"/tenants/{world.repository}/public"
        warned = await world.author.delete(url)
        assert warned.status_code == 409
        assert warned.json()["type"] == "public-copies-would-be-cut-off"
        assert warned.json()["libraries"] == 1
        assert (await _profile(world.repository)).visibility == "public"

        made = await world.author.delete(url, params={"acknowledge_revokes": "true"})
        assert made.status_code == 200, made.text
        assert made.json() == {"revoked": 1}
        assert (await _profile(world.repository)).visibility == "private"
        after = await _check(world)
        assert (after["visibility"], after["public_libraries"], after["invited_libraries"]) == (
            "private",
            0,
            1,
        )
        # The one the Owner invited reads it live; the copier is cut off and keeps its copy.
        assert (
            await world.gm.get(f"/tenants/{world.table}/repositories/{world.repository}/entities")
        ).status_code == 200
        assert (
            await stranger.get(f"/tenants/{library}/repositories/{world.repository}/entities")
        ).status_code == 404
        assert (await world.author.delete(url)).status_code == 409  # already private
    finally:
        await world.done()


async def test_a_repository_a_public_one_is_built_on_is_not_made_private(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    stack = await _stack(raw_client, fake_jwks_server)
    try:
        for repository in (stack.equipment, stack.rules):
            made = await stack.author.put(
                f"/tenants/{repository}/public",
                json={"accept_terms": True, "summary": "An upstream"},
            )
            assert made.status_code == 200, made.text
        await publish_stack_taking_releases(stack)
        made = await stack.author.put(
            f"/tenants/{stack.bridge}/public",
            json={"accept_terms": True, "summary": "The 5e armoury"},
        )
        assert made.status_code == 200, made.text

        check = (await stack.author.get(f"/tenants/{stack.equipment}/flip-check")).json()
        assert [d["name"] for d in check["public_dependents"]] == ["D&D Equipment"]
        assert check["public_dependents"][0]["owned"] is True
        refused = await stack.author.delete(f"/tenants/{stack.equipment}/public")
        assert refused.status_code == 409
        assert refused.json()["type"] == "public-repositories-built-on-it"
        assert [d["name"] for d in refused.json()["repositories"]] == ["D&D Equipment"]

        assert (await stack.author.delete(f"/tenants/{stack.bridge}/public")).status_code == 200
        assert (await stack.author.delete(f"/tenants/{stack.equipment}/public")).status_code == 200
    finally:
        await cleanup(stack.tenants, stack.actors)


async def publish_stack_taking_releases(stack: Any) -> None:
    """The bridge takes the releases its upstreams made as they went public."""
    for upstream in (stack.equipment, stack.rules):
        response = await stack.author.post(
            f"/tenants/{stack.bridge}/repositories/{upstream}/updates", json={"actions": []}
        )
        assert response.status_code == 200, response.text


# --- The profile and the deletion keep to the rules -------------------------------------------


async def test_the_profile_cannot_flip_a_repository_and_a_public_one_is_not_deleted_with_copies(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    stranger = await make_actor(raw_client, fake_jwks_server, "copier")
    library = await stranger.create_tenant("A table of its own")
    world.tenants.append(library)
    world.actors.append(stranger)
    try:
        profile_url = f"/tenants/{world.repository}/profile"
        refused = await world.author.patch(profile_url, json={"visibility": "private"})
        assert refused.status_code == 422
        assert refused.json()["type"] == "visibility-has-its-own-route"
        assert (await _profile(world.repository)).visibility == "public"
        # Saying what it already is changes nothing and is allowed.
        same = await world.author.patch(profile_url, json={"visibility": "public"})
        assert same.status_code == 200

        await stranger.post(f"/tenants/{library}/repositories/{world.repository}/copy", json={})
        deleted = await world.author.delete(f"/tenants/{world.repository}")
        assert deleted.status_code == 409
        assert "make it private first" in deleted.json()["detail"]
        async with admin_session_factory() as session:
            assert await session.scalar(
                select(RepositoryProfile.tenant_id).where(
                    RepositoryProfile.tenant_id == world.repository
                )
            )
    finally:
        await world.done()
        await cleanup([], [stranger])


async def test_a_public_repository_is_made_private_and_not_unpublished(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        refused = await world.author.delete(f"/tenants/{world.repository}/published")
        assert refused.status_code == 409
        assert refused.json()["type"] == "public-repository-cannot-be-unpublished"
        assert "Make this repository private first" in refused.json()["detail"]
        # Nothing moved: libraries still read it.
        assert (
            await world.gm.get(f"/tenants/{world.table}/repositories/{world.repository}/entities")
        ).status_code == 200

        made = await world.author.delete(
            f"/tenants/{world.repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert made.status_code == 200, made.text
        assert (
            await world.author.delete(f"/tenants/{world.repository}/published")
        ).status_code == 200
    finally:
        await world.done()
