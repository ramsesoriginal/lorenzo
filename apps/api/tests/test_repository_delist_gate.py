"""ADR 0303: the delisting in the database, as the restricted app role with RLS in force. The gate
(`repository_read_tenant_id()`), the profile's own read, `discover_read` and the insert policy of
`repository_subscription` each leave out a delisted repository, for a library that holds a grant,
for one that does not and for a request in none; its own members read it as ever; and the columns
are all or none.
"""

import uuid
from datetime import UTC, datetime

import pytest
from _admin_db import admin_session_factory
from _upstream_documents import in_tenant, set_visibility
from sqlalchemy import select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from test_public_repository_gate import _as, _delete, _grant, _reads, _subscribe, _tenants

from lorenzo_api.dependencies import NO_TENANT
from lorenzo_api.models import Entity, RepositoryProfile, RepositorySubscription, Tenant


async def _delisting(repository: uuid.UUID, reason: str | None = "Abusive") -> None:
    """Delisted (or listed again, with `None`), written straight in the database."""
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant)
            .where(Tenant.id == repository)
            .values(
                delisted_at=datetime.now(UTC) if reason else None,
                delist_reason=reason,
                delisted_by=None,
            )
        )
        await session.commit()


async def _listing_sees(reader: uuid.UUID, repository: uuid.UUID) -> bool:
    """Whether the profile is visible to a request that asked to read nothing (`discover_read`)."""
    async with _as(reader) as session:
        return (
            await session.scalar(
                select(RepositoryProfile.tenant_id).where(RepositoryProfile.tenant_id == repository)
            )
        ) is not None


async def _release(repository: uuid.UUID) -> None:
    """A release label, so that the repository is one `discover_read` would list."""
    async with admin_session_factory() as session:
        await session.execute(
            update(RepositoryProfile)
            .where(RepositoryProfile.tenant_id == repository)
            .values(release_label="1.0", released_at=datetime.now(UTC))
        )
        await session.commit()


async def test_a_delisted_repository_is_read_by_nobody_through_the_gate() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _grant(repository, library)
        for reader in (library, other, NO_TENANT):
            assert (await _reads(reader, repository))[0] is True

        await _delisting(repository)
        # Granted, not granted, and in no library: the same, and nothing of it is read.
        for reader in (library, other, NO_TENANT):
            assert await _reads(reader, repository) == (False, [], None)

        # Listed again, it reads as it did.
        await _delisting(repository, None)
        for reader in (library, other, NO_TENANT):
            assert (await _reads(reader, repository))[0] is True
    finally:
        await _delete(repository, library, other)


async def test_a_delisted_private_repository_is_closed_to_the_library_that_was_invited() -> None:
    repository, library, other = await _tenants()
    try:
        await _grant(repository, library)
        assert await _reads(library, repository) == (True, ["Sword"], "A little of everything")
        await _delisting(repository)
        assert await _reads(library, repository) == (False, [], None)
        await _delisting(repository, None)
        assert (await _reads(library, repository))[0] is True
    finally:
        await _delete(repository, library, other)


async def test_the_members_of_a_delisted_repository_read_it_as_ever() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _delisting(repository)
        # A request in the repository's own tenant: its rows and its profile, and the reason.
        async with _as(repository) as session:
            names = await session.scalars(select(Entity.name).where(Entity.tenant_id == repository))
            assert list(names) == ["Sword"]
            profile = await session.get_one(RepositoryProfile, repository)
            assert profile.summary == "A little of everything"
    finally:
        await _delete(repository, library, other)


async def test_discover_does_not_list_a_delisted_repository() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _release(repository)
        assert await _listing_sees(library, repository) is True
        assert await _listing_sees(NO_TENANT, repository) is True

        await _delisting(repository)
        assert await _listing_sees(library, repository) is False
        assert await _listing_sees(NO_TENANT, repository) is False
        # Its own tenant still reads its own profile.
        assert await _listing_sees(repository, repository) is True

        await _delisting(repository, None)
        assert await _listing_sees(NO_TENANT, repository) is True
    finally:
        await _delete(repository, library, other)


async def test_the_profile_of_a_delisted_repository_is_not_read_through_the_gate() -> None:
    """A library that holds a grant reads the profile through the gated read, and a delisted
    repository's is not there to be read."""
    repository, library, other = await _tenants()
    try:
        await _grant(repository, library)
        async with _as(library) as session:
            # The gated read of a repository that is not open: nothing, not the profile either.
            await _delisting(repository)
            await session.execute(
                text("SELECT set_config('app.repository_tenant_id', :r, true)"),
                {"r": str(repository)},
            )
            assert await session.get(RepositoryProfile, repository) is None
    finally:
        await _delete(repository, library, other)


async def test_a_library_cannot_write_its_own_grant_to_a_delisted_repository() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _delisting(repository)
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(library, repository)
        # Listed again, it can.
        await _delisting(repository, None)
        await _subscribe(library, repository)
    finally:
        await _delete(repository, library, other)


async def test_the_repositorys_own_side_still_invites_while_it_is_delisted() -> None:
    """An invitation is the repository's to write, whatever state it is in; it reads as unpublished
    to the library it invites until it is listed again."""
    repository, library, other = await _tenants()
    try:
        await _delisting(repository)
        async with _as(repository) as session:
            await in_tenant(session, repository)
            session.add(
                RepositorySubscription(
                    repository_tenant_id=repository,
                    subscriber_tenant_id=library,
                    source="invited",
                )
            )
            await session.flush()
            await session.commit()
        assert (await _reads(library, repository))[0] is False
        await _delisting(repository, None)
        assert (await _reads(library, repository))[0] is True
    finally:
        await _delete(repository, library, other)


# --- The columns --------------------------------------------------------------------------------


async def test_a_delisting_is_a_time_and_a_reason_of_up_to_five_hundred_characters() -> None:
    repository, library, other = await _tenants()
    try:

        async def attempt(**values: object) -> None:
            async with admin_session_factory() as session:
                await session.execute(
                    update(Tenant).where(Tenant.id == repository).values(**values)
                )
                await session.commit()

        now = datetime.now(UTC)
        for values in (
            {"delisted_at": now},  # no reason
            {"delisted_at": now, "delist_reason": ""},
            {"delisted_at": now, "delist_reason": "x" * 501},
            {"delist_reason": "Abusive"},  # a reason and no time
        ):
            with pytest.raises(IntegrityError):
                await attempt(**values)
        await attempt(delisted_at=now, delist_reason="x" * 500)
        await attempt(delisted_at=None, delist_reason=None)

        # Only a repository is ever delisted.
        with pytest.raises(IntegrityError):
            async with admin_session_factory() as session:
                await session.execute(
                    update(Tenant)
                    .where(Tenant.id == library)
                    .values(delisted_at=now, delist_reason="Abusive")
                )
                await session.commit()
    finally:
        await _delete(repository, library, other)
