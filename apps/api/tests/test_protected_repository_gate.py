"""ADR 0434: the protected case of the gate, in the database, as the restricted app role with RLS in
force. One function, `repository_reached_through_another(a)`, says whether the request has gone
through a public repository whose current release lists the protected one; the gate
(`repository_read_tenant_id()`), the profile's own `repository_read` and the insert policy of
`repository_subscription` call it, and a Python statement of the same rule is held to all three on
every combination of the facts it reads.
"""

import itertools
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest
from _admin_db import admin_session_factory
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError
from test_public_repository_gate import _as, _delete

from lorenzo_api.dependencies import NO_TENANT
from lorenzo_api.models import (
    Entity,
    RepositoryProfile,
    RepositorySubscription,
    Tenant,
    TenantKind,
)
from lorenzo_api.repository_access import reading_repository, reading_repository_held


@dataclass
class World:
    """`a` is protected and published, with an entry and a licence in its profile; `via` is a public
    repository whose current release lists it; `library` and `other` are libraries."""

    a: uuid.UUID
    via: uuid.UUID
    library: uuid.UUID
    other: uuid.UUID

    async def done(self) -> None:
        await _delete(self.a, self.via, self.library, self.other)


async def _world() -> World:
    async with admin_session_factory() as session:
        now = datetime.now(UTC)
        a = Tenant(name="Rules", kind=TenantKind.REPOSITORY, published_at=now)
        via = Tenant(name="Handouts", kind=TenantKind.REPOSITORY, published_at=now)
        library, other = Tenant(name="A table"), Tenant(name="Another table")
        session.add_all([a, via, library, other])
        await session.flush()
        via.released_public = True
        via.released_over = [a.id]
        session.add(Entity(tenant_id=a.id, name="Law of gravity"))
        session.add(RepositoryProfile(tenant_id=a.id, visibility="protected", summary="Secret"))
        session.add(RepositoryProfile(tenant_id=via.id, visibility="public", summary="Open"))
        await session.commit()
        return World(a.id, via.id, library.id, other.id)


async def _grant(repository: uuid.UUID, library: uuid.UUID, source: str) -> None:
    async with admin_session_factory() as session:
        session.add(
            RepositorySubscription(
                repository_tenant_id=repository, subscriber_tenant_id=library, source=source
            )
        )
        await session.commit()


async def _reads(
    reader: uuid.UUID, repository: uuid.UUID, via: uuid.UUID | None = None
) -> tuple[bool, list[str], str | None]:
    """Whether the gated read of `repository` through `via` is allowed for a request in `reader`,
    the entries' names it sees, and the summary of the profile."""
    async with _as(reader) as session, reading_repository(session, repository, via=via) as allowed:
        names = list(
            await session.scalars(select(Entity.name).where(Entity.tenant_id == repository))
        )
        summary = await session.scalar(
            select(RepositoryProfile.summary).where(RepositoryProfile.tenant_id == repository)
        )
        return allowed, names, summary


# --- The Python statement of the rule ---------------------------------------------------------


@dataclass(frozen=True)
class Facts:
    """Everything the rule reads."""

    via_set: bool
    tenant: bool  # the request is in a tenant (a request in none is `NO_TENANT`)
    lists_a: bool  # the release of `via` lists `a`
    public: bool  # `via` is public
    via_delisted: bool
    via_deprecated: bool
    holds_via: bool
    a_deprecated: bool
    holds_a: bool


def reached(f: Facts) -> bool:
    """The rule of `repository_reached_through_another`: the request goes through a published,
    undelisted repository whose release lists `a` and which is public, as a tenant, and neither
    that repository nor `a` is retired unless the tenant holds it."""
    return (
        f.via_set
        and f.tenant
        and f.lists_a
        and f.public
        and not f.via_delisted
        and (not f.via_deprecated or f.holds_via)
        and (not f.a_deprecated or f.holds_a)
    )


