"""ADR 0184, through the real HTTP API: DELETE /tenants/{id}. Who may, what is refused, what goes
with the tenant and who is told.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import cleanup, make_actor
from _repository_fixtures import seed_every_content_table
from conftest import make_campaign, make_character, make_player
from httpx import AsyncClient
from sqlalchemy import func, select, text

from lorenzo_api.models import (
    CampaignGm,
    Membership,
    MembershipRole,
    Notification,
    RepositorySubscription,
    Tenant,
)


async def _exists(tenant_id: uuid.UUID) -> bool:
    async with admin_session_factory() as session:
        return await session.get(Tenant, tenant_id) is not None


async def _rows_left(tenant_id: uuid.UUID) -> dict[str, int]:
    """Every table that carries a `tenant_id`, and how many rows of it the tenant still has."""
    async with admin_session_factory() as session:
        tables = (
            await session.scalars(
                text(
                    "SELECT table_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND column_name = 'tenant_id'"
                )
            )
        ).all()
        left: dict[str, int] = {}
        for table in tables:
            count = await session.scalar(
                text(f'SELECT count(*) FROM "{table}" WHERE tenant_id = :t'), {"t": tenant_id}
            )
            if count:
                left[table] = int(count)
        return left


async def _notified(user_id: uuid.UUID) -> list[Notification]:
    async with admin_session_factory() as session:
        return list(
            (
                await session.scalars(
                    select(Notification).where(
                        Notification.user_id == user_id, Notification.type == "tenant_deleted"
                    )
                )
            ).all()
        )


async def test_an_owner_with_the_role_deletes_a_tenant_and_everything_in_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    table = await owner.create_tenant("Doomed Table")
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=table, user_id=orga.user_id, role=MembershipRole.ORGA))
        await seed_every_content_table(session, table)
        campaign = await make_campaign(session, tenant_id=table, name="Doomed Campaign")
        session.add(CampaignGm(tenant_id=table, user_id=gm.user_id, campaign_id=campaign.id))
        player = await make_player(session, tenant_id=table, campaign_id=campaign.id)
        await make_character(
            session, tenant_id=table, name="Doomed Hero", owner_player_id=player.id
        )
        await session.commit()
        player_user_id = player.user_id
    assert await _rows_left(table)  # there is plenty to delete
    try:
        deleted = await owner.delete(f"/tenants/{table}")

        assert deleted.status_code == 204, deleted.text
        assert not await _exists(table)
        assert await _rows_left(table) == {}
        assert (await owner.get(f"/tenants/{table}")).status_code == 404
        # The people with standing in it are told, on notifications that outlive it; the person
        # who deleted it is not.
        for told in (orga.user_id, gm.user_id, player_user_id):
            notices = await _notified(told)
            assert [(n.scope, n.tenant_id) for n in notices] == [("platform", None)], told
            assert "Doomed Table" in notices[0].title
            assert notices[0].created_by == owner.user_id
        assert await _notified(owner.user_id) == []
        assert [n["type"] for n in (await orga.get("/me/notifications")).json()["items"]] == [
            "tenant_deleted"
        ]
    finally:
        async with admin_session_factory() as session:
            for user_id in (player_user_id,):
                await session.execute(text("DELETE FROM app_user WHERE id = :u"), {"u": user_id})
            await session.commit()
        await cleanup([table], [owner, orga, gm])


async def test_it_takes_the_owner_role_and_the_tenant_creator_role_and_hides_the_tenant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    owner = await make_actor(raw_client, fake_jwks_server, "owner")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    roleless = await make_actor(raw_client, fake_jwks_server, "roleless", roles=())
    table = await owner.create_tenant("Guarded Table")
    async with admin_session_factory() as session:
        session.add(Membership(tenant_id=table, user_id=orga.user_id, role=MembershipRole.ORGA))
        # An owner of it who lacks the platform role: both are needed.
        session.add(
            Membership(tenant_id=table, user_id=roleless.user_id, role=MembershipRole.OWNER)
        )
        await session.commit()
    try:
        not_a_member = await stranger.delete(f"/tenants/{table}")
        not_an_owner = await orga.delete(f"/tenants/{table}")
        no_role = await roleless.delete(f"/tenants/{table}")

        assert not_a_member.status_code == 404  # the same answer as for a tenant that isn't there
        assert not_a_member.json()["type"] == "tenant-not-found"
        assert not_an_owner.status_code == 403
        assert not_an_owner.json()["type"] == "tenant-deletion-forbidden"
        assert no_role.status_code == 403
        assert no_role.json()["type"] == "tenant-creation-forbidden"
        assert await _exists(table)
        assert await _notified(orga.user_id) == []

        assert (await owner.delete(f"/tenants/{table}")).status_code == 204
    finally:
        await cleanup([table], [owner, orga, stranger, roleless])


async def test_a_repository_others_hold_is_kept_until_the_grant_is_gone(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        assert (await author.put(f"/tenants/{faerun}/subscribers/{table}")).status_code == 201

        refused = await author.delete(f"/tenants/{faerun}")

        assert refused.status_code == 409
        assert refused.json()["type"] == "repository-still-granted"
        assert "1 tenant(s)" in refused.json()["detail"]
        assert await _exists(faerun)
        assert await _notified(gm.user_id) == []

        assert (await author.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 204
        assert (await author.delete(f"/tenants/{faerun}")).status_code == 204
        assert not await _exists(faerun)
        assert await _exists(table)
    finally:
        await cleanup([faerun, table], [author, gm])


async def test_deleting_the_tenant_that_holds_a_grant_ends_the_grant_and_keeps_the_repository(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        await author.put(f"/tenants/{faerun}/subscribers/{table}")

        assert (await gm.delete(f"/tenants/{table}")).status_code == 204

        assert await _exists(faerun)
        async with admin_session_factory() as session:
            grants = await session.scalar(
                select(func.count()).where(RepositorySubscription.repository_tenant_id == faerun)
            )
        assert grants == 0
        assert (await author.delete(f"/tenants/{faerun}")).status_code == 204  # nothing holds it
    finally:
        await cleanup([faerun, table], [author, gm])


async def test_a_copy_outlives_the_repository_it_came_from(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    try:
        sword = await author.post(f"/tenants/{faerun}/items", json={"name": "Sword"})
        assert sword.status_code == 201, sword.text
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await author.put(f"/tenants/{faerun}/published")
        assert (await gm.post(f"/tenants/{table}/repositories/{faerun}/copy")).status_code == 201
        await author.delete(f"/tenants/{faerun}/subscribers/{table}")

        assert (await author.delete(f"/tenants/{faerun}")).status_code == 204

        # The table keeps what it copied, as it does when the grant is only revoked.
        items = (await gm.get(f"/tenants/{table}/items")).json()["items"]
        assert [i["title"] for i in items] == ["Sword"]
        # Its record that it copied it stays too, as it does for a repository that was only
        # revoked: the name as it was, and nothing else (the repository is another tenant's
        # and may go, so the record holds a plain id).
        listed = (await gm.get(f"/tenants/{table}/repositories")).json()["items"]
        assert [
            (r["repository"]["name"], r["repository"]["slug"], r["granted_at"]) for r in listed
        ] == [("Faerûn", "", None)]
        assert listed[0]["copied_at"] is not None
    finally:
        await cleanup([faerun, table], [author, gm])
