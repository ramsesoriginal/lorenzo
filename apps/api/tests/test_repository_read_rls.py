"""ADR 0118's gated read, tested directly against the database as the
restricted app role (ADR 0021), table by table: a repository's rows are
visible to another tenant only with the setting, a grant, and publication
all at once, and never writable.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from _admin_db import admin_session_factory
from _repository_fixtures import seed_every_content_table
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncConnection

from lorenzo_api.db import engine
from lorenzo_api.models import RepositorySubscription, Tenant, TenantKind
from lorenzo_api.repository_access import REPOSITORY_CONTENT_TABLES, REPOSITORY_EXCLUDED_TABLES


@dataclass
class _World:
    repository: uuid.UUID
    subscriber: uuid.UUID
    stranger: uuid.UUID


@pytest.fixture
async def world() -> AsyncIterator[_World]:
    async with admin_session_factory() as session:
        repository = Tenant(name="Faerûn", kind=TenantKind.REPOSITORY)
        subscriber = Tenant(name="My Table")
        stranger = Tenant(name="Somebody Else")
        session.add_all([repository, subscriber, stranger])
        await session.flush()
        await seed_every_content_table(session, repository.id)
        await session.commit()
        ids = _World(repository.id, subscriber.id, stranger.id)
    yield ids
    async with admin_session_factory() as session:
        for tenant_id in (ids.subscriber, ids.stranger, ids.repository):
            await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def _grant(world: _World, *, to: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        session.add(
            RepositorySubscription(repository_tenant_id=world.repository, subscriber_tenant_id=to)
        )
        await session.commit()


async def _publish(world: _World) -> None:
    async with admin_session_factory() as session:
        (await session.get_one(Tenant, world.repository)).published_at = datetime.now(UTC)
        await session.commit()


async def _set(conn: AsyncConnection, *, tenant: uuid.UUID, reading: uuid.UUID | None) -> None:
    await conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
    await conn.execute(
        text("SELECT set_config('app.repository_tenant_id', :r, true)"),
        {"r": str(reading) if reading else ""},
    )


async def _visible(
    *, tenant: uuid.UUID, reading: uuid.UUID | None, of: uuid.UUID
) -> dict[str, int]:
    """How many of `of`'s rows each content table shows the app role."""
    async with engine.connect() as conn, conn.begin():
        await _set(conn, tenant=tenant, reading=reading)
        return {
            table: (
                await conn.execute(
                    text(f'SELECT count(*) FROM "{table}" WHERE tenant_id = :t'), {"t": of}
                )
            ).scalar_one()
            for table in sorted(REPOSITORY_CONTENT_TABLES)
        }


def _none(counts: dict[str, int]) -> bool:
    return all(n == 0 for n in counts.values())


async def test_setting_alone_shows_nothing(world: _World) -> None:
    await _publish(world)
    assert _none(
        await _visible(tenant=world.subscriber, reading=world.repository, of=world.repository)
    )


async def test_grant_without_publishing_shows_nothing(world: _World) -> None:
    await _grant(world, to=world.subscriber)
    assert _none(
        await _visible(tenant=world.subscriber, reading=world.repository, of=world.repository)
    )


async def test_grant_and_publishing_without_the_setting_shows_nothing(world: _World) -> None:
    """The point of amendment A1: an ordinary request never sees a
    repository, grant or no grant."""
    await _grant(world, to=world.subscriber)
    await _publish(world)
    assert _none(await _visible(tenant=world.subscriber, reading=None, of=world.repository))


async def test_setting_grant_and_publishing_show_every_table(world: _World) -> None:
    await _grant(world, to=world.subscriber)
    await _publish(world)
    counts = await _visible(tenant=world.subscriber, reading=world.repository, of=world.repository)
    assert all(n > 0 for n in counts.values()), counts


async def test_a_grant_to_somebody_else_shows_nothing(world: _World) -> None:
    await _grant(world, to=world.subscriber)
    await _publish(world)
    assert _none(
        await _visible(tenant=world.stranger, reading=world.repository, of=world.repository)
    )


async def test_reading_a_play_tenant_is_impossible(world: _World) -> None:
    """The setting can name any tenant; only a granted, published
    repository ever reads back. A grant to a play tenant can't exist."""
    async with admin_session_factory() as session:
        session.add(
            RepositorySubscription(
                repository_tenant_id=world.stranger, subscriber_tenant_id=world.subscriber
            )
        )
        with pytest.raises(DBAPIError, match="only a repository can be subscribed to"):
            await session.commit()
    assert _none(await _visible(tenant=world.subscriber, reading=world.stranger, of=world.stranger))


@pytest.mark.parametrize("table", sorted(REPOSITORY_CONTENT_TABLES))
async def test_repository_rows_are_never_writable(world: _World, table: str) -> None:
    await _grant(world, to=world.subscriber)
    await _publish(world)
    async with engine.connect() as conn, conn.begin():
        await _set(conn, tenant=world.subscriber, reading=world.repository)
        updated = await conn.execute(
            text(f'UPDATE "{table}" SET tenant_id = tenant_id WHERE tenant_id = :t'),
            {"t": world.repository},
        )
        assert updated.rowcount == 0
        deleted = await conn.execute(
            text(f'DELETE FROM "{table}" WHERE tenant_id = :t'), {"t": world.repository}
        )
        assert deleted.rowcount == 0
        # Re-inserting one of its own rows, still labelled as the
        # repository's: refused by tenant_isolation's check, whatever the
        # read policy shows.
        with pytest.raises(DBAPIError, match="row-level security"):
            async with conn.begin_nested():
                await conn.execute(
                    text(
                        f'INSERT INTO "{table}" SELECT * FROM "{table}" '
                        "WHERE tenant_id = :t LIMIT 1"
                    ),
                    {"t": world.repository},
                )
    counts = await _visible(tenant=world.repository, reading=None, of=world.repository)
    assert counts[table] > 0


async def test_authors_see_their_own_repository_as_usual(world: _World) -> None:
    counts = await _visible(tenant=world.repository, reading=None, of=world.repository)
    assert all(n > 0 for n in counts.values()), counts


async def test_every_tenant_table_is_classified() -> None:
    """The tripwire: a new tenant table must be put in one list or the
    other in lorenzo_api.repository_access, and the policy must match."""
    async with admin_session_factory() as session:
        tenant_tables = set(
            (
                await session.execute(
                    text(
                        """
                        SELECT c.relname FROM pg_class c
                        JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
                        WHERE c.relkind = 'r' AND c.relnamespace = 'public'::regnamespace
                          AND c.relrowsecurity
                        """
                    )
                )
            ).scalars()
        )
        with_policy = set(
            (
                await session.execute(
                    text(
                        "SELECT polrelid::regclass::text FROM pg_policy "
                        "WHERE polname = 'repository_read'"
                    )
                )
            ).scalars()
        )
    with_policy = {name.strip('"') for name in with_policy}
    assert tenant_tables - REPOSITORY_CONTENT_TABLES - REPOSITORY_EXCLUDED_TABLES == set()
    assert with_policy == REPOSITORY_CONTENT_TABLES
