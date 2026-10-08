"""ADR 0213 against the database as the restricted app role (ADR 0021): the profile
table is one tenant's own and shows nothing of a repository to anyone but through the
gated read; only a repository has one; a grant has a source, and the repository's side
can only write an invited one.
"""

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from lorenzo_api.db import engine
from lorenzo_api.models import RepositoryProfile, RepositorySubscription, Tenant, TenantKind


@dataclass
class _World:
    repository: uuid.UUID
    library: uuid.UUID
    stranger: uuid.UUID


@pytest.fixture
async def world() -> AsyncIterator[_World]:
    async with admin_session_factory() as session:
        repository = Tenant(name="Faerûn", kind=TenantKind.REPOSITORY)
        library = Tenant(name="My Table")
        stranger = Tenant(name="Somebody Else")
        session.add_all([repository, library, stranger])
        await session.flush()
        session.add(RepositoryProfile(tenant_id=repository.id, summary="Realms."))
        await session.commit()
        ids = _World(repository.id, library.id, stranger.id)
    yield ids
    async with admin_session_factory() as session:
        for tenant_id in (ids.library, ids.stranger, ids.repository):
            await session.delete(await session.get_one(Tenant, tenant_id))
        await session.commit()


async def _as(conn: AsyncConnection, tenant: uuid.UUID) -> None:
    await conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})


async def test_a_profile_is_its_tenants_own(world: _World) -> None:
    async with engine.connect() as conn, conn.begin():
        await _as(conn, world.repository)
        own = await conn.execute(text("SELECT summary FROM repository_profile"))
        assert [r[0] for r in own] == ["Realms."]
    async with engine.connect() as conn, conn.begin():
        await _as(conn, world.stranger)
        assert (await conn.execute(text("SELECT count(*) FROM repository_profile"))).scalar() == 0
        # Nor can it be written into another tenant's name, or changed from outside.
        with pytest.raises(DBAPIError, match="row-level security"):
            async with conn.begin_nested():
                await conn.execute(
                    text("INSERT INTO repository_profile (tenant_id) VALUES (:t)"),
                    {"t": world.repository},
                )
        updated = await conn.execute(
            text("UPDATE repository_profile SET summary = 'Mine.' WHERE tenant_id = :t"),
            {"t": world.repository},
        )
        assert updated.rowcount == 0


async def test_only_a_repository_has_a_profile(world: _World) -> None:
    async with admin_session_factory() as session:
        session.add(RepositoryProfile(tenant_id=world.library))
        with pytest.raises(DBAPIError, match="only a repository has a profile"):
            await session.commit()


async def test_the_profile_defaults_are_private_and_showcase_and_its_values_are_checked(
    world: _World,
) -> None:
    async with admin_session_factory() as session:
        row = await session.get_one(RepositoryProfile, world.repository)
        assert (row.visibility, row.preview) == ("private", "showcase")
    for column, value in (("visibility", "hidden"), ("preview", "all"), ("summary", "x" * 281)):
        async with admin_session_factory() as session:
            with pytest.raises(IntegrityError, match="repository_profile"):
                await session.execute(
                    text(f"UPDATE repository_profile SET {column} = :v WHERE tenant_id = :t"),
                    {"v": value, "t": world.repository},
                )


async def test_a_grant_is_invited_unless_it_says_otherwise_and_has_only_two_sources(
    world: _World,
) -> None:
    async with admin_session_factory() as session:
        session.add(
            RepositorySubscription(
                repository_tenant_id=world.repository, subscriber_tenant_id=world.library
            )
        )
        await session.commit()
        grant = await session.get_one(RepositorySubscription, (world.repository, world.library))
        assert grant.source == "invited"
        grant.source = "public"
        await session.commit()
        grant.source = "somebody"
        with pytest.raises(IntegrityError, match="repository_subscription_source"):
            await session.commit()


async def test_the_repositorys_side_writes_an_invited_grant_and_never_a_public_one(
    world: _World,
) -> None:
    async with engine.connect() as conn, conn.begin():
        await _as(conn, world.repository)
        with pytest.raises(DBAPIError, match="row-level security"):
            async with conn.begin_nested():
                await conn.execute(
                    text(
                        "INSERT INTO repository_subscription "
                        "(repository_tenant_id, subscriber_tenant_id, source) "
                        "VALUES (:r, :s, 'public')"
                    ),
                    {"r": world.repository, "s": world.library},
                )
        await conn.execute(
            text(
                "INSERT INTO repository_subscription "
                "(repository_tenant_id, subscriber_tenant_id) VALUES (:r, :s)"
            ),
            {"r": world.repository, "s": world.library},
        )
        source = await conn.execute(text("SELECT source FROM repository_subscription"))
        assert [r[0] for r in source] == ["invited"]
    # And the library cannot make one for itself: that comes with the public read.
    async with engine.connect() as conn, conn.begin():
        await _as(conn, world.stranger)
        with pytest.raises(DBAPIError, match="row-level security"):
            async with conn.begin_nested():
                await conn.execute(
                    text(
                        "INSERT INTO repository_subscription "
                        "(repository_tenant_id, subscriber_tenant_id, source) "
                        "VALUES (:r, :s, 'public')"
                    ),
                    {"r": world.repository, "s": world.stranger},
                )
