"""Redeeming the invite links of a library or repository (ADR 0220), through the public routes with
real verified tokens: what a visitor sees before they accept, a role link, a library-access link,
and that a dead link is the same answer in every kind.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import AsyncGenerator

import pytest
from _admin_db import admin_session_factory
from _author_world import World, make_world
from _fake_jwks import FakeJwksServer
from _invite_helpers import (  # noqa: F401
    _fresh_rate_limiter,
    end,
    mint,
    mint_library,
    mint_role,
    preview,
    redeem,
    use_count,
)
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog, Membership, Player

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fake-png-content"


@pytest.fixture
async def library(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> AsyncGenerator[World]:
    world = await make_world(raw_client, fake_jwks_server, name="A table")
    yield world
    await world.clean_up()


@pytest.fixture
async def repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> AsyncGenerator[World]:
    world = await make_world(raw_client, fake_jwks_server, kind="repository", name="Faerûn")
    yield world
    await world.clean_up()


@pytest.fixture
async def newcomers(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> AsyncGenerator[list[Actor]]:
    people = [
        await make_actor(raw_client, fake_jwks_server, f"newcomer{i}", roles=()) for i in range(3)
    ]
    yield people
    await cleanup([], people)


async def _notices(actor: Actor) -> list[dict[str, str]]:
    response = await actor.get("/me/notifications")
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


async def _role_of(actor: Actor, tenant_id: uuid.UUID) -> str | None:
    me = (await actor.get("/me")).json()
    return next((m["role"] for m in me["memberships"] if m["tenant_id"] == str(tenant_id)), None)


async def _log(tenant_id: uuid.UUID) -> list[tuple[str, uuid.UUID | None, str | None]]:
    async with admin_session_factory() as session:
        rows = (
            await session.execute(
                select(AuditLog.action, AuditLog.actor_id, AuditLog.detail)
                .where(AuditLog.tenant_id == tenant_id)
                .order_by(AuditLog.created_at)
            )
        ).all()
    return [(a, b, c) for a, b, c in rows]


# --- What a visitor sees before they accept ---------------------------------------------------


async def test_the_preview_of_a_role_link_says_the_name_the_kind_and_the_role(
    raw_client: AsyncClient, library: World, repository: World
) -> None:
    author = await mint_role(library.owner, library.tenant_id, "author")
    organizer = await mint_role(repository.owner, repository.tenant_id, "orga")

    assert await preview(raw_client, author) == (
        200,
        {
            "kind": "tenant_role",
            "name": "A table",
            "campaign_name": None,
            "tenant_kind": "play",
            "picture_url": None,
            "role": "author",
        },
    )
    assert await preview(raw_client, organizer) == (
        200,
        {
            "kind": "tenant_role",
            "name": "Faerûn",
            "campaign_name": None,
            "tenant_kind": "repository",
            "picture_url": None,
            "role": "orga",
        },
    )


async def test_the_preview_of_a_library_link_names_the_repository_and_no_role(
    raw_client: AsyncClient, repository: World
) -> None:
    token = await mint_library(repository.owner, repository.tenant_id)
    assert await preview(raw_client, token) == (
        200,
        {
            "kind": "library_access",
            "name": "Faerûn",
            "campaign_name": None,
            "tenant_kind": "repository",
            "picture_url": None,
            "role": None,
        },
    )


async def test_a_visitor_learns_nothing_but_what_they_are_asked(
    raw_client: AsyncClient, library: World
) -> None:
    """No id, no member, no count: a leaked link shows a name, a kind and a role."""
    await mint_role(library.owner, library.tenant_id, "author")
    token = await mint_role(library.owner, library.tenant_id, "author", max_uses=5)
    response = await raw_client.get(f"/invites/{token}")
    assert response.status_code == 200
    assert set(response.json()) == {
        "kind",
        "name",
        "campaign_name",
        "tenant_kind",
        "picture_url",
        "role",
    }
    text = response.text
    for secret in (
        str(library.tenant_id),
        str(library.owner.user_id),
        str(library.orga.user_id),
        str(library.author.user_id),
    ):
        assert secret not in text
    assert re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-", text) is None


async def test_the_preview_carries_the_tenants_picture_when_it_has_one(
    raw_client: AsyncClient, library: World
) -> None:
    uploaded = await library.owner.put(
        f"/tenants/{library.tenant_id}/picture", files={"file": ("a.png", _PNG_BYTES, "image/png")}
    )
    assert uploaded.status_code == 204, uploaded.text
    token = await mint_role(library.owner, library.tenant_id, "author")

    status, shown = await preview(raw_client, token)
    assert status == 200
    url = str(shown["picture_url"])
    assert url.endswith(f"/tenants/{library.tenant_id}/picture")
    # What the visitor's browser then fetches, with no login.
    served = await raw_client.get(f"/tenants/{library.tenant_id}/picture")
    assert served.status_code == 200


@pytest.mark.parametrize("kind", ["author", "orga", "library"])
async def test_every_dead_link_is_the_same_answer_whatever_the_kind(
    raw_client: AsyncClient, repository: World, newcomers: list[Actor], kind: str
) -> None:
    async def make() -> tuple[str, str]:
        if kind == "library":
            created = await mint(repository.owner, repository.tenant_id, kind="library_access")
        else:
            created = await mint(
                repository.owner, repository.tenant_id, kind="tenant_role", role=kind
            )
        return str(created["token"]), str(created["id"])

    unknown = ("not-a-token-" + uuid.uuid4().hex) * 2
    revoked, revoked_id = await make()
    await repository.owner.delete(f"/tenants/{repository.tenant_id}/invites/{revoked_id}")
    expired, expired_id = await make()
    await end(expired_id, "expired")
    used_up, used_id = await make()
    await end(used_id, "used up")

    answers = set()
    for token in (unknown, revoked, expired, used_up):
        previewed = await raw_client.get(f"/invites/{token}")
        redeemed = await newcomers[0].post(
            f"/invites/{token}/redeem",
            **({"json": {"library_id": str(uuid.uuid4())}} if kind == "library" else {}),
        )
        assert previewed.status_code == 404
        assert redeemed.status_code == 404
        answers.add((previewed.text, redeemed.text))
    assert len(answers) == 1


# --- A role link ------------------------------------------------------------------------------


async def test_an_author_link_makes_an_author_and_tells_only_the_owners(
    library: World, newcomers: list[Actor]
) -> None:
    nia, other, _ = newcomers
    assert (await nia.patch("/me", json={"display_name": "Nia"})).status_code == 200
    created = await mint(library.owner, library.tenant_id, kind="tenant_role", role="author")
    token = str(created["token"])
    before = {name: len(await _notices(getattr(library, name))) for name in ("owner", "orga")}

    status, joined = await redeem(nia, token)

    assert status == 201, joined
    assert joined == {
        "kind": "tenant_role",
        "tenant_id": str(library.tenant_id),
        "campaign_id": None,
        "role": "author",
        "player_id": None,
        "library_id": None,
        "already_joined": False,
    }
    assert await _role_of(nia, library.tenant_id) == "author"
    assert await use_count(str(created["id"])) == 1
    # Attributed to whoever made the link, as an added person is.
    async with admin_session_factory() as session:
        membership = await session.get_one(Membership, (library.tenant_id, nia.user_id))
    assert membership.created_by == library.owner.user_id
    # No player seat, no campaign: a role link makes a role and nothing else.
    async with admin_session_factory() as session:
        assert (
            await session.scalars(select(Player).where(Player.user_id == nia.user_id))
        ).all() == []

    # The Owner is told, in words. The Organizer is not.
    notice = (await _notices(library.owner))[0]
    assert notice["type"] == "invite_role_redeemed"
    assert notice["title"] == "Nia joined A table as an Author"
    assert "library" in notice["body"] and "A table" in notice["body"]
    assert len(await _notices(library.orga)) == before["orga"]
    assert len(await _notices(library.owner)) == before["owner"] + 1

    # The redeemer is the actor in the log.
    entries = await _log(library.tenant_id)
    assert (
        "invite.redeemed",
        nia.user_id,
        f"kind=tenant_role, role=author, member={nia.user_id}",
    ) in entries

    # Single use: the next person is told the link is dead, and gets nothing.
    assert (await redeem(other, token))[0] == 404
    assert await _role_of(other, library.tenant_id) is None


async def test_an_organizer_link_makes_an_organizer_of_a_repository(
    repository: World, newcomers: list[Actor]
) -> None:
    token = await mint_role(repository.owner, repository.tenant_id, "orga")
    status, joined = await redeem(newcomers[0], token)
    assert status == 201, joined
    assert joined["role"] == "orga"
    assert await _role_of(newcomers[0], repository.tenant_id) == "orga"
    assert (
        await newcomers[0].get(f"/tenants/{repository.tenant_id}/memberships")
    ).status_code == 200
    notice = (await _notices(repository.owner))[0]
    assert notice["title"].endswith("joined Faerûn as an Organizer")
    assert "repository" in notice["body"]


async def test_a_link_for_a_small_team_admits_up_to_its_cap_and_counts(
    library: World, newcomers: list[Actor]
) -> None:
    created = await mint(
        library.owner, library.tenant_id, kind="tenant_role", role="author", max_uses=2
    )
    token = str(created["token"])
    assert (await redeem(newcomers[0], token))[0] == 201
    assert (await redeem(newcomers[1], token))[0] == 201
    assert (await redeem(newcomers[2], token))[0] == 404
    assert await use_count(str(created["id"])) == 2
    assert await _role_of(newcomers[2], library.tenant_id) is None
    listed = (await library.owner.get(f"/tenants/{library.tenant_id}/invites")).json()["items"]
    assert listed[0]["use_count"] == 2
    assert listed[0]["is_active"] is False


async def test_a_link_never_changes_a_role_someone_already_has(library: World) -> None:
    """Changing a role is People's job, by an Owner: a link can neither raise nor lower one."""
    author_link = await mint(library.owner, library.tenant_id, kind="tenant_role", role="author")
    organizer_link = await mint(library.owner, library.tenant_id, kind="tenant_role", role="orga")
    cases = [
        (library.owner, str(author_link["token"]), "owner"),
        (library.orga, str(author_link["token"]), "orga"),
        (library.author, str(organizer_link["token"]), "author"),
        (library.owner, str(organizer_link["token"]), "owner"),
    ]
    for actor, token, role in cases:
        status, body = await redeem(actor, token)
        assert status == 200, body
        assert body["already_joined"] is True
        assert await _role_of(actor, library.tenant_id) == role
    assert await use_count(str(author_link["id"])) == 0
    assert await use_count(str(organizer_link["id"])) == 0


