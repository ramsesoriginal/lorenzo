"""ADR 0384: the deprecation in the database, as the restricted app role with RLS in force. The gate
(`repository_read_tenant_id()`), the profile's own read, `discover_read` and the insert policy of
`repository_subscription` close the public branch for a repository its Owner retired, and nothing
else: a library that holds a grant (invited, or by a copy of a public repository) reads it as it
did, a visitor and a library with no grant read nothing, a delisted one is closed to everybody, and
the columns are all or none.
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


async def _deprecating(
    repository: uuid.UUID, message: str | None = None, *, on: bool = True
) -> None:
    """Retired (or brought back, with `on=False`), written straight in the database."""
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant)
            .where(Tenant.id == repository)
            .values(
                deprecated_at=datetime.now(UTC) if on else None,
                deprecated_message=message if on else None,
            )
        )
        await session.commit()


async def _delisting(repository: uuid.UUID, *, on: bool = True) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant)
            .where(Tenant.id == repository)
            .values(
                delisted_at=datetime.now(UTC) if on else None,
                delist_reason="Abusive" if on else None,
            )
        )
        await session.commit()


async def _listing_sees(reader: uuid.UUID, repository: uuid.UUID) -> bool:
    async with _as(reader) as session:
        return (
            await session.scalar(
                select(RepositoryProfile.tenant_id).where(RepositoryProfile.tenant_id == repository)
            )
        ) is not None


async def _release(repository: uuid.UUID) -> None:
    async with admin_session_factory() as session:
        await session.execute(
            update(RepositoryProfile)
            .where(RepositoryProfile.tenant_id == repository)
            .values(release_label="1.0", released_at=datetime.now(UTC))
        )
        await session.commit()


OPEN = (True, ["Sword"], "A little of everything")
CLOSED = (False, [], None)


async def test_a_deprecated_public_repository_is_closed_to_whoever_holds_no_grant() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _grant(repository, library, "public")
        for reader in (library, other, NO_TENANT):
            assert await _reads(reader, repository) == OPEN

        await _deprecating(repository, "Use the new one")
        # A library with a grant given by its own copy reads all it read, the profile included.
        assert await _reads(library, repository) == OPEN
        # A library with none and a request in none read nothing of it.
        assert await _reads(other, repository) == CLOSED
        assert await _reads(NO_TENANT, repository) == CLOSED

        # Brought back, it reads as it did.
        await _deprecating(repository, on=False)
        for reader in (library, other, NO_TENANT):
            assert await _reads(reader, repository) == OPEN
    finally:
        await _delete(repository, library, other)


async def test_an_invited_library_keeps_reading_a_deprecated_repository_public_or_private() -> None:
    repository, library, other = await _tenants()
    try:
        await _grant(repository, library)
        await _deprecating(repository)
        assert await _reads(library, repository) == OPEN
        assert await _reads(other, repository) == CLOSED

        await set_visibility([repository], "public")
        assert await _reads(library, repository) == OPEN
        assert await _reads(other, repository) == CLOSED
        assert await _reads(NO_TENANT, repository) == CLOSED
    finally:
        await _delete(repository, library, other)


async def test_a_deprecated_and_delisted_repository_is_closed_to_every_library() -> None:
    """The operator's delist wins: it reads as unpublished, to the holder too."""
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _grant(repository, library, "public")
        await _deprecating(repository)
        await _delisting(repository)
        for reader in (library, other, NO_TENANT):
            assert await _reads(reader, repository) == CLOSED

        # Listed again it is deprecated still: the holder reads, the rest do not.
        await _delisting(repository, on=False)
        assert await _reads(library, repository) == OPEN
        assert await _reads(other, repository) == CLOSED
    finally:
        await _delete(repository, library, other)


async def test_the_members_of_a_deprecated_repository_read_it_as_ever() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _deprecating(repository, "Use the new one")
        async with _as(repository) as session:
            names = await session.scalars(select(Entity.name).where(Entity.tenant_id == repository))
            assert list(names) == ["Sword"]
            tenant = await session.get_one(Tenant, repository)
            assert tenant.deprecated_message == "Use the new one"
    finally:
        await _delete(repository, library, other)


async def test_discover_does_not_list_a_deprecated_repository() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _release(repository)
        assert await _listing_sees(NO_TENANT, repository) is True
        await _deprecating(repository)
        assert await _listing_sees(library, repository) is False
        assert await _listing_sees(NO_TENANT, repository) is False
        # Its own tenant still reads its own profile.
        assert await _listing_sees(repository, repository) is True
        await _deprecating(repository, on=False)
        assert await _listing_sees(NO_TENANT, repository) is True
    finally:
        await _delete(repository, library, other)


async def test_a_deprecated_profile_is_read_through_the_gate_by_a_holder_only() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _grant(repository, library, "public")
        await _deprecating(repository)
        for reader, expected in ((library, True), (other, False), (NO_TENANT, False)):
            async with _as(reader) as session:
                await session.execute(
                    text("SELECT set_config('app.repository_tenant_id', :r, true)"),
                    {"r": str(repository)},
                )
                assert (await session.get(RepositoryProfile, repository) is not None) is expected
    finally:
        await _delete(repository, library, other)


async def test_a_library_cannot_write_its_own_grant_to_a_deprecated_repository() -> None:
    repository, library, other = await _tenants()
    try:
        await set_visibility([repository], "public")
        await _deprecating(repository)
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(library, repository)
        # Brought back, it can.
        await _deprecating(repository, on=False)
        await _subscribe(library, repository)
    finally:
        await _delete(repository, library, other)


async def test_the_repositorys_own_side_still_invites_while_it_is_deprecated() -> None:
    repository, library, other = await _tenants()
    try:
        await _deprecating(repository)
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
        assert (await _reads(library, repository))[0] is True
    finally:
        await _delete(repository, library, other)


# --- The columns --------------------------------------------------------------------------------


async def test_a_deprecation_is_a_time_and_a_message_of_up_to_five_hundred_characters() -> None:
    repository, library, other = await _tenants()
    try:

        async def attempt(target: uuid.UUID = repository, **values: object) -> None:
            async with admin_session_factory() as session:
                await session.execute(update(Tenant).where(Tenant.id == target).values(**values))
                await session.commit()

        now = datetime.now(UTC)
        for values in (
            {"deprecated_message": "A message and no time"},
            {"deprecated_at": now, "deprecated_message": ""},
            {"deprecated_at": now, "deprecated_message": "x" * 501},
        ):
            with pytest.raises(IntegrityError):
                await attempt(**values)
        # The message is optional, and five hundred characters is the most.
        await attempt(deprecated_at=now, deprecated_message=None)
        await attempt(deprecated_at=now, deprecated_message="x" * 500)
        await attempt(deprecated_at=None, deprecated_message=None)

        # Only a repository is ever deprecated.
        with pytest.raises(IntegrityError):
            await attempt(library, deprecated_at=now)
    finally:
        await _delete(repository, library, other)
