"""ADR 0287: the gate in the database. `repository_read_tenant_id()` answers for a grant and now
for a published public repository too, and the insert policy of `repository_subscription` lets a
library write its own `public` grant to one and to nothing else. Run as the restricted app role,
as a request does, with RLS in force.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from _admin_db import admin_session_factory
from _upstream_documents import in_tenant, set_visibility
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.db import async_session_factory
from lorenzo_api.dependencies import NO_TENANT
from lorenzo_api.models import (
    Entity,
    RepositoryProfile,
    RepositorySubscription,
    Tenant,
    TenantKind,
)
from lorenzo_api.repository_access import reading_repository


async def _tenants() -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """A published repository with an entry, a library, and a library with no grant."""
    async with admin_session_factory() as session:
        repository = Tenant(
            name="Handouts", kind=TenantKind.REPOSITORY, published_at=datetime.now(UTC)
        )
        library, other = Tenant(name="A table"), Tenant(name="Another table")
        session.add_all([repository, library, other])
        await session.flush()
        session.add(Entity(tenant_id=repository.id, name="Sword"))
        session.add(RepositoryProfile(tenant_id=repository.id, summary="A little of everything"))
        await session.commit()
        return repository.id, library.id, other.id


async def _delete(*tenants: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.execute(delete(Tenant).where(Tenant.id.in_(tenants)))
        await session.commit()


@asynccontextmanager
async def _as(tenant_id: uuid.UUID) -> AsyncIterator[AsyncSession]:
    """A request of the restricted app role, in a library (`NO_TENANT`: in none)."""
    async with async_session_factory() as session:
        await in_tenant(session, tenant_id)
        yield session


async def _reads(tenant_id: uuid.UUID, repository: uuid.UUID) -> tuple[bool, list[str], str | None]:
    """What a request in `tenant_id` sees of the repository inside the gated read: whether it is
    allowed, its entries' names, and what the profile says."""
    async with _as(tenant_id) as session, reading_repository(session, repository) as allowed:
        names = list(
            await session.scalars(select(Entity.name).where(Entity.tenant_id == repository))
        )
        summary = await session.scalar(
            select(RepositoryProfile.summary).where(RepositoryProfile.tenant_id == repository)
        )
        return allowed, names, summary


async def _grant(repository: uuid.UUID, library: uuid.UUID, source: str = "invited") -> None:
    async with admin_session_factory() as session:
        session.add(
            RepositorySubscription(
                repository_tenant_id=repository, subscriber_tenant_id=library, source=source
            )
        )
        await session.commit()


# --- The read ------------------------------------------------------------------------------


async def test_a_grant_still_reads_a_private_repository_and_nothing_else_does() -> None:
    repository, library, other = await _tenants()
    try:
        assert await _reads(library, repository) == (False, [], None)
        await _grant(repository, library)
        assert await _reads(library, repository) == (True, ["Sword"], "A little of everything")
        # Granted to somebody else is not granted to this one; no tenant at all is the same.
        assert await _reads(other, repository) == (False, [], None)
        assert await _reads(NO_TENANT, repository) == (False, [], None)
    finally:
        await _delete(repository, library, other)


async def test_anyone_reads_a_published_public_repository_inside_the_gated_read() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        for reader in (library, other, NO_TENANT):
            assert await _reads(reader, repository) == (True, ["Sword"], "A little of everything")

        # Only inside the gated read: an ordinary query sees nothing of it, as ever.
        async with _as(library) as session:
            assert await session.scalar(select(Entity.name)) is None
            assert (
                await session.scalar(
                    select(RepositoryProfile.summary).where(
                        RepositoryProfile.tenant_id == repository
                    )
                )
                is None
            )
            assert (
                await session.execute(text("SELECT repository_read_tenant_id()"))
            ).scalar() is None
    finally:
        await _delete(repository, library, other)


async def test_a_draft_or_a_private_repository_is_not_public_for_anyone() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        async with admin_session_factory() as session:
            (await session.get_one(Tenant, repository)).published_at = None
            await session.commit()
        for reader in (library, NO_TENANT):
            assert (await _reads(reader, repository))[0] is False

        async with admin_session_factory() as session:
            (await session.get_one(Tenant, repository)).published_at = datetime.now(UTC)
            await session.commit()
        await set_visibility([repository], "private")
        for reader in (library, NO_TENANT):
            assert (await _reads(reader, repository))[0] is False
    finally:
        await _delete(repository, library, other)


async def test_a_grant_to_a_repository_that_went_private_still_reads_it() -> None:
    """An invitation outranks the public read: a repository going private again does not cut off
    a library it invited, and cuts off one that only copied it."""
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _grant(repository, library, "invited")
        await _grant(repository, other, "public")
        await set_visibility([repository], "private")
        # Both hold a grant row, and the gate asks for the grant only: revoking a public one
        # when the repository goes private is the flip's, not the gate's (RFC 0037 section 6).
        assert (await _reads(library, repository))[0] is True
        assert (await _reads(other, repository))[0] is True
    finally:
        await _delete(repository, library, other)


# --- The grant a library writes ---------------------------------------------------------------


async def _subscribe(library: uuid.UUID, repository: uuid.UUID, *, source: str = "public") -> None:
    async with _as(library) as session, reading_repository(session, repository):
        session.add(
            RepositorySubscription(
                repository_tenant_id=repository, subscriber_tenant_id=library, source=source
            )
        )
        await session.flush()


async def test_a_library_writes_a_public_grant_to_a_public_repository_only() -> None:
    repository, library, other = await _tenants()
    try:
        # Private: refused, as it would be for anybody.
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(library, repository)

        await set_visibility([repository], "public")
        await _subscribe(library, repository)

        # A draft is not offered, public or not.
        async with admin_session_factory() as session:
            (await session.get_one(Tenant, repository)).published_at = None
            await session.commit()
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(other, repository)
    finally:
        await _delete(repository, library, other)


async def test_a_library_writes_only_its_own_grant_and_never_an_invited_one() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        # An invitation is the repository's to write, whatever the repository is.
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(library, repository, source="invited")
        # A grant for somebody else is somebody else's.
        with pytest.raises(DBAPIError, match="row-level security"):
            async with _as(library) as session, reading_repository(session, repository):
                session.add(
                    RepositorySubscription(
                        repository_tenant_id=repository,
                        subscriber_tenant_id=other,
                        source="public",
                    )
                )
                await session.flush()
        # The repository's own side still writes an invitation and nothing else.
        async with _as(repository) as session:
            session.add(
                RepositorySubscription(
                    repository_tenant_id=repository, subscriber_tenant_id=library, source="invited"
                )
            )
            await session.flush()
        with pytest.raises(DBAPIError, match="row-level security"):
            async with _as(repository) as session:
                session.add(
                    RepositorySubscription(
                        repository_tenant_id=repository,
                        subscriber_tenant_id=other,
                        source="public",
                    )
                )
                await session.flush()
    finally:
        await _delete(repository, library, other)


async def test_the_gate_is_asked_for_and_never_ambient_when_the_repository_is_public() -> None:
    """The public branch changes who is let in, not that the read has to be asked for."""
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        async with _as(library) as session:
            visible = await session.scalars(
                select(Entity.name).where(Entity.tenant_id == repository)
            )
            assert list(visible) == []
        # And inside the block for another repository, this one stays closed.
        async with _as(library) as session, reading_repository(session, other):
            assert list(await session.scalars(select(Entity.name))) == []
    finally:
        await _delete(repository, library, other)