async def test_redeeming_needs_a_login(raw_client: AsyncClient, library: World) -> None:
    token = await mint_role(library.owner, library.tenant_id, "author")
    response = await raw_client.post(f"/invites/{token}/redeem")  # no Authorization header
    assert response.status_code in (401, 403)


async def test_a_revoked_role_link_gives_nothing(library: World, newcomers: list[Actor]) -> None:
    created = await mint(library.owner, library.tenant_id, kind="tenant_role", role="author")
    await library.owner.delete(f"/tenants/{library.tenant_id}/invites/{created['id']}")
    assert (await redeem(newcomers[0], str(created["token"])))[0] == 404
    assert await _role_of(newcomers[0], library.tenant_id) is None


async def test_two_people_racing_for_one_single_use_link_get_one_role(
    library: World, newcomers: list[Actor]
) -> None:
    created = await mint(library.owner, library.tenant_id, kind="tenant_role", role="author")
    token = str(created["token"])
    results = await asyncio.gather(redeem(newcomers[0], token), redeem(newcomers[1], token))
    assert sorted(status for status, _ in results) == [201, 404]
    assert await use_count(str(created["id"])) == 1
    roles = [await _role_of(person, library.tenant_id) for person in newcomers[:2]]
    assert sorted(str(r) for r in roles) == ["None", "author"]


