"""ADR 0118, second half, through the real HTTP API: a repository's owner
grants a tenant access, the tenant's members browse it once published, and
either side can end the grant.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from _repository_fixtures import seed_every_content_table
from httpx import AsyncClient
from sqlalchemy import select

from lorenzo_api.models import AuditLog, Membership, MembershipRole


async def _notification_types(actor: Actor) -> list[str]:
    response = await actor.get("/me/notifications")
    assert response.status_code == 200
    return [n["type"] for n in response.json()["items"]]


async def _seed(repository_id: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await seed_every_content_table(session, repository_id)
        await session.commit()


async def test_granting_publishing_browsing_and_removing(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    elsewhere = await stranger.create_tenant("Elsewhere")
    await _seed(faerun)
    try:
        granted = await author.put(f"/tenants/{faerun}/subscribers/{table}")
        assert granted.status_code == 201
        assert granted.json()["name"] == "My Table"
        assert (await author.put(f"/tenants/{faerun}/subscribers/{table}")).status_code == 200
        assert await _notification_types(gm) == ["repository_granted"]

        subscribers = (await author.get(f"/tenants/{faerun}/subscribers")).json()["items"]
        assert [s["tenant_id"] for s in subscribers] == [str(table)]

        listed = (await gm.get(f"/tenants/{table}/repositories")).json()["items"]
        assert [(r["repository"]["id"], r["repository"]["published_at"]) for r in listed] == [
            (str(faerun), None)
        ]

        # A draft can't be browsed, even with a grant.
        draft = await gm.get(f"/tenants/{table}/repositories/{faerun}/entities")
        assert draft.status_code == 404
        assert draft.json()["type"] == "repository-not-found"

        assert (await author.put(f"/tenants/{faerun}/published")).status_code == 200
        assert (await _notification_types(gm))[0] == "repository_published"

        entities = (await gm.get(f"/tenants/{table}/repositories/{faerun}/entities")).json()
        by_name = {e["name"]: e for e in entities["items"]}
        assert set(by_name) == {"Blade", "Chest", "Elminster", "Harpers", "Sword"}
        assert by_name["Blade"]["kinds"] == ["item_instance"]
        assert by_name["Blade"]["prototype_ids"] == [by_name["Sword"]["id"]]
        assert by_name["Elminster"]["kinds"] == ["being", "character"]
        filtered = await gm.get(f"/tenants/{table}/repositories/{faerun}/entities?q=elm")
        assert [e["name"] for e in filtered.json()["items"]] == ["Elminster"]

        groups = (await gm.get(f"/tenants/{table}/repositories/{faerun}/stat-groups")).json()
        assert [g["name"] for g in groups] == ["Abilities"]
        definitions = {d["name"]: d for d in groups[0]["definitions"]}
        assert definitions["Alignment"]["enum_values"] == ["neutral"]
        assert definitions["Strength"]["value_type"] == "int"

        # Nobody else gets in: not the stranger's own tenant, and not the
        # stranger through somebody else's tenant.
        assert (
            await stranger.get(f"/tenants/{elsewhere}/repositories/{faerun}/entities")
        ).status_code == 404
        assert (
            await stranger.get(f"/tenants/{table}/repositories/{faerun}/entities")
        ).status_code in (403, 404)

        # Publishing again announces an update.
        await author.put(f"/tenants/{faerun}/published")
        assert (await _notification_types(gm))[0] == "repository_updated"

        # The subscribing side gives the grant up.
        assert (await gm.delete(f"/tenants/{table}/repositories/{faerun}")).status_code == 204
        assert (await gm.get(f"/tenants/{table}/repositories")).json()["items"] == []
        assert (await gm.get(f"/tenants/{table}/repositories/{faerun}/entities")).status_code == 404
        assert (await gm.delete(f"/tenants/{table}/repositories/{faerun}")).status_code == 404

        # The repository's side revokes one.
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        assert (await author.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 204
        assert (await author.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 404

        async with admin_session_factory() as session:
            repository_actions = (
                await session.scalars(
                    select(AuditLog.action)
                    .where(AuditLog.tenant_id == faerun)
                    .order_by(AuditLog.created_at)
                )
            ).all()
            table_actions = (
                await session.scalars(select(AuditLog.action).where(AuditLog.tenant_id == table))
            ).all()
        assert repository_actions == [
            "repository.granted",
            "repository.published",
            "repository.published",
            "repository.granted",
            "repository.revoked",
        ]
        assert table_actions == ["repository.removed"]
    finally:
        await cleanup([table, elsewhere, faerun], [author, gm, stranger])


async def test_who_may_grant_and_what(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    orga = await make_actor(raw_client, fake_jwks_server, "orga")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await author.create_tenant("My Table")
    async with admin_session_factory() as session:
        session.add_all(
            [
                Membership(tenant_id=faerun, user_id=orga.user_id, role=MembershipRole.ORGA),
                Membership(tenant_id=table, user_id=orga.user_id, role=MembershipRole.ORGA),
            ]
        )
        await session.commit()
    try:
        forbidden = await orga.put(f"/tenants/{faerun}/subscribers/{table}")
        assert forbidden.status_code == 403
        assert forbidden.json()["type"] == "repository-management-forbidden"

        itself = await author.put(f"/tenants/{faerun}/subscribers/{faerun}")
        assert itself.status_code == 422
        assert itself.json()["type"] == "invalid-subscriber"

        unknown = await author.put(f"/tenants/{faerun}/subscribers/{uuid.uuid4()}")
        assert unknown.status_code == 404

        from_play = await author.put(f"/tenants/{table}/subscribers/{faerun}")
        assert from_play.status_code == 409
        assert from_play.json()["type"] == "not-a-repository"

        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        # Any member of either side can list; only an owner removes.
        assert (await orga.get(f"/tenants/{faerun}/subscribers")).status_code == 200
        assert (await orga.get(f"/tenants/{table}/repositories")).status_code == 200
        assert (await orga.delete(f"/tenants/{table}/repositories/{faerun}")).status_code == 403
        assert (await orga.delete(f"/tenants/{faerun}/subscribers/{table}")).status_code == 403
    finally:
        await cleanup([table, faerun], [author, orga])


async def test_browsing_leaves_the_request_reading_only_its_own_tenant(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """A subscriber's ordinary reads never show the repository's rows,
    before or after browsing it (amendment A1)."""
    author = await make_actor(raw_client, fake_jwks_server, "author")
    gm = await make_actor(raw_client, fake_jwks_server, "gm")
    faerun = await author.create_tenant("Faerûn", kind="repository")
    table = await gm.create_tenant("My Table")
    await _seed(faerun)
    try:
        await author.put(f"/tenants/{faerun}/subscribers/{table}")
        await author.put(f"/tenants/{faerun}/published")
        assert (await gm.get(f"/tenants/{table}/entities")).json()["items"] == []
        await gm.get(f"/tenants/{table}/repositories/{faerun}/entities")
        assert (await gm.get(f"/tenants/{table}/entities")).json()["items"] == []
        assert (await gm.get(f"/tenants/{table}/items")).json()["items"] == []
        assert (await gm.get(f"/tenants/{faerun}/entities")).status_code in (403, 404)
    finally:
        await cleanup([table, faerun], [author, gm])