async def _set(w: World, f: Facts) -> None:
    """The facts, written straight in the database."""
    async with admin_session_factory() as session:
        await session.execute(
            update(Tenant)
            .where(Tenant.id == w.via)
            .values(
                released_over=[w.a] if f.lists_a else [],
                released_public=f.public,
                delisted_at=datetime.now(UTC) if f.via_delisted else None,
                delist_reason="x" if f.via_delisted else None,
                deprecated_at=datetime.now(UTC) if f.via_deprecated else None,
            )
        )
        await session.execute(
            update(Tenant)
            .where(Tenant.id == w.a)
            .values(deprecated_at=datetime.now(UTC) if f.a_deprecated else None)
        )
        await session.execute(
            delete(RepositorySubscription).where(
                RepositorySubscription.subscriber_tenant_id == w.library
            )
        )
        if f.holds_via:
            session.add(
                RepositorySubscription(
                    repository_tenant_id=w.via, subscriber_tenant_id=w.library, source="public"
                )
            )
        if f.holds_a:
            session.add(
                RepositorySubscription(
                    repository_tenant_id=w.a, subscriber_tenant_id=w.library, source="protected"
                )
            )
        await session.commit()


async def test_the_database_says_what_the_python_statement_says_on_every_combination() -> None:
    """The function, the gate and the profile's policy against `reached`, on every combination of
    the facts the rule reads, as the restricted role: 288 of them."""
    w = await _world()
    seen = {True: 0, False: 0}
    try:
        for via_set, tenant, lists_a, public, delisted, via_dep, a_dep in itertools.product(
            (True, False),
            (True, False),
            (True, False),
            (True, False),
            (True, False),
            (0, 1, 2),
            (0, 1, 2),
        ):
            # via_dep / a_dep: 0 not retired, 1 retired and the tenant holds it, 2 retired and not.
            if delisted and (via_dep or a_dep):
                continue  # delisted is closed whatever else is true: one of each is enough
            facts = Facts(
                via_set=via_set,
                tenant=tenant,
                lists_a=lists_a,
                public=public,
                via_delisted=delisted,
                via_deprecated=via_dep > 0,
                holds_via=via_dep == 1,
                a_deprecated=a_dep > 0,
                holds_a=a_dep == 1,
            )
            await _set(w, facts)
            reader = w.library if tenant else NO_TENANT
            allowed, names, summary = await _reads(reader, w.a, w.via if via_set else None)
            expected = reached(facts)
            assert allowed is expected, facts
            assert (names, summary) == (
                (["Law of gravity"], "Secret") if expected else ([], None)
            ), facts
            seen[expected] += 1
    finally:
        await w.done()
    assert seen[True] == 4 and seen[False] > 100


# --- What the function is not ----------------------------------------------------------------


async def test_a_protected_row_is_not_a_grant_and_reads_nothing_alone() -> None:
    w = await _world()
    try:
        await _grant(w.a, w.library, "protected")
        # Holding it through another is not a way in: nothing of it is read, not the entries and
        # not the profile, and nothing says it is there.
        assert await _reads(w.library, w.a) == (False, [], None)
        assert await _reads(w.other, w.a) == (False, [], None)
        # Through the repository that lists it, it is.
        assert await _reads(w.library, w.a, w.via) == (True, ["Law of gravity"], "Secret")
    finally:
        await w.done()


async def test_an_invitation_reads_a_protected_repository_as_it_reads_a_private_one() -> None:
    """The Owner of a protected repository invites a library as of any repository (ADR 0118):
    that is the grant a repository built on it takes, and it reads it alone."""
    w = await _world()
    try:
        await _grant(w.a, w.library, "invited")
        assert await _reads(w.library, w.a) == (True, ["Law of gravity"], "Secret")
        assert await _reads(w.other, w.a) == (False, [], None)
        assert await _reads(NO_TENANT, w.a) == (False, [], None)
    finally:
        await w.done()


async def test_the_gate_asks_the_repository_through_which_and_never_another() -> None:
    """`via` is one repository, and the rule is about that one: a public repository that lists a
    different one does not open this."""
    w = await _world()
    try:
        async with admin_session_factory() as session:
            elsewhere = Tenant(
                name="Elsewhere",
                kind=TenantKind.REPOSITORY,
                published_at=datetime.now(UTC),
                released_public=True,
                released_over=[uuid.uuid4()],
            )
            session.add(elsewhere)
            await session.flush()
            session.add(RepositoryProfile(tenant_id=elsewhere.id, visibility="public"))
            await session.commit()
            other_via = elsewhere.id
        try:
            assert (await _reads(w.library, w.a, other_via))[0] is False
            assert (await _reads(w.library, w.a, w.via))[0] is True
            # A repository that is not protected is not read through another: the public branch
            # and a grant are as they were.
            assert (await _reads(w.library, w.via, w.via))[0] is True
            assert (await _reads(w.library, w.via, other_via))[0] is True
        finally:
            await _delete(other_via)
    finally:
        await w.done()