# --- A library-access link ---------------------------------------------------------------------


async def test_a_library_link_shares_the_repository_with_the_library_its_redeemer_owns(
    repository: World, library: World
) -> None:
    created = await mint(repository.owner, repository.tenant_id, kind="library_access")
    token = str(created["token"])
    # The Owner of the library redeems it. Nobody at the repository named the library's id.
    status, joined = await redeem(library.owner, token, library.tenant_id)

    assert status == 201, joined
    assert joined == {
        "kind": "library_access",
        "tenant_id": str(repository.tenant_id),
        "campaign_id": None,
        "role": None,
        "player_id": None,
        "library_id": str(library.tenant_id),
        "already_joined": False,
    }
    assert await use_count(str(created["id"])) == 1

    # The same grant an Owner naming the library would make.
    subscribers = (
        await repository.owner.get(f"/tenants/{repository.tenant_id}/subscribers")
    ).json()
    assert [s["tenant_id"] for s in subscribers["items"]] == [str(library.tenant_id)]
    held = (await library.owner.get(f"/tenants/{library.tenant_id}/repositories")).json()["items"]
    assert [r["repository"]["id"] for r in held] == [str(repository.tenant_id)]

    # The library's Owner and Organizer are told, as a direct grant tells them; its Author is not.
    for actor in (library.owner, library.orga):
        types = [n["type"] for n in await _notices(actor)]
        assert "repository_granted" in types
    assert "repository_granted" not in [n["type"] for n in await _notices(library.author)]
    # So is the repository's Owner, who did not do it.
    notice = (await _notices(repository.owner))[0]
    assert notice["type"] == "invite_library_redeemed"
    assert notice["title"] == "Someone shared Faerûn with A table"

    actions = [(a, who) for a, who, _ in await _log(repository.tenant_id)]
    assert ("repository.granted", library.owner.user_id) in actions
    assert ("invite.redeemed", library.owner.user_id) in actions


