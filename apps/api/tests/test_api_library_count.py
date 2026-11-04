"""ADR 0386: how many libraries hold a copy of a row of a repository - a count through a gated
policy on the copy links, never a name - and the deletes that log it.
"""

import uuid

from _admin_db import admin_session_factory
from _fake_jwks import FakeJwksServer
from _repository_actors import Actor, cleanup, make_actor
from httpx import AsyncClient
from sqlalchemy import select, text
from test_repository_updates import _local, _world

from lorenzo_api.db import engine
from lorenzo_api.models import AuditLog, Entity, Membership, MembershipRole


async def _second_library(
    world, raw_client: AsyncClient, jwks: FakeJwksServer
) -> tuple[Actor, uuid.UUID]:
    gm2 = await make_actor(raw_client, jwks, "gm2")
    table2 = await gm2.create_tenant("Another Table")
    assert (
        await world.author.put(f"/tenants/{world.repository}/subscribers/{table2}")
    ).status_code == 201
    copied = await gm2.post(f"/tenants/{table2}/repositories/{world.repository}/copy")
    assert copied.status_code == 201, copied.text
    return gm2, table2


async def _count(actor: Actor, url: str) -> int:
    response = await actor.get(url)
    assert response.status_code == 200, response.text
    assert set(response.json()) == {"count"}  # a number, never a name
    return response.json()["count"]


async def _logged(tenant: uuid.UUID, action: str) -> list[str | None]:
    async with admin_session_factory() as session:
        return list(
            await session.scalars(
                select(AuditLog.detail).where(
                    AuditLog.tenant_id == tenant, AuditLog.action == action
                )
            )
        )


