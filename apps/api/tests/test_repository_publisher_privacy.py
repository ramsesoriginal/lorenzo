"""ADR 0299, RFC 0038 section 6 items 4 to 6: what a repository learns of the libraries that copied
it (a number, never a name), who a storefront says published it (its Owners' accounts), the report
link, and the terms line behind `PUT .../public`.

A repository is made public in the database where a test needs one that is already public, since
the API refuses it unless the deployment accepts public repositories; the flip itself is tested
through the route with the setting on.
"""

import json
import uuid
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _release_world import ReleaseWorld, release_world
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import select
from test_public_repository_read import _public_world

from lorenzo_api.config import get_settings
from lorenzo_api.models import AuditLog, Membership, MembershipRole, RepositorySubscription

LIBRARY_NAME = "The Secret Society"


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "public_repositories_enabled", True)


async def _copier(
    raw_client: AsyncClient, jwks: FakeJwksServer, world: ReleaseWorld
) -> tuple[Actor, uuid.UUID]:
    """Somebody else's library, which copies the public repository by itself."""
    copier = await make_actor(raw_client, jwks, "copier")
    library = await copier.create_tenant(LIBRARY_NAME)
    copied = await copier.post(f"/tenants/{library}/repositories/{world.repository}/copy", json={})
    assert copied.status_code == 201, copied.text
    world.tenants.append(library)
    world.actors.append(copier)
    return copier, library


async def _log(world: ReleaseWorld) -> list[dict[str, Any]]:
    response = await world.author.get(f"/tenants/{world.repository}/activity-log")
    assert response.status_code == 200, response.text
    return response.json()["items"]  # type: ignore[no-any-return]


async def _summary(world: ReleaseWorld) -> dict[str, int]:
    response = await world.author.get(f"/tenants/{world.repository}/subscribers/summary")
    assert response.status_code == 200, response.text
    return response.json()  # type: ignore[no-any-return]


async def _subscribers(world: ReleaseWorld) -> list[dict[str, Any]]:
    response = await world.author.get(f"/tenants/{world.repository}/subscribers")
    assert response.status_code == 200, response.text
    return response.json()["items"]  # type: ignore[no-any-return]


# --- The libraries that copied it ---------------------------------------------------------------


async def test_the_owner_sees_the_invited_by_name_and_the_public_copies_as_a_number(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server, granted=True)
    try:
        _, library = await _copier(raw_client, fake_jwks_server, world)

        listed = await _subscribers(world)
        assert [s["name"] for s in listed] == ["My Table"]
        assert await _summary(world) == {"named": 1, "public_copies": 1}

        # Nowhere the Owner reads says which library it was: not the list, the log, the notices.
        everything = json.dumps(
            [
                listed,
                await _log(world),
                (await world.author.get("/me/notifications")).json(),
                (await world.author.get(f"/tenants/{world.repository}/subscribers")).json(),
            ]
        )
        assert LIBRARY_NAME not in everything
        assert str(library) not in everything
    finally:
        await world.done()