async def test_a_library_link_needs_the_library_in_the_body_and_spends_nothing_without_it(
    repository: World, library: World
) -> None:
    created = await mint(repository.owner, repository.tenant_id, kind="library_access")
    token = str(created["token"])

    status, problem = await redeem(library.owner, token)
    assert status == 422
    assert problem["type"] == "invite-library-required"
    assert await use_count(str(created["id"])) == 0

    assert (await redeem(library.owner, token, library.tenant_id))[0] == 201


async def test_a_library_link_is_redeemed_for_a_library_you_own_and_for_no_other(
    repository: World, library: World, newcomers: list[Actor]
) -> None:
    created = await mint(repository.owner, repository.tenant_id, kind="library_access", max_uses=5)
    token = str(created["token"])
    answers = []
    for actor, chosen in (
        (library.orga, library.tenant_id),  # an Organizer of it, not an Owner
        (library.author, library.tenant_id),
        (newcomers[0], library.tenant_id),  # nothing to do with it
        (newcomers[0], uuid.uuid4()),  # a library that does not exist
        (library.owner, repository.tenant_id),  # the repository itself
    ):
        status, problem = await redeem(actor, token, chosen)
        assert status == 422, (actor, chosen, problem)
        answers.append(problem["type"])
    assert set(answers) == {"invalid-invite-library"}
    # Not a word of which libraries exist: a missing library and someone else's read the same.
    assert await use_count(str(created["id"])) == 0
    assert (await repository.owner.get(f"/tenants/{repository.tenant_id}/subscribers")).json()[
        "items"
    ] == []


async def test_a_library_link_is_idempotent_for_a_library_that_already_holds_the_grant(
    repository: World, library: World
) -> None:
    created = await mint(repository.owner, repository.tenant_id, kind="library_access", max_uses=3)
    token = str(created["token"])
    assert (await redeem(library.owner, token, library.tenant_id))[0] == 201
    status, again = await redeem(library.owner, token, library.tenant_id)
    assert status == 200
    assert again["already_joined"] is True
    assert await use_count(str(created["id"])) == 1  # nothing spent the second time
    notices = [
        n for n in await _notices(repository.owner) if n["type"] == "invite_library_redeemed"
    ]
    assert len(notices) == 1


async def test_a_library_link_is_single_use_by_default(
    repository: World, library: World, raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    token = await mint_library(repository.owner, repository.tenant_id)
    other = await make_actor(raw_client, fake_jwks_server, "other-owner")
    other_library = await other.create_tenant("Elsewhere")
    try:
        assert (await redeem(library.owner, token, library.tenant_id))[0] == 201
        assert (await redeem(other, token, other_library))[0] == 404
    finally:
        await cleanup([other_library], [other])


async def test_a_bridge_can_be_shared_with_by_the_owner_of_another_repository(
    repository: World, raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The tenant to share with may be a repository the redeemer owns: a bridge is built on one."""
    builder = await make_actor(raw_client, fake_jwks_server, "builder")
    bridge = await builder.create_tenant("A bridge", kind="repository")
    try:
        token = await mint_library(repository.owner, repository.tenant_id)
        status, joined = await redeem(builder, token, bridge)
        assert status == 201, joined
        subscribers = (
            await repository.owner.get(f"/tenants/{repository.tenant_id}/subscribers")
        ).json()["items"]
        assert [s["tenant_id"] for s in subscribers] == [str(bridge)]
    finally:
        await cleanup([bridge], [builder])


async def test_a_revoked_library_link_shares_nothing(repository: World, library: World) -> None:
    created = await mint(repository.owner, repository.tenant_id, kind="library_access")
    await repository.owner.delete(f"/tenants/{repository.tenant_id}/invites/{created['id']}")
    assert (await redeem(library.owner, str(created["token"]), library.tenant_id))[0] == 404
    assert (await repository.owner.get(f"/tenants/{repository.tenant_id}/subscribers")).json()[
        "items"
    ] == []


async def test_one_tenants_link_cannot_be_used_to_reach_another(
    repository: World, library: World, newcomers: list[Actor]
) -> None:
    """A role link is for its own tenant only: the membership it makes is there and nowhere else."""
    token = await mint_role(library.owner, library.tenant_id, "author")
    assert (await redeem(newcomers[0], token))[0] == 201
    assert await _role_of(newcomers[0], library.tenant_id) == "author"
    assert await _role_of(newcomers[0], repository.tenant_id) is None
    assert (
        await newcomers[0].get(f"/tenants/{repository.tenant_id}/stat-groups")
    ).status_code == 404
