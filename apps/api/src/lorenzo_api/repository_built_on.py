"""What a repository is built on, as the rules of making it public and publishing it ask -
ADR 0289, RFC 0037 §6, RFC 0038 §7, RFC 0051.

A repository is built on the repositories it has copied (`repository_copy`, ADR 0120). Three
questions about that set: whether each of them has a release this repository has not taken
(`built_on_behind`, the bridge-skew gate), whether each can be reached (`built_on_not_public`, a
rule of making this one public or protected), and the other way round, which public or protected
repositories are built on this one (`public_dependents`, a rule of making it private). Each reads
the other repository through the gated read, as any tenant does, so what it learns of one it cannot
read is that it cannot.

*Reached* (ADR 0434) is what the stack rule asks of a source: public, protected, or included.
A library that copies a repository gets the repositories it is built on as steps, and a protected
one is read as a step of that copy and nowhere else, so it can stay protected; a private one cannot
be granted to a library by an Owner who never saw it, so it has to be included.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.campaign_access import is_tenant_owner
from lorenzo_api.models import RepositoryCopy, RepositoryProfile, Tenant
from lorenzo_api.repository_access import reading_repository_held
from lorenzo_api.repository_inclusion import (
    includable,
    recorded_inclusions,
    showable,
    terms_of,
)
from lorenzo_api.repository_reach import dependents_over, held_protected
from lorenzo_api.repository_releases import ReleaseRef, current_release, releases_named
from lorenzo_api.repository_upstream import DOCUMENT_VISIBILITIES, visibility_of

__all__ = [
    "Behind",
    "built_on_behind",
    "built_on_not_public",
    "built_on_sources",
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
    newer state than the one it is built on gives a library rows ADR 0120 drops. A protected one
    is read through the public repository this one holds that lists it (ADR 0434); one it cannot
    read that it holds a copy of is compared by the release `tenant` says is current
    (`held_protected`), so a repository that copied a public repository goes on releasing when it
    becomes protected."""
    found: list[Behind] = []
    for copy, name in await _copies(session, repository_id):
        upstream = copy.repository_tenant_id
        async with reading_repository_held(session, upstream) as readable:
            if not readable:
                # A source it cannot read but holds a copy of, protected since (ADR 0434): what
                # it took is current while the source has made no release since. One it cannot
                # take is behind, and so is one it holds no copy of.
                held = await held_protected(session, repository_id, upstream)
                if held is None or held[0] != copy.synced_release_id:
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
    """The repositories this one is built on that cannot be reached, each with whether `user_id`
    owns it (so they can be offered to make it public): the ones that stop this repository being
    made public or protected. A source is reached when it is public or protected and this
    repository can read it (ADR 0434), or when this repository includes it, since its release
    carries it as its own rows (ADR 0431); whether the user may include it is asked once, when
    the choice is set (`set_inclusion`), or when it holds a copy of it that it cannot read now
    because it is protected since (`held_protected`). Any other source it cannot read counts as
    not reached."""
    found: list[dict[str, Any]] = []
    for copy, name in await _copies(session, repository_id):
        if copy.inclusion == "include":
            continue
        upstream = copy.repository_tenant_id
        async with reading_repository_held(session, upstream) as readable:
            reached = readable and await visibility_of(session, upstream) in DOCUMENT_VISIBILITIES
        # A copy it holds of a repository that is protected since, which it cannot read now, is
        # reached too (ADR 0434): the copy was taken while it could, and its release lists it.
        reached = reached or (
            not readable and await held_protected(session, repository_id, upstream) is not None
        )
        if not reached:
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
    """The public or protected, published repositories built on this one, which making it private
    would leave without a dependency a library can copy. Read through the repository's own side
    of the copy records (ADR 0204: the owner reads who copied it) and the facts each one keeps on
    its `tenant` row of what its current release is built on (ADR 0434). `owned` says whether
    `user_id` owns the dependent, so a dialog can link to it. A dependent whose current release
    carries this repository included has no dependency on it for a library to copy, so making this
    one private leaves it as it is, and it is not here (ADR 0431): what a release carries is what
    it recorded, not the choice the dependent has made since. A dependent that is delisted or
    retired is not read by any library as a stack, so it does not stop it either."""
    found: list[dict[str, Any]] = []
    for dependent, name in await dependents_over(session, repository_id):
        owned = user_id is not None and await is_tenant_owner(
            session, tenant_id=dependent, user_id=user_id
        )
        found.append({"id": str(dependent), "name": name, "owned": owned})
    return found


async def built_on_sources(
    session: AsyncSession, repository_id: uuid.UUID, user_id: uuid.UUID
) -> list[dict[str, Any]]:
    """Each repository this one is built on, as the Owner sees it before making this one public
    (ADR 0431, ADR 0434): whether it is public or protected, whether `user_id` owns it, how this
    repository carries it (`inclusion`), whether the user may include it and why (`include_by`:
    they own it, or its terms allow it), whether they may keep it separate and visible and why
    (`show_by`), and how the current public release carried it (`in_release`, null where there is
    none or it was built on later). In the order of the manifest's names."""
    recorded = recorded_inclusions(await session.get(RepositoryProfile, repository_id))
    found: list[dict[str, Any]] = []
    for copy, name in await _copies(session, repository_id):
        upstream = copy.repository_tenant_id
        async with reading_repository_held(session, upstream) as readable:
            visibility = await visibility_of(session, upstream) if readable else None
            terms = terms_of(await session.get(RepositoryProfile, upstream)) if readable else None
        if not readable and await held_protected(session, repository_id, upstream) is not None:
            visibility = "protected"
        can = await includable(session, upstream, user_id)
        may_show = await showable(session, upstream, user_id)
        found.append(
            {
                "id": str(upstream),
                "name": name,
                "public": visibility == "public",
                "protected": visibility == "protected",
                "owned": await is_tenant_owner(session, tenant_id=upstream, user_id=user_id),
                "inclusion": copy.inclusion,
                "includable": can.allowed,
                "include_by": can.by,
                "showable": may_show.allowed,
                "show_by": may_show.by,
                "may_be_shown": terms.may_be_shown if terms is not None else True,
                "in_release": recorded.get(str(upstream)),
            }
        )
    return found