async def test_it_is_asked_for_and_never_ambient() -> None:
    w = await _world()
    try:
        async with _as(w.library) as session:
            await session.execute(
                text("SELECT set_config('app.repository_via', :v, true)"),
                {"v": str(w.via)},
            )
            # Said to go through `via`, and no repository asked for: nothing is read.
            assert list(await session.scalars(select(Entity.name))) == []
            assert (
                await session.execute(text("SELECT repository_read_tenant_id()"))
            ).scalar() is None
    finally:
        await w.done()


async def test_a_delisted_or_draft_protected_repository_is_closed_through_the_listing_one() -> None:
    w = await _world()
    try:
        async with admin_session_factory() as session:
            await session.execute(
                update(Tenant)
                .where(Tenant.id == w.a)
                .values(delisted_at=datetime.now(UTC), delist_reason="Abusive")
            )
            await session.commit()
        assert (await _reads(w.library, w.a, w.via))[0] is False
        async with admin_session_factory() as session:
            await session.execute(
                update(Tenant).where(Tenant.id == w.a).values(delisted_at=None, delist_reason=None)
            )
            await session.commit()
        assert (await _reads(w.library, w.a, w.via))[0] is True
        async with admin_session_factory() as session:
            await session.execute(update(Tenant).where(Tenant.id == w.a).values(published_at=None))
            await session.commit()
        assert (await _reads(w.library, w.a, w.via))[0] is False
    finally:
        await w.done()


async def test_a_repository_that_became_public_or_private_is_read_as_such_whatever_via_says() -> (
    None
):
    w = await _world()
    try:
        for visibility, expected in (("public", True), ("private", False), ("protected", True)):
            async with admin_session_factory() as session:
                await session.execute(
                    update(RepositoryProfile)
                    .where(RepositoryProfile.tenant_id == w.a)
                    .values(visibility=visibility)
                )
                await session.commit()
            # Public is read by anybody; private is not read through another; protected is.
            assert (await _reads(w.library, w.a, w.via))[0] is expected
        async with admin_session_factory() as session:
            await session.execute(
                update(RepositoryProfile)
                .where(RepositoryProfile.tenant_id == w.a)
                .values(visibility="public")
            )
            await session.commit()
        assert (await _reads(NO_TENANT, w.a))[0] is True
    finally:
        await w.done()


# --- The helper a reader that holds a repository uses -----------------------------------------


async def test_a_reader_that_holds_it_goes_through_each_repository_that_could() -> None:
    w = await _world()
    try:
        # The library holds the public repository (a grant it gave itself) and nothing of A.
        await _grant(w.via, w.library, "public")
        async with _as(w.library) as session, reading_repository_held(session, w.a) as allowed:
            assert allowed is True
            assert list(await session.scalars(select(Entity.name))) == ["Law of gravity"]
        # One that holds nothing is let in nowhere, and nothing stays set after the block.
        async with _as(w.other) as session:
            async with reading_repository_held(session, w.a) as allowed:
                assert allowed is False
            assert list(await session.scalars(select(Entity.name))) == []
        # The repository stops listing it: the library holds it and reads it no more.
        async with admin_session_factory() as session:
            await session.execute(update(Tenant).where(Tenant.id == w.via).values(released_over=[]))
            await session.commit()
        async with _as(w.library) as session, reading_repository_held(session, w.a) as allowed:
            assert allowed is False
    finally:
        await w.done()


# --- The grant a library writes ----------------------------------------------------------------


async def _subscribe(
    library: uuid.UUID,
    repository: uuid.UUID,
    *,
    via: uuid.UUID | None,
    source: str = "protected",
    subscriber: uuid.UUID | None = None,
) -> None:
    async with _as(library) as session, reading_repository(session, repository, via=via):
        session.add(
            RepositorySubscription(
                repository_tenant_id=repository,
                subscriber_tenant_id=subscriber or library,
                source=source,
            )
        )
        await session.flush()
        await session.commit()


async def test_a_library_writes_a_protected_row_through_the_repository_that_lists_it_only() -> None:
    w = await _world()
    try:
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(w.library, w.a, via=None)
        await _subscribe(w.library, w.a, via=w.via)
        async with admin_session_factory() as session:
            row = await session.get_one(RepositorySubscription, (w.a, w.library))
            assert row.source == "protected"
    finally:
        await w.done()


