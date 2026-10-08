"""ADR 0199 through the real HTTP API: revoking an invitation from the
repository's side tells the invited library's Owners and Organizers, and
nothing else about the two sides' notifications changes.
"""

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient

from lorenzo_api.models import Membership, MembershipRole


async def _notifications(actor: Actor) -> list[dict[str, str]]:
    response = await actor.get("/me/notifications")
    assert response.status_code == 200
    return response.json()["items"]


async def _revoked(actor: Actor) -> list[dict[str, str]]:
    return [n for n in await _notifications(actor) if n["type"] == "repository_revoked"]


async def test_revoking_tells_the_libraries_owners_and_organizers_and_nobody_else(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    repository_orga = await make_actor(raw_client, fake_jwks_server, "repository-orga")
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    player = await make_actor(raw_client, fake_jwks_server, "outsider")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await owner.create_tenant("My Table")
    elsewhere = await stranger.create_tenant("Elsewhere")
    async with admin_session_factory() as session:
        session.add_all(
            [
                Membership(
                    tenant_id=faerun, user_id=repository_orga.user_id, role=MembershipRole.ORGA
                ),
                Membership(tenant_id=table, user_id=orga.user_id, role=MembershipRole.ORGA),
            ]
        )
        await session.commit()
    try:
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await author.put(f"/tenants/{faerun}/subscribers/{elsewhere}")
        before = {
            name: len(await _notifications(actor))
            for name, actor in {
                "author": author,
                "repository_orga": repository_orga,
                "outsider": player,
                "stranger": stranger,
            }.items()
        }

        assert (await author.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 204

        for member in (owner, orga):
            [notice] = await _revoked(member)
            assert "Faerûn" in notice["title"]
            assert "your library" in notice["title"] + notice["body"]
            assert "copied" in notice["body"]
            assert "invited again" in notice["body"]
            assert "tenant" not in (notice["title"] + notice["body"]).lower()
            assert "My Table" not in notice["title"] + notice["body"]
            assert notice["scope"] == "tenant"
            assert notice["tenant_id"] == str(table)

        # Nobody else is told: not the repository's own people, not someone
        # with no standing in the library, and not another invited library.
        after = {
            "author": len(await _notifications(author)),
            "repository_orga": len(await _notifications(repository_orga)),
            "outsider": len(await _notifications(player)),
            "stranger": len(await _notifications(stranger)),
        }
        assert after == before
        assert await _revoked(author) == []
        assert await _revoked(repository_orga) == []
        assert await _revoked(player) == []
        assert await _revoked(stranger) == []
    finally:
        await cleanup(
            [table, elsewhere, faerun], [author, repository_orga, owner, orga, player, stranger]
        )


async def test_revoking_an_invitation_that_does_not_exist_tells_no_one(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await owner.create_tenant("My Table")
    try:
        missing = await author.delete(f"/tenants/{faerun}/subscribers/{table}")
        assert missing.status_code == 404
        assert await _notifications(owner) == []

        # Revoking twice tells them once.
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        assert (await author.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 204
        assert (await author.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 404
        assert len(await _revoked(owner)) == 1
    finally:
        await cleanup([table, faerun], [author, owner])


async def test_a_refused_revoke_tells_no_one_and_keeps_the_invitation(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await owner.create_tenant("My Table")
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=faerun, user_id=orga.user_id, role=MembershipRole.ORGA))
        await session.commit()
    try:
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        assert (await orga.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 403
        assert await _revoked(owner) == []
        subscribers = (await author.get(f"/tenants/{faerun}/subscribers")).json()["items"]
        assert [s["tenant_id"] for s in subscribers] == [str(table)]
    finally:
        await cleanup([table, faerun], [author, orga, owner])


async def test_a_library_giving_up_its_own_access_tells_no_one(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await owner.create_tenant("My Table")
    try:
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        authors_before = len(await _notifications(author))
        owners_before = len(await _notifications(owner))

        assert (await owner.delete(f"/tenants/{table}/repositories/{faerun}")).status_code == 204

        assert len(await _notifications(author)) == authors_before
        assert len(await _notifications(owner)) == owners_before
        assert await _revoked(owner) == []
        assert await _revoked(author) == []
    finally:
        await cleanup([table, faerun], [author, owner])