async def test_the_repository_log_says_a_library_copied_it_and_not_which(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        before = [e for e in await _log(world) if e["action"] == "repository.copied_publicly"]
        assert before == []
        copier, library = await _copier(raw_client, fake_jwks_server, world)

        entries = [e for e in await _log(world) if e["action"] == "repository.copied_publicly"]
        assert len(entries) == 1
        entry = entries[0]
        # No person, no library, no detail: the entry is the fact and nothing that identifies it.
        assert (entry["actor_id"], entry["target_id"], entry["detail"]) == (None, None, None)
        assert str(copier.user_id) not in json.dumps(entries)
        assert str(library) not in json.dumps(entries)

        # The library's own log keeps its own record of it, as for anything it does.
        own = await copier.get(f"/tenants/{library}/activity-log")
        actions = [e["action"] for e in own.json()["items"]]
        assert "repository.copied" in actions and "repository.subscribed" in actions
    finally:
        await world.done()


async def test_a_copy_that_outlives_the_repository_going_private_is_still_only_counted(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server, granted=True)
    try:
        await _copier(raw_client, fake_jwks_server, world)
        made = await world.author.delete(
            f"/tenants/{world.repository}/public", params={"acknowledge_revokes": "true"}
        )
        assert made.status_code == 200, made.text
        assert made.json()["revoked"] == 1

        # Its public grant is gone and its copy stays, and the copy is not a name to be told.
        assert [s["name"] for s in await _subscribers(world)] == ["My Table"]
        assert await _summary(world) == {"named": 1, "public_copies": 1}
        assert LIBRARY_NAME not in json.dumps(await _log(world))
    finally:
        await world.done()


async def test_a_library_invited_once_and_not_any_more_is_still_named_while_it_holds_a_copy(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        await world.copy()
        stopped = await world.author.delete(
            f"/tenants/{world.repository}/subscribers/{world.table}"
        )
        assert stopped.status_code == 204
        listed = await _subscribers(world)
        assert [(s["name"], s["granted_at"]) for s in listed] == [("My Table", None)]
        assert await _summary(world) == {"named": 1, "public_copies": 0}
    finally:
        await world.done()


async def test_no_route_of_the_repository_names_or_ends_a_grant_a_library_gave_itself(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    try:
        _, library = await _copier(raw_client, fake_jwks_server, world)
        gone = await world.author.delete(f"/tenants/{world.repository}/subscribers/{library}")
        assert gone.status_code == 404
        assert gone.json()["type"] == "subscription-not-found"
        async with admin_session_factory() as session:
            sources = await session.scalars(
                select(RepositorySubscription.source).where(
                    RepositorySubscription.repository_tenant_id == world.repository,
                    RepositorySubscription.subscriber_tenant_id == library,
                )
            )
            assert list(sources) == ["public"]

        # Inviting it, which the Owner may do by its id, makes it an invitation and the answer is
        # the one for any new invitation, whether or not it had copied the repository.
        invited = await world.author.put(f"/tenants/{world.repository}/subscribers/{library}")
        assert invited.status_code == 201
        assert [s["name"] for s in await _subscribers(world)] == [LIBRARY_NAME]
        assert await _summary(world) == {"named": 1, "public_copies": 0}
    finally:
        await world.done()


async def test_the_summary_is_for_the_administrators_of_a_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server, granted=True)
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger", roles=())
    try:
        url = f"/tenants/{world.repository}/subscribers/summary"
        # Not a member of the repository, a library's Owner included: it is not there for them.
        assert (await stranger.get(url)).status_code == 404
        assert (await world.gm.get(url)).status_code == 404
        assert (await raw_client.get(url)).status_code == 401
    finally:
        await world.done()
        await cleanup([], [stranger])


# --- Who published it ---------------------------------------------------------------------------


async def _add_member(world: ReleaseWorld, actor: Actor, role: MembershipRole) -> None:
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=world.repository, user_id=actor.user_id, role=role))
        await session.commit()


async def test_a_storefront_and_a_listing_say_the_owners_accounts_published_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    second = await make_actor(raw_client, fake_jwks_server, "second")
    editor = await make_actor(raw_client, fake_jwks_server, "editor")
    try:
        assert (
            await world.author.patch("/me", json={"display_name": "Ada Author"})
        ).status_code == 200
        nickname = f"bob-{uuid.uuid4().hex[:8]}"
        assert (await second.patch("/me", json={"nickname": nickname})).status_code == 200
        await _add_member(world, second, MembershipRole.OWNER)
        await _add_member(world, editor, MembershipRole.ORGA)

        # What the repository writes about itself never changes who published it.
        await world.author.patch(
            f"/tenants/{world.repository}/profile",
            json={
                "summary": "By Somebody Else",
                "credits": [{"name": "Somebody Else", "role": "Publisher"}],
            },
        )
        await world.author.patch(
            f"/tenants/{world.repository}", json={"description": "Published by Somebody Else"}
        )

        store = await visitor.get(f"/discover/repositories/{world.repository}")
        assert store.status_code == 200, store.text
        expected = [{"display_name": "Ada Author"}, {"display_name": nickname}]
        assert store.json()["item"]["publishers"] == expected

        word = uuid.uuid4().hex[:10]
        await world.author.patch(f"/tenants/{world.repository}", json={"name": f"Armoury {word}"})
        listing = await visitor.get("/discover/repositories", params={"q": word})
        mine = [i for i in listing.json()["items"] if i["id"] == str(world.repository)]
        assert mine[0]["publishers"] == expected
    finally:
        await world.done()
        await cleanup([], [visitor, second, editor])