async def test_a_library_cannot_write_any_other_row_to_a_protected_repository() -> None:
    w = await _world()
    try:
        # Not an invitation, not a public grant (it is not public), not one for somebody else.
        for source in ("invited", "public"):
            with pytest.raises(DBAPIError, match="row-level security"):
                await _subscribe(w.library, w.a, via=w.via, source=source)
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(w.library, w.a, via=w.via, subscriber=w.other)
        # And not a protected row to a repository that is not protected.
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(w.library, w.via, via=w.via)
        # Nor through a repository that is not public, or that does not list it.
        async with admin_session_factory() as session:
            await session.execute(update(Tenant).where(Tenant.id == w.via).values(released_over=[]))
            await session.commit()
        with pytest.raises(DBAPIError, match="row-level security"):
            await _subscribe(w.library, w.a, via=w.via)
    finally:
        await w.done()


async def test_the_repositorys_side_turns_public_rows_into_protected_ones_and_nothing_else() -> (
    None
):
    w = await _world()
    try:
        await _grant(w.a, w.library, "public")
        await _grant(w.a, w.other, "invited")
        async with _as(w.a) as session:
            await session.execute(
                update(RepositorySubscription)
                .where(
                    RepositorySubscription.repository_tenant_id == w.a,
                    RepositorySubscription.source == "public",
                )
                .values(source="protected")
            )
            # An invitation is not turned into anything: the row is not visible to the update.
            await session.execute(
                update(RepositorySubscription)
                .where(
                    RepositorySubscription.repository_tenant_id == w.a,
                    RepositorySubscription.source == "invited",
                )
                .values(source="public")
            )
            await session.commit()
        async with admin_session_factory() as session:
            sources = {
                row.subscriber_tenant_id: row.source
                for row in await session.scalars(
                    select(RepositorySubscription).where(
                        RepositorySubscription.repository_tenant_id == w.a
                    )
                )
            }
        assert sources == {w.library: "protected", w.other: "invited"}
        # A library cannot turn its own row, and the repository cannot turn one into an
        # invitation.
        async with _as(w.library) as session:
            result = await session.execute(
                update(RepositorySubscription)
                .where(RepositorySubscription.subscriber_tenant_id == w.library)
                .values(source="public")
            )
            assert result.rowcount == 0  # type: ignore[attr-defined]
        with pytest.raises(DBAPIError, match="row-level security"):
            async with _as(w.a) as session:
                await session.execute(
                    update(RepositorySubscription)
                    .where(RepositorySubscription.subscriber_tenant_id == w.library)
                    .values(source="invited")
                )
    finally:
        await w.done()


# --- The columns --------------------------------------------------------------------------------


async def test_the_database_allows_the_three_visibilities_and_the_three_sources() -> None:
    w = await _world()
    try:
        async with admin_session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(RepositoryProfile)
                    .where(RepositoryProfile.tenant_id == w.a)
                    .values(visibility="hidden")
                )
            await session.rollback()
            with pytest.raises(IntegrityError):
                await session.execute(
                    text(
                        "INSERT INTO repository_subscription "
                        "(repository_tenant_id, subscriber_tenant_id, source) "
                        "VALUES (:r, :s, 'secret')"
                    ),
                    {"r": w.a, "s": w.library},
                )
            await session.rollback()
            # A protected repository is not listed as unlisted: the check of ADR 0432 holds.
            await session.execute(
                update(RepositoryProfile)
                .where(RepositoryProfile.tenant_id == w.a)
                .values(listed=True)
            )
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(RepositoryProfile)
                    .where(RepositoryProfile.tenant_id == w.a)
                    .values(listed=False)
                )
    finally:
        await w.done()


async def test_only_a_repository_reaches_anything() -> None:
    w = await _world()
    try:
        async with admin_session_factory() as session:
            with pytest.raises(IntegrityError):
                await session.execute(
                    update(Tenant)
                    .where(Tenant.id == w.library)
                    .values(released_public=True, released_over=[w.a])
                )
    finally:
        await w.done()


def test_the_facts_are_what_the_rule_reads() -> None:
    """The mirror's own sanity: a request in no tenant never gets through, whatever else is true."""
    everything: dict[str, Any] = {
        "via_set": True,
        "lists_a": True,
        "public": True,
        "via_delisted": False,
        "via_deprecated": False,
        "holds_via": False,
        "a_deprecated": False,
        "holds_a": False,
    }
    assert reached(Facts(tenant=True, **everything)) is True
    assert reached(Facts(tenant=False, **everything)) is False
