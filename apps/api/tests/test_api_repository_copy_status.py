"""ADR 0204 through the real HTTP API: a repository's members see which
tenants have an invitation to it or a copy of it, and for each, whether
and when it copied and last updated - including one that holds a copy
after its invitation was withdrawn - and nobody else sees any of it.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import text

from lorenzo_api.db import engine


async def _publish_with_an_item(author: Actor, repository: uuid.UUID) -> None:
    created = await author.post(
        f"/tenants/{repository}/items",
        json={"name": "Longsword", "prototype_ids": [], "in_public_catalog": False},
    )
    assert created.status_code == 201, created.text
    assert (await author.put(f"/tenants/{repository}/published")).status_code == 200


async def _copy(actor: Actor, library: uuid.UUID, repository: uuid.UUID) -> None:
    response = await actor.post(f"/tenants/{library}/repositories/{repository}/copy", json={})
    assert response.status_code == 201, response.text


async def _users(author: Actor, repository: uuid.UUID) -> dict[str, dict[str, object]]:
    response = await author.get(f"/tenants/{repository}/subscribers")
    assert response.status_code == 200, response.text
    return {entry["name"]: entry for entry in response.json()["items"]}


async def test_each_library_says_whether_it_copied_and_when(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    copier = await make_actor(raw_client, fake_jwks_server, "copier")
    waiting = await make_actor(raw_client, fake_jwks_server, "waiting")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    copied = await copier.create_tenant("Copied Table")
    invited = await waiting.create_tenant("Invited Table")
    try:
        await _publish_with_an_item(author, faerun)
        await author.put(f"/tenants/{faerun}/subscribers/{copied}")
        await author.put(f"/tenants/{faerun}/subscribers/{invited}")
        await _copy(copier, copied, faerun)

        users = await _users(author, faerun)

        assert list(users) == ["Copied Table", "Invited Table"]
        assert users["Copied Table"]["granted_at"] is not None
        assert users["Copied Table"]["copied_at"] is not None
        assert users["Copied Table"]["synced_at"] is not None
        # Invited, and has not copied it.
        assert users["Invited Table"]["granted_at"] is not None
        assert users["Invited Table"]["copied_at"] is None
        assert users["Invited Table"]["synced_at"] is None
    finally:
        await cleanup([copied, invited, faerun], [author, copier, waiting])


async def test_a_library_that_keeps_its_copy_after_the_invitation_went_is_still_listed(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    copier = await make_actor(raw_client, fake_jwks_server, "copier")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await copier.create_tenant("My Table")
    try:
        await _publish_with_an_item(author, faerun)
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await _copy(copier, table, faerun)
        assert (await author.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 204

        users = await _users(author, faerun)

        assert list(users) == ["My Table"]
        assert users["My Table"]["granted_at"] is None
        assert users["My Table"]["granted_by"] is None
        assert users["My Table"]["copied_at"] is not None
    finally:
        await cleanup([table, faerun], [author, copier])


async def test_a_tenant_with_neither_an_invitation_nor_a_copy_is_not_listed(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    other = await make_actor(raw_client, fake_jwks_server, "other")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    elsewhere = await other.create_tenant("Elsewhere")
    revoked = await other.create_tenant("Revoked Without Copying")
    try:
        await _publish_with_an_item(author, faerun)
        await author.put(f"/tenants/{faerun}/subscribers/{revoked}")
        await author.delete(f"/tenants/{faerun}/subscribers/{revoked}")

        assert await _users(author, faerun) == {}
        assert elsewhere  # a tenant that was never involved
    finally:
        await cleanup([elsewhere, revoked, faerun], [author, other])


async def test_only_the_repositorys_own_members_may_ask(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    copier = await make_actor(raw_client, fake_jwks_server, "copier")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await copier.create_tenant("My Table")
    try:
        await _publish_with_an_item(author, faerun)
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await _copy(copier, table, faerun)

        # The library that copied it is a member of its own tenant, not of the repository.
        assert (await copier.get(f"/tenants/{faerun}/subscribers")).status_code in (403, 404)
        assert (await stranger.get(f"/tenants/{faerun}/subscribers")).status_code in (403, 404)
    finally:
        await cleanup([table, faerun], [author, copier, stranger])


async def test_the_policy_shows_a_copy_to_the_repository_it_came_from_and_to_nobody_else(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """`repository_owner_read` itself, as the restricted app role: a
    `repository_copy` row is visible to its own tenant and to the tenant it
    was copied from, never to a third one, and is never writable by the
    latter."""
    author = await make_actor(raw_client, fake_jwks_server, "author")
    copier = await make_actor(raw_client, fake_jwks_server, "copier")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    other_repository = await author.create_tenant("Another", kind="repository")
    table = await copier.create_tenant("My Table")
    elsewhere = await stranger.create_tenant("Elsewhere")
    try:
        await _publish_with_an_item(author, faerun)
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await _copy(copier, table, faerun)

        async def seen_by(tenant: uuid.UUID) -> int:
            async with engine.connect() as conn, conn.begin():
                await conn.execute(
                    text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)}
                )
                return (
                    await conn.execute(
                        text("SELECT count(*) FROM repository_copy WHERE tenant_id = :t"),
                        {"t": table},
                    )
                ).scalar_one()

        assert await seen_by(table) == 1  # its own
        assert await seen_by(faerun) == 1  # the repository it came from
        assert await seen_by(other_repository) == 0  # another repository
        assert await seen_by(elsewhere) == 0  # another library

        async with engine.connect() as conn, conn.begin():
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(faerun)}
            )
            rows = (
                await conn.execute(
                    text("DELETE FROM repository_copy WHERE tenant_id = :t"), {"t": table}
                )
            ).rowcount
        assert rows == 0  # a read, not a write

        async with admin_session_factory() as session:
            still = (
                await session.execute(
                    text("SELECT count(*) FROM repository_copy WHERE tenant_id = :t"),
                    {"t": table},
                )
            ).scalar_one()
        assert still == 1
    finally:
        await cleanup([table, elsewhere, other_repository, faerun], [author, copier, stranger])
