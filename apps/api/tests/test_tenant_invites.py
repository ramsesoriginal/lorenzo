"""The invite links of a library or repository (ADR 0211): an Owner's role links (Author,
Organizer) and library-access links, through the real HTTP API. Redeeming them is
test_invite_kinds_redemption.py; the table's own rules are at the end.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from _admin_db import admin_session_factory
from _author_world import World, make_world
from _fake_jwks import FakeJwksServer
from _invite_helpers import (  # noqa: F401
    _fresh_rate_limiter,
    in_days,
    mint,
)
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from lorenzo_api.invites import hash_token
from lorenzo_api.models import AuditLog, Invite, InviteKind, InviteRole


@pytest.fixture
async def world(
    request: pytest.FixtureRequest, raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> AsyncGenerator[World]:
    """A library or a repository, as the test says: parametrized with `indirect=True`."""
    built = await make_world(raw_client, fake_jwks_server, kind=request.param, name="World")
    yield built
    await built.clean_up()


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


# --- Making a role link ---------------------------------------------------------------------


@pytest.mark.parametrize("world", ["play", "repository"], indirect=True)
async def test_an_owner_makes_an_author_link_in_either_kind_of_tenant(world: World) -> None:
    created = await mint(world.owner, world.tenant_id, kind="tenant_role", role="author")

    assert created["kind"] == "tenant_role"
    assert created["role"] == "author"
    assert created["campaign_id"] is None
    assert created["max_uses"] == 1  # single use unless asked for more
    assert created["use_count"] == 0
    assert created["is_active"] is True
    assert isinstance(created["token"], str) and len(created["token"]) >= 40
    # Short-lived by default: three days.
    lifetime = datetime.fromisoformat(str(created["expires_at"])) - datetime.now(tz=UTC)
    assert timedelta(days=2.9) < lifetime <= timedelta(days=3)


async def test_the_token_is_shown_once_and_only_its_hash_is_stored(library: World) -> None:
    created = await mint(library.owner, library.tenant_id, kind="tenant_role", role="orga")
    token = created["token"]
    assert isinstance(token, str)

    listed = (await library.owner.get(f"/tenants/{library.tenant_id}/invites")).json()["items"]
    assert [i["id"] for i in listed] == [created["id"]]
    assert "token" not in listed[0]
    assert token not in str(listed)

    async with admin_session_factory() as session:
        stored = await session.get_one(Invite, uuid.UUID(str(created["id"])))
    assert stored.token_hash == hash_token(token)
    assert stored.token_hash != token


async def test_an_author_link_may_be_raised_to_a_small_team_and_never_to_unlimited(
    library: World,
) -> None:
    owner, tenant_id = library.owner, library.tenant_id
    assert (await mint(owner, tenant_id, kind="tenant_role", role="author", max_uses=5))[
        "max_uses"
    ] == 5
    assert (await mint(owner, tenant_id, kind="tenant_role", role="author", max_uses=10))[
        "max_uses"
    ] == 10
    for refused in (11, 0, -1):
        response = await owner.post(
            f"/tenants/{tenant_id}/invites",
            json={"kind": "tenant_role", "role": "author", "max_uses": refused},
        )
        assert response.status_code == 422, refused


async def test_an_organizer_link_is_single_use_and_cannot_be_raised(library: World) -> None:
    owner, tenant_id = library.owner, library.tenant_id
    assert (await mint(owner, tenant_id, kind="tenant_role", role="orga"))["max_uses"] == 1
    assert (await mint(owner, tenant_id, kind="tenant_role", role="orga", max_uses=1))[
        "max_uses"
    ] == 1
    response = await owner.post(
        f"/tenants/{tenant_id}/invites",
        json={"kind": "tenant_role", "role": "orga", "max_uses": 2},
    )
    assert response.status_code == 422


async def test_no_link_ever_makes_an_owner(library: World) -> None:
    owner, tenant_id = library.owner, library.tenant_id
    for body in (
        {"kind": "tenant_role", "role": "owner"},
        {"kind": "tenant_role", "role": "gm"},
        {"kind": "tenant_role", "role": "player"},
        {"kind": "tenant_role"},
        {"kind": "tenant_role", "role": None},
        {"kind": "campaign", "role": "author"},
    ):
        response = await owner.post(f"/tenants/{tenant_id}/invites", json=body)
        assert response.status_code == 422, body
    assert (await owner.get(f"/tenants/{tenant_id}/invites")).json()["items"] == []


async def test_the_lifetimes_are_bounded_per_kind(library: World, repository: World) -> None:
    owner, tenant_id = library.owner, library.tenant_id
    # A role link lives at most seven days.
    for days, status in ((6.9, 201), (7.1, 422), (30, 422), (-1, 422)):
        response = await owner.post(
            f"/tenants/{tenant_id}/invites",
            json={"kind": "tenant_role", "role": "author", "expires_at": in_days(days)},
        )
        assert response.status_code == status, days
    # A library link as long as a player link: thirty days.
    for days, status in ((29.9, 201), (30.1, 422), (-1, 422)):
        response = await repository.owner.post(
            f"/tenants/{repository.tenant_id}/invites",
            json={"kind": "library_access", "expires_at": in_days(days)},
        )
        assert response.status_code == status, days


# --- Making a library-access link ---------------------------------------------------------


async def test_a_library_link_is_for_a_repository_and_single_use_by_default(
    repository: World,
) -> None:
    created = await mint(repository.owner, repository.tenant_id, kind="library_access")
    assert created["kind"] == "library_access"
    assert created["role"] is None
    assert created["campaign_id"] is None
    assert created["max_uses"] == 1
    raised = await mint(repository.owner, repository.tenant_id, kind="library_access", max_uses=4)
    assert raised["max_uses"] == 4


async def test_a_library_cannot_make_one(library: World) -> None:
    response = await library.owner.post(
        f"/tenants/{library.tenant_id}/invites", json={"kind": "library_access"}
    )
    assert response.status_code == 409
    assert response.json()["type"] == "not-a-repository"


async def test_a_library_link_takes_no_role(repository: World) -> None:
    response = await repository.owner.post(
        f"/tenants/{repository.tenant_id}/invites",
        json={"kind": "library_access", "role": "author"},
    )
    assert response.status_code == 422


# --- Who may --------------------------------------------------------------------------------


@pytest.mark.parametrize("world", ["play", "repository"], indirect=True)
async def test_only_an_owner_makes_lists_or_revokes_a_link(world: World) -> None:
    url = f"/tenants/{world.tenant_id}/invites"
    body = {"kind": "tenant_role", "role": "author"}
    made = await mint(world.owner, world.tenant_id, **body)

    for who in (world.orga, world.author):
        assert (await who.post(url, json=body)).status_code == 403
        assert (await who.get(url)).status_code == 403
        assert (await who.delete(f"{url}/{made['id']}")).status_code == 403
    # Not a member: the usual 404, which says nothing of the tenant.
    assert (await world.outsider.post(url, json=body)).status_code == 404
    assert (await world.outsider.get(url)).status_code == 404
    assert (await world.outsider.delete(f"{url}/{made['id']}")).status_code == 404
    # The link is untouched.
    assert [i["is_active"] for i in (await world.owner.get(url)).json()["items"]] == [True]


async def test_one_tenants_links_are_not_anothers(library: World, repository: World) -> None:
    made = await mint(library.owner, library.tenant_id, kind="tenant_role", role="author")
    # The other tenant's Owner cannot see it, or revoke it by naming it in their own tenant.
    assert (await repository.owner.get(f"/tenants/{repository.tenant_id}/invites")).json()[
        "items"
    ] == []
    gone = await repository.owner.delete(f"/tenants/{repository.tenant_id}/invites/{made['id']}")
    assert gone.status_code == 404
    assert (await library.owner.get(f"/tenants/{library.tenant_id}/invites")).json()["items"][0][
        "is_active"
    ] is True


async def test_a_campaigns_links_are_not_listed_with_the_tenants(library: World) -> None:
    campaign = await library.owner.post(
        f"/tenants/{library.tenant_id}/campaigns",
        json={"name": "Open", "game_system": "5e", "slug": "open", "description": ""},
    )
    assert campaign.status_code == 201, campaign.text
    invite = await library.owner.post(
        f"/tenants/{library.tenant_id}/campaigns/{campaign.json()['id']}/invites",
        json={"expires_at": in_days(3)},
    )
    assert invite.status_code == 201, invite.text
    assert invite.json()["kind"] == "campaign"
    assert (await library.owner.get(f"/tenants/{library.tenant_id}/invites")).json()["items"] == []
    refused = await library.owner.delete(
        f"/tenants/{library.tenant_id}/invites/{invite.json()['id']}"
    )
    assert refused.status_code == 404


# --- Revoking, and the log ----------------------------------------------------------------


async def test_revoking_is_instant_idempotent_and_logged_once(library: World) -> None:
    owner, tenant_id = library.owner, library.tenant_id
    made = await mint(owner, tenant_id, kind="tenant_role", role="author")
    url = f"/tenants/{tenant_id}/invites/{made['id']}"

    assert (await owner.delete(url)).status_code == 204
    assert (await owner.delete(url)).status_code == 204
    listed = (await owner.get(f"/tenants/{tenant_id}/invites")).json()["items"]
    assert listed[0]["revoked_at"] is not None
    assert listed[0]["is_active"] is False
    assert (await owner.delete(f"/tenants/{tenant_id}/invites/{uuid.uuid4()}")).status_code == 404

    async with admin_session_factory() as session:
        actions = (
            await session.scalars(
                select(AuditLog.action)
                .where(AuditLog.tenant_id == tenant_id, AuditLog.target_id == uuid.UUID(made["id"]))
                .order_by(AuditLog.created_at)
            )
        ).all()
    assert actions == ["invite.created", "invite.revoked"]


async def test_the_log_says_what_was_made_and_never_the_token(library: World) -> None:
    made = await mint(library.owner, library.tenant_id, kind="tenant_role", role="author")
    async with admin_session_factory() as session:
        entry = (
            await session.scalars(
                select(AuditLog).where(
                    AuditLog.tenant_id == library.tenant_id, AuditLog.action == "invite.created"
                )
            )
        ).one()
    assert entry.actor_id == library.owner.user_id
    assert entry.detail is not None
    assert entry.detail.startswith("kind=tenant_role, role=author, expires_at=")
    assert "max_uses=1" in entry.detail
    assert str(made["token"]) not in entry.detail


# --- The table's own rules ----------------------------------------------------------------


async def _insert(tenant_id: uuid.UUID, **fields: object) -> None:
    async with admin_session_factory() as session:
        defaults: dict[str, object] = {
            "tenant_id": tenant_id,
            "token_hash": hash_token(str(uuid.uuid4())),
            "expires_at": datetime.now(tz=UTC) + timedelta(days=1),
        }
        session.add(Invite(**{**defaults, **fields}))
        await session.commit()


@pytest.mark.parametrize(
    "fields",
    [
        # A campaign link needs its campaign, and says player or gm.
        {"kind": InviteKind.CAMPAIGN, "campaign_id": None, "role": InviteRole.PLAYER},
        # A role link has no campaign and says author or orga.
        {"kind": InviteKind.TENANT_ROLE, "role": InviteRole.PLAYER, "max_uses": 1},
        {"kind": InviteKind.TENANT_ROLE, "role": InviteRole.GM, "max_uses": 1},
        {"kind": InviteKind.TENANT_ROLE, "role": None, "max_uses": 1},
        # A library link has neither a campaign nor a role.
        {"kind": InviteKind.LIBRARY_ACCESS, "role": InviteRole.AUTHOR, "max_uses": 1},
        # A link that is not for a campaign is always capped.
        {"kind": InviteKind.TENANT_ROLE, "role": InviteRole.AUTHOR, "max_uses": None},
        {"kind": InviteKind.LIBRARY_ACCESS, "role": None, "max_uses": None},
    ],
)
async def test_the_table_refuses_a_link_that_does_not_fit_its_kind(
    library: World, fields: dict[str, object]
) -> None:
    with pytest.raises(IntegrityError):
        await _insert(library.tenant_id, **fields)


async def test_the_table_takes_the_three_shapes(library: World) -> None:
    await _insert(library.tenant_id, kind=InviteKind.TENANT_ROLE, role=InviteRole.ORGA, max_uses=1)
    await _insert(library.tenant_id, kind=InviteKind.LIBRARY_ACCESS, role=None, max_uses=3)