async def test_the_count_follows_who_still_holds_a_copy(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    ids, repository = world.ids, world.repository
    base = f"/tenants/{repository}"
    gm2, table2 = await _second_library(world, raw_client, fake_jwks_server)
    try:
        entry = f"{base}/entities/{ids['Longsword']}/libraries"
        group = f"{base}/stat-groups/{ids['Abilities']}/libraries"
        definition = f"{base}/stat-definitions/{ids['Strength']}/libraries"
        assert [await _count(world.author, u) for u in (entry, group, definition)] == [2, 2, 2]

        # One library deletes its copy of the entry: its link stays, with no copy to count.
        local = await _local(world)
        async with admin_session_factory() as session:
            await session.delete(await session.get_one(Entity, local[ids["Longsword"]]))
            await session.commit()
        assert await _count(world.author, entry) == 1
        assert await _count(world.author, group) == 2  # its stat group it still holds

        # A library asking about its own copy, or about the repository's id, learns nothing.
        copy_url = f"/tenants/{world.table}/entities/{local[ids['Dagger']]}/libraries"
        assert await _count(world.gm, copy_url) == 0
        refused = await world.gm.get(entry)
        assert refused.status_code in (403, 404)
        assert (
            await world.author.get(f"{base}/entities/{uuid.uuid4()}/libraries")
        ).status_code == 404
    finally:
        await cleanup([world.table, table2, world.repository], [world.author, world.gm, gm2])


async def test_an_author_may_count_an_entry_and_not_a_stat(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    ids, base = world.ids, f"/tenants/{world.repository}"
    helper = await make_actor(raw_client, fake_jwks_server, "helper")
    try:
        async with admin_session_factory() as session:
            session.add(
                Membership(
                    tenant_id=world.repository, user_id=helper.user_id, role=MembershipRole.AUTHOR
                )
            )
            await session.commit()
        assert await _count(helper, f"{base}/entities/{ids['Longsword']}/libraries") == 1
        for url in (
            f"{base}/stat-definitions/{ids['Strength']}/libraries",
            f"{base}/stat-groups/{ids['Abilities']}/libraries",
        ):
            assert (await helper.get(url)).status_code == 403
    finally:
        await cleanup([world.table, world.repository], [world.author, world.gm, helper])


async def test_a_delete_logs_how_many_libraries_held_it(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    ids, repository = world.ids, world.repository
    base = f"/tenants/{repository}"
    try:
        # Delete never waits for the count: this one was never asked.
        assert (await world.author.delete(f"{base}/entities/{ids['Orc']}")).status_code == 204
        assert (await world.author.delete(f"{base}/items/{ids['Dagger']}")).status_code == 204
        assert (
            await world.author.delete(f"{base}/stat-definitions/{ids['Speed']}")
        ).status_code == 204
        assert await _logged(repository, "entity.deleted") == ["kinds=none, libraries=1"]
        assert await _logged(repository, "item.deleted") == ["libraries=1"]
        deleted = await _logged(repository, "stat_definition.deleted")
        assert len(deleted) == 1 and deleted[0] is not None and deleted[0].endswith(", libraries=1")
    finally:
        await cleanup([world.table, world.repository], [world.author, world.gm])


async def test_a_delete_nobody_holds_logs_no_count(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    author = await make_actor(raw_client, fake_jwks_server, "author")
    repository = await author.create_tenant("Unused", kind="repository")
    try:
        made = await author.post(
            f"/tenants/{repository}/entities", json={"name": "Pebble", "kinds": []}
        )
        assert made.status_code == 201, made.text
        entity = made.json()["id"]
        assert await _count(author, f"/tenants/{repository}/entities/{entity}/libraries") == 0
        assert (await author.delete(f"/tenants/{repository}/entities/{entity}")).status_code == 204
        assert await _logged(repository, "entity.deleted") == ["kinds=none"]
    finally:
        await cleanup([repository], [author])


async def test_a_play_library_counts_zero(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    world = await _world(raw_client, fake_jwks_server)
    local = await _local(world)
    try:
        url = f"/tenants/{world.table}/entities/{local[world.ids['Longsword']]}/libraries"
        assert await _count(world.gm, url) == 0
    finally:
        await cleanup([world.table, world.repository], [world.author, world.gm])


async def test_only_the_repository_with_the_setting_reads_its_links(
    raw_client: AsyncClient, fake_jwks_server: FakeJwksServer
) -> None:
    """The policy itself, as the restricted role: no setting, nothing; the setting, the
    repository's own links; a library or a stranger with the setting, nothing of it."""
    world = await _world(raw_client, fake_jwks_server)
    gm2, table2 = await _second_library(world, raw_client, fake_jwks_server)
    stranger = await make_actor(raw_client, fake_jwks_server, "stranger")
    elsewhere = await stranger.create_tenant("Elsewhere")
    sql = "SELECT count(*) FROM repository_copy_link_entity WHERE source_tenant_id = :repository"

    async def read(tenant: uuid.UUID, *, gate: bool) -> int:
        async with engine.connect() as conn:
            await conn.execute(
                text("SELECT set_config('app.tenant_id', :t, false)"), {"t": str(tenant)}
            )
            if gate:
                await conn.execute(text("SELECT set_config('app.library_count', 'on', false)"))
            return (await conn.execute(text(sql), {"repository": world.repository})).scalar_one()

    try:
        async with admin_session_factory() as session:
            everything = (
                await session.execute(
                    text(
                        "SELECT count(*) FROM repository_copy_link_entity "
                        "WHERE source_tenant_id = :r"
                    ),
                    {"r": world.repository},
                )
            ).scalar_one()
        assert everything > 0
        assert await read(world.repository, gate=False) == 0
        assert await read(world.repository, gate=True) == everything
        # a library sees only its own links, with or without the setting
        own = await read(world.table, gate=True)
        assert 0 < own < everything
        assert await read(world.table, gate=False) == own
        assert await read(elsewhere, gate=True) == 0
    finally:
        await cleanup(
            [world.table, table2, world.repository, elsewhere],
            [world.author, world.gm, gm2, stranger],
        )