async def test_an_owner_with_no_name_is_a_lorenzo_account_and_a_handful_are_named(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    others = [await make_actor(raw_client, fake_jwks_server, f"owner{n}") for n in range(6)]
    try:
        store = await visitor.get(f"/discover/repositories/{world.repository}")
        assert store.json()["item"]["publishers"] == [{"display_name": "A Lorenzo account"}]
        for other in others:
            await _add_member(world, other, MembershipRole.OWNER)
        store = await visitor.get(f"/discover/repositories/{world.repository}")
        assert len(store.json()["item"]["publishers"]) == 5
    finally:
        await world.done()
        await cleanup([], [visitor, *others])


async def test_reading_the_owners_leaves_the_reader_in_no_tenant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The publishers are read under each repository's own context; the reader's is put back, so
    what the same request reads next is still nothing of any tenant."""
    world = await _public_world(raw_client, fake_jwks_server)
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    try:
        listing = await visitor.get("/discover/repositories")
        assert listing.status_code == 200
        # The visitor still cannot read the repository's own members or log.
        assert (await visitor.get(f"/tenants/{world.repository}/memberships")).status_code in (
            403,
            404,
        )
        assert (await visitor.get(f"/tenants/{world.repository}/activity-log")).status_code in (
            403,
            404,
        )
    finally:
        await world.done()
        await cleanup([], [visitor])


async def test_the_flip_check_says_which_accounts_will_be_shown(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        await world.author.patch("/me", json={"display_name": "Ada Author"})
        check = await world.author.get(f"/tenants/{world.repository}/flip-check")
        assert check.json()["publishers"] == [{"display_name": "Ada Author"}]
    finally:
        await world.done()


# --- The report link ----------------------------------------------------------------------------


async def test_the_storefront_carries_a_mailto_to_the_report_address_only_where_one_is_set(
    raw_client: AsyncClient,
    fake_jwks_server: FakeJwksServer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = await _public_world(raw_client, fake_jwks_server)
    visitor = await make_actor(raw_client, fake_jwks_server, "visitor", roles=())
    try:
        url = f"/discover/repositories/{world.repository}"
        monkeypatch.setattr(get_settings(), "report_address", None)
        assert (await visitor.get(url)).json()["report_mailto"] is None

        monkeypatch.setattr(get_settings(), "report_address", "reports@example.org")
        mailto = (await visitor.get(url)).json()["report_mailto"]
        parts = urlsplit(mailto)
        assert (parts.scheme, parts.path) == ("mailto", "reports@example.org")
        subject = parse_qs(parts.query)["subject"][0]
        assert "Armoury" in subject and str(world.repository) in subject
        assert "&" not in parts.query and " " not in mailto

        # A name with characters a mailto cares about stays in the subject.
        await world.author.patch(f"/tenants/{world.repository}", json={"name": "Tom & Jerry's #1"})
        again = (await visitor.get(url)).json()["report_mailto"]
        assert parse_qs(urlsplit(again).query)["subject"][0].count("Tom & Jerry's #1") == 1
        assert "Tom & Jerry's #1" not in unquote(urlsplit(again).path)
    finally:
        await world.done()
        await cleanup([], [visitor])


# --- The terms line -----------------------------------------------------------------------------


async def _terms_entries(world: ReleaseWorld) -> list[AuditLog]:
    async with admin_session_factory() as session:
        return list(
            await session.scalars(
                select(AuditLog).where(
                    AuditLog.tenant_id == world.repository,
                    AuditLog.action == "repository.terms_accepted",
                )
            )
        )


async def test_going_public_needs_the_terms_accepted_and_logs_that_they_were(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        url = f"/tenants/{world.repository}/public"
        for body in (None, {"summary": "Every blade there is"}, {"accept_terms": False}):
            refused = (
                await world.author.put(url, json=body) if body else await world.author.put(url)
            )
            assert refused.status_code == 422, refused.text
            assert refused.json()["type"] == "terms-not-accepted"
            assert "tenant" not in (refused.json()["title"] + refused.json()["detail"]).lower()
        # Nothing was kept: still private, no summary, nothing logged.
        profile = (await world.author.get(f"/tenants/{world.repository}/profile")).json()
        assert (profile["visibility"], profile["summary"]) == ("private", "")
        assert await _terms_entries(world) == []

        accepted = await world.author.put(
            url, json={"accept_terms": True, "summary": "Every blade there is"}
        )
        assert accepted.status_code == 200, accepted.text
        (entry,) = await _terms_entries(world)
        # Who agreed, and no wording: the wording is the dialog's, and may change.
        assert (entry.actor_id, entry.target_id, entry.detail) == (
            world.author.user_id,
            world.repository,
            None,
        )
    finally:
        await world.done()


async def test_a_flip_that_is_refused_for_something_else_logs_no_agreement(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer, enabled: None
) -> None:
    world = await release_world(raw_client, fake_jwks_server)
    try:
        refused = await world.author.put(
            f"/tenants/{world.repository}/public", json={"accept_terms": True, "summary": "  "}
        )
        assert refused.json()["type"] == "public-repository-summary-required"
        assert await _terms_entries(world) == []
    finally:
        await world.done()
