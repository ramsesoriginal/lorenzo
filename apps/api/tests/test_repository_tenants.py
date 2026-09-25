"""ADR 0118, first half: what makes a tenant a repository - an immutable
`kind`, no campaigns, and a published/draft state only its owners set.
"""

import uuid

import pytest
from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup, make_actor
from conftest import make_campaign
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from lorenzo_api.models import AuditLog, Membership, MembershipRole


async def test_tenants_are_for_play_unless_created_as_repositories(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    play_id = await author.create_tenant("My Table")
    repository_id = await author.create_tenant("Faerûn", kind="repository")
    try:
        play = (await author.get(f"/tenants/{play_id}")).json()
        repository = (await author.get(f"/tenants/{repository_id}")).json()
        assert (play["kind"], play["published_at"]) == ("play", None)
        assert (repository["kind"], repository["published_at"]) == ("repository", None)

        listed = (await author.get("/tenants")).json()["items"]
        assert {item["id"]: item["kind"] for item in listed} == {
            str(play_id): "play",
            str(repository_id): "repository",
        }
        only_play = (await author.get("/tenants", params={"kind": "play"})).json()["items"]
        assert [item["id"] for item in only_play] == [str(play_id)]

        managed = (await author.get("/me/managed")).json()["tenants"]
        assert {t["tenant_id"]: t["kind"] for t in managed} == {
            str(play_id): "play",
            str(repository_id): "repository",
        }
    finally:
        await cleanup([play_id, repository_id], [author])


async def test_kind_never_changes(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    tenant_id = await author.create_tenant("My Table")
    try:
        # PATCH doesn't accept it at all...
        response = await author.patch(f"/tenants/{tenant_id}", json={"kind": "repository"})
        assert response.status_code == 200
        assert response.json()["kind"] == "play"
        # ...and the database refuses it even from the privileged role.
        async with admin_session_factory() as session:
            with pytest.raises(DBAPIError, match="tenant.kind can't change"):
                await session.execute(
                    text("UPDATE tenant SET kind = 'repository' WHERE id = :t"), {"t": tenant_id}
                )
    finally:
        await cleanup([tenant_id], [author])


async def test_a_repository_holds_no_campaigns(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    repository_id = await author.create_tenant("Faerûn", kind="repository")
    try:
        response = await author.post(
            f"/tenants/{repository_id}/campaigns",
            json={"name": "Nope", "game_system": "D&D 5e", "slug": "nope", "description": ""},
        )
        assert response.status_code == 409
        assert response.json()["type"] == "repository-has-no-campaigns"

        async with admin_session_factory() as session:
            with pytest.raises(DBAPIError, match="a repository holds no campaigns"):
                await make_campaign(session, tenant_id=repository_id)
    finally:
        await cleanup([repository_id], [author])


async def test_owners_publish_and_withdraw_a_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    repository_id = await author.create_tenant("Faerûn", kind="repository")
    play_id = await author.create_tenant("My Table")
    async with admin_session_factory() as session:
        session.add(
            Membership(tenant_id=repository_id, user_id=orga.user_id, role=MembershipRole.ORGA)
        )
        await session.commit()
    try:
        response = await orga.put(f"/tenants/{repository_id}/published")
        assert response.status_code == 403
        assert response.json()["type"] == "repository-management-forbidden"

        response = await author.put(f"/tenants/{play_id}/published")
        assert response.status_code == 409
        assert response.json()["type"] == "not-a-repository"

        first = await author.put(f"/tenants/{repository_id}/published")
        assert first.status_code == 200
        assert first.json()["published_at"] is not None
        again = await author.put(f"/tenants/{repository_id}/published")
        assert again.json()["published_at"] > first.json()["published_at"]

        withdrawn = await author.delete(f"/tenants/{repository_id}/published")
        assert withdrawn.status_code == 200
        assert withdrawn.json()["published_at"] is None

        async with admin_session_factory() as session:
            actions = (
                await session.scalars(
                    select(AuditLog.action)
                    .where(AuditLog.tenant_id == repository_id)
                    .order_by(AuditLog.created_at)
                )
            ).all()
        assert actions == [
            "repository.published",
            "repository.published",
            "repository.unpublished",
        ]
    finally:
        await cleanup([repository_id, play_id], [author, orga])


async def test_only_a_repository_can_carry_published_at() -> None:
    async with admin_session_factory() as session:
        with pytest.raises(DBAPIError, match="tenant_only_repositories_publish"):
            await session.execute(
                text("INSERT INTO tenant (published_at) VALUES (now())"),
            )


async def test_repository_ids_are_unrelated_to_play(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A stray id can't be used to publish somebody else's repository: the
    route sits behind the ordinary tenant-membership gate."""
    author = await make_actor(raw_client, fake_jwks_server, "author")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    repository_id = await author.create_tenant("Faerûn", kind="repository")
    try:
        response = await stranger.put(f"/tenants/{repository_id}/published")
        assert response.status_code in (403, 404)
        response = await stranger.put(f"/tenants/{uuid.uuid4()}/published")
        assert response.status_code == 404
    finally:
        await cleanup([repository_id], [author, stranger])
