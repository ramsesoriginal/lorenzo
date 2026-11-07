"""What a repository's current release reaches - ADR 0434, RFC 0051 H3.

A library reads a protected repository only through a public repository whose current release
lists it. The database says so in one function (`repository_reached_through_another`, revision
c04330000001) and it can only read the `tenant` row of the repository the reader goes through, so
two facts of that repository's profile are kept there: `tenant.released_over`, the repositories its
current release was built on and did not include, and `tenant.released_public`, whether it is
public. `sync_reach` writes both from the profile, whenever the profile's `release_sources` or
`visibility` change; the tests hold them to it.

The same facts answer, from a repository's own side, which repositories depend on it staying
reachable (`dependents_over`): those whose current release is built on it and did not include it,
public or protected.
"""

import uuid
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import RepositoryCopy, RepositoryProfile, RepositorySubscription, Tenant

__all__ = [
    "PROTECTED_NAME",
    "dependents_over",
    "held_protected",
    "holders_of",
    "reach_of",
    "revoke_protected_through",
    "sync_reach",
]

# What a repository kept for a library that holds it through another is called to everybody who
# does not own it or was not invited to it: no public view names a protected repository
# (ADR 0434, RFC 0051 default 2).
PROTECTED_NAME = "A protected repository"


def reach_of(
    visibility: str,
    release_sources: list[dict[str, Any]] | None,
    copied: list[uuid.UUID],
) -> tuple[list[uuid.UUID], bool]:
    """`(released_over, released_public)` of a repository with this visibility, release record and
    copy records. A private repository reaches nothing. A record of the current release is what it
    was built on; a release made before the record existed was built on what the repository had
    copied."""
    if visibility not in ("public", "protected"):
        return [], False
    if release_sources is None:
        over = sorted(copied, key=str)
    else:
        over = sorted(
            (uuid.UUID(s["id"]) for s in release_sources if s["inclusion"] != "include"), key=str
        )
    return over, visibility == "public"


async def sync_reach(session: AsyncSession, repository_id: uuid.UUID) -> None:
    """Writes the two facts from the profile and the copy records. Flushes. The caller is the
    repository's own context, which is where its `tenant` row is written."""
    tenant = await session.get(Tenant, repository_id)
    profile = await session.get(RepositoryProfile, repository_id)
    if tenant is None:
        return
    copied = list(
        await session.scalars(
            select(RepositoryCopy.repository_tenant_id).where(
                RepositoryCopy.tenant_id == repository_id
            )
        )
    )
    over, public = reach_of(
        profile.visibility if profile is not None else "private",
        profile.release_sources if profile is not None else None,
        copied,
    )
    if tenant.released_over != over or tenant.released_public != public:
        tenant.released_over = over
        tenant.released_public = public
        await session.flush()


async def held_protected(
    session: AsyncSession, repository_id: uuid.UUID, source_id: uuid.UUID
) -> tuple[uuid.UUID | None] | None:
    """Whether the repository holds a copy of `source_id` that it took while the source was
    readable to it, and the source is protected now: the repository's own `protected` grant row
    for it (written when a library or repository copies a public repository that brings a
    protected one, and when a public repository is made protected, ADR 0434) on a source that is
    published and not delisted. Returns `(its current release id,)`, or None when it holds no such
    copy.

    This is what lets a repository that copied a public A go on releasing once A is protected
    (ADR 0434, the maintainer's decision), with no invitation and no new way to read A: the answer
    comes from the repository's own row and from the source's `tenant` row, which every tenant
    reads, and the gates that ask it (`built_on_behind`, `built_on_not_public`) learn nothing of
    the source's profile or content. Nothing here is a read of the source, so the three places
    that say who may read a repository are unchanged, and an unrelated library, a visitor, or this
    repository for any other purpose still reads nothing of it. The release gate still compares
    the source's current release with the one taken: a release made after it went protected is one
    the repository cannot take without an invitation, and it is behind until it has one."""
    row = (
        await session.execute(
            select(Tenant.current_release_id)
            .join(RepositorySubscription, RepositorySubscription.repository_tenant_id == Tenant.id)
            .where(
                RepositorySubscription.subscriber_tenant_id == repository_id,
                RepositorySubscription.repository_tenant_id == source_id,
                RepositorySubscription.source == "protected",
                Tenant.published_at.is_not(None),
                Tenant.delisted_at.is_(None),
            )
        )
    ).first()
    return None if row is None else (row[0],)


async def dependents_over(
    session: AsyncSession, repository_id: uuid.UUID
) -> list[tuple[uuid.UUID, str]]:
    """The repositories whose current release is built on this one and did not include it, public
    or protected, by id and name: the ones that need it to stay reachable. Read through the copy
    records the repository's own side reads (ADR 0204) and the `tenant` rows. A dependent that is
    not published, or is delisted or retired, is not one: no library reads it as a stack."""
    rows = await session.execute(
        select(Tenant.id, Tenant.name)
        .join(RepositoryCopy, RepositoryCopy.tenant_id == Tenant.id)
        .where(
            RepositoryCopy.repository_tenant_id == repository_id,
            Tenant.released_over.contains([repository_id]),
            Tenant.published_at.is_not(None),
            Tenant.delisted_at.is_(None),
            Tenant.deprecated_at.is_(None),
        )
        .order_by(Tenant.name, Tenant.id)
    )
    return [(i, n) for i, n in rows.all()]


async def holders_of(session: AsyncSession, repository_id: uuid.UUID) -> list[uuid.UUID]:
    """The libraries that hold the repository: a grant to it, of any source, or a copy of it. Read
    from the repository's own side (ADR 0204)."""
    ids = set(
        await session.scalars(
            select(RepositorySubscription.subscriber_tenant_id).where(
                RepositorySubscription.repository_tenant_id == repository_id
            )
        )
    )
    ids |= set(
        await session.scalars(
            select(RepositoryCopy.tenant_id).where(
                RepositoryCopy.repository_tenant_id == repository_id
            )
        )
    )
    return sorted(ids, key=str)


async def revoke_protected_through(
    session: AsyncSession, repository_id: uuid.UUID, sources: list[uuid.UUID]
) -> int:
    """A repository stops being a way to a protected one (it is made private or protected, or goes
    on without it): each library that holds it loses the `protected` row it wrote for each of
    `sources` unless another public repository it holds still lists that source. The reads end by
    themselves, since the database asks again each time; this is what the library lists. A row is
    the library's to delete, so each is deleted under that library's own context, which is put
    back to the repository's afterwards. Returns how many rows went."""
    if not sources:
        return 0
    from lorenzo_api.dependencies import set_tenant_rls_context

    libraries = await holders_of(session, repository_id)
    await session.flush()
    removed = 0
    for library in libraries:
        await set_tenant_rls_context(session, library)
        for source in sources:
            row = await session.get(RepositorySubscription, (source, library))
            if row is None or row.source != "protected":
                continue
            still = await session.scalar(
                select(Tenant.id)
                .where(
                    Tenant.id != repository_id,
                    Tenant.released_public.is_(True),
                    Tenant.released_over.contains([source]),
                    or_(
                        Tenant.id.in_(
                            select(RepositorySubscription.repository_tenant_id).where(
                                RepositorySubscription.subscriber_tenant_id == library
                            )
                        ),
                        Tenant.id.in_(
                            select(RepositoryCopy.repository_tenant_id).where(
                                RepositoryCopy.tenant_id == library
                            )
                        ),
                    ),
                )
                .limit(1)
            )
            if still is None:
                await session.delete(row)
                removed += 1
        await session.flush()
    await set_tenant_rls_context(session, repository_id)
    return removed
