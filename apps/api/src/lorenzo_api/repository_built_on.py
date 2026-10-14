"""What a repository is built on, as the rules of making it public and publishing it ask -
ADR 0289, RFC 0037 §6, RFC 0038 §7.

A repository is built on the repositories it has copied (`repository_copy`, ADR 0120). Three
questions about that set: whether each of them has a release this repository has not taken
(`built_on_behind`, the bridge-skew gate), whether each is public (`built_on_not_public`, a rule
of making this one public), and the other way round, which public repositories are built on this
one (`public_dependents`, a rule of making it private). Each reads the other repository through
the gated read, as any tenant does, so what it learns of one it cannot read is that it cannot.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.campaign_access import is_tenant_owner
from lorenzo_api.models import RepositoryCopy, Tenant, TenantKind
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_releases import ReleaseRef, current_release, releases_named
from lorenzo_api.repository_upstream import is_public

__all__ = [
    "Behind",
    "built_on_behind",
    "built_on_not_public",
    "public_dependents",
]


def _ref_json(release: ReleaseRef | None) -> dict[str, Any] | None:
    if release is None:
        return None
    return {"id": str(release.id), "number": release.number, "label": release.label}


@dataclass(frozen=True)
class Behind:
    """A repository this one is built on, and where this one stands with it."""

    repository_id: uuid.UUID
    name: str
    # The release this repository last took of it, if it can be told, and the one it has now.
    taken: ReleaseRef | None
    current: ReleaseRef | None
    # False when it cannot be read (unpublished, or no longer granted), so nothing is known.
    readable: bool

    def as_json(self) -> dict[str, Any]:
        return {
            "repository_id": str(self.repository_id),
            "name": self.name,
            "taken": _ref_json(self.taken),
            "current": _ref_json(self.current),
            "readable": self.readable,
        }


async def _copies(
    session: AsyncSession, repository_id: uuid.UUID
) -> list[tuple[RepositoryCopy, str]]:
    """The repository's own copy records with the name of what each copied; one whose
    repository has gone is left out."""
    rows = await session.execute(
        select(RepositoryCopy, Tenant.name)
        .join(Tenant, Tenant.id == RepositoryCopy.repository_tenant_id)
        .where(RepositoryCopy.tenant_id == repository_id)
        .order_by(Tenant.name, RepositoryCopy.repository_tenant_id)
    )
    return [(copy, name) for copy, name in rows.all()]


async def built_on_behind(session: AsyncSession, repository_id: uuid.UUID) -> list[Behind]:
    """The repositories this one is built on whose current release is not the one this one took
    (a copy from before releases took none), or that cannot be read. Empty when this repository
    is built on nothing. Both directions count: a repository authored against an older or a
    newer state than the one it is built on gives a library rows ADR 0120 drops."""
    found: list[Behind] = []
    for copy, name in await _copies(session, repository_id):
        upstream = copy.repository_tenant_id
        async with reading_repository(session, upstream) as readable:
            if not readable:
                found.append(Behind(upstream, name, None, None, readable=False))
                continue
            current = await current_release(session, upstream)
            taken = (
                (await releases_named(session, upstream, [copy.synced_release_id])).get(
                    copy.synced_release_id
                )
                if copy.synced_release_id
                else None
            )
        if (current.id if current else None) != copy.synced_release_id:
            found.append(Behind(upstream, name, taken, current, readable=True))
    return found


async def built_on_not_public(
    session: AsyncSession, repository_id: uuid.UUID, user_id: uuid.UUID
) -> list[dict[str, Any]]:
    """The repositories this one is built on that are not public and published, each with whether
    `user_id` owns it (so they can be offered to make it public): the ones that stop this
    repository being made public."""
    found: list[dict[str, Any]] = []
    for copy, name in await _copies(session, repository_id):
        upstream = copy.repository_tenant_id
        async with reading_repository(session, upstream) as readable:
            public = readable and await is_public(session, upstream)
        if not public:
            found.append(
                {
                    "id": str(upstream),
                    "name": name,
                    "owned": await is_tenant_owner(session, tenant_id=upstream, user_id=user_id),
                }
            )
    return found


async def public_dependents(
    session: AsyncSession, repository_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    """The public, published repositories built on this one, which making it private would leave
    without a dependency a library can copy. Read through the repository's own side of the copy
    records (ADR 0204: the owner reads who copied it). `owned` says whether
    `user_id` owns the dependent, so a dialog can link to it."""
    rows = await session.execute(
        select(RepositoryCopy.tenant_id, Tenant.name)
        .join(Tenant, Tenant.id == RepositoryCopy.tenant_id)
        .where(
            RepositoryCopy.repository_tenant_id == repository_id,
            Tenant.kind == TenantKind.REPOSITORY,
        )
        .order_by(Tenant.name, RepositoryCopy.tenant_id)
    )
    found: list[dict[str, Any]] = []
    for dependent, name in rows.all():
        async with reading_repository(session, dependent) as readable:
            public = readable and await is_public(session, dependent)
        if public:
            owned = user_id is not None and await is_tenant_owner(
                session, tenant_id=dependent, user_id=user_id
            )
            found.append({"id": str(dependent), "name": name, "owned": owned})
    return found
