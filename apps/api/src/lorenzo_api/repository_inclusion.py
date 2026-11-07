"""Including a repository a repository is built on - ADR 0431, RFC 0051 (H1).

A repository B built on A normally gives a library two steps: A, and B on top of it. B's Owner may
choose, for each repository B is built on, to *include* it: when a release of B is made, B's copies
of A's rows are carried as B's own, so the document names no A and a library never needs to read
it. This module is everything about that choice except where the release is made
(`repository_digest.assess`, `repository_publishing.publish_release`):

- A's *terms*: whether a repository built on A may include it (`terms_of`), and who may include it
  anyway (`includable`).
- The choice itself, kept on B's copy record of A (`set_inclusion`), and the record of how a
  release carried each source (`sources_of`, `Content.sources`, the profile's `release_sources`).
- The flattening of a loaded `Content` (`flatten`): which rows are B's copies of A, and what
  becomes of the links that said so.
- Changing the choice after a public release is a breaking release (`inclusion_changes`).

Reading A goes through `reading_repository` like any read of another tenant's repository: B's
Owner reads A's profile and nothing else of it, and only as far as a grant lets B read it.
"""

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.campaign_access import is_tenant_owner
from lorenzo_api.exceptions import RepositoryNotCopiedError, RepositoryNotIncludableError
from lorenzo_api.models import RepositoryCopy, RepositoryProfile, Tenant
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import Content

__all__ = [
    "INCLUSIONS",
    "Includable",
    "Inclusion",
    "InclusionChange",
    "Source",
    "Terms",
    "default_may_be_included",
    "flatten",
    "included_by",
    "recorded_inclusions",
    "includable",
    "inclusion_changes",
    "release_sources_of",
    "set_inclusion",
    "sources_of",
    "terms_of",
]

Inclusion = Literal["show", "include"]
INCLUSIONS: tuple[Inclusion, ...] = ("show", "include")


# --- A's terms ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class Terms:
    """What a repository built on this one may do with it. H1 has the one switch."""

    may_be_included: bool


def default_may_be_included(visibility: str) -> bool:
    """What an Owner who said nothing allows: a public repository can be included, since anyone
    can copy it anyway and so, to the same effect, hold its rows; a private one cannot, which
    makes inclusion available to its Owners only (RFC 0051, the decided defaults)."""
    return visibility == "public"


def terms_of(profile: RepositoryProfile | None) -> Terms:
    """A repository's terms as they stand: an Owner's own value where there is one, else the
    default for its visibility. A repository with no profile row is private, with no terms said."""
    visibility = profile.visibility if profile is not None else "private"
    explicit = profile.may_be_included if profile is not None else None
    return Terms(
        may_be_included=default_may_be_included(visibility) if explicit is None else explicit
    )


@dataclass(frozen=True)
class Includable:
    """Whether a user may include a repository, and why: they own it, or its terms allow it."""

    allowed: bool
    by: Literal["owner", "terms"] | None = None


async def includable(session: AsyncSession, source_id: uuid.UUID, user_id: uuid.UUID) -> Includable:
    """Whether `user_id` may include the repository `source_id` in a repository they own: they own
    it, or its terms allow it and the tenant of the session can read its profile (a grant, or it is
    public). One Owner's content is not published by another without a yes: a grant to read the
    repository is not that yes."""
    if await is_tenant_owner(session, tenant_id=source_id, user_id=user_id):
        return Includable(True, "owner")
    async with reading_repository(session, source_id) as readable:
        if readable and terms_of(await session.get(RepositoryProfile, source_id)).may_be_included:
            return Includable(True, "terms")
    return Includable(False)


# --- The choice and the record of it -----------------------------------------------------------


@dataclass(frozen=True)
class Source:
    """A repository another is built on, and how the first carries it. `licence` is a snapshot of
    A's licence as its profile says it, `{label, url}`, or none when it says none or cannot be
    read; `readable` says whether A could be read through the gated read just now."""

    repository_id: uuid.UUID
    name: str
    inclusion: str
    licence: dict[str, Any] | None
    readable: bool

    def record(self) -> dict[str, Any]:
        """How a release document records it (`Content.sources`)."""
        return {"inclusion": self.inclusion, "name": self.name, "licence": self.licence}


async def sources_of(session: AsyncSession, repository_id: uuid.UUID) -> list[Source]:
    """Every repository this one has copied, by name, with the choice made for it and the
    snapshot a release records: its name, and its licence if its profile can be read."""
    rows = await session.execute(
        select(RepositoryCopy, Tenant.name)
        .join(Tenant, Tenant.id == RepositoryCopy.repository_tenant_id)
        .where(RepositoryCopy.tenant_id == repository_id)
        .order_by(Tenant.name, RepositoryCopy.repository_tenant_id)
    )
    found: list[Source] = []
    for copy, name in rows.all():
        licence: dict[str, Any] | None = None
        async with reading_repository(session, copy.repository_tenant_id) as readable:
            if readable:
                profile = await session.get(RepositoryProfile, copy.repository_tenant_id)
                if profile is not None and profile.licence_label is not None:
                    licence = {"label": profile.licence_label, "url": profile.licence_url}
        found.append(Source(copy.repository_tenant_id, name, copy.inclusion, licence, readable))
    return found


async def set_inclusion(
    session: AsyncSession,
    *,
    repository_id: uuid.UUID,
    source_id: uuid.UUID,
    inclusion: Inclusion,
    user_id: uuid.UUID,
) -> RepositoryCopy:
    """Sets how the repository carries `source_id`, which it must have copied
    (`RepositoryNotCopiedError`). `include` needs the user to be allowed to include it
    (`409 repository-not-includable`); `show` is always allowed. Flushes; the caller records it
    and commits."""
    copy = await session.get(RepositoryCopy, (repository_id, source_id))
    if copy is None:
        raise RepositoryNotCopiedError(detail=f"Copy repository {source_id} first")
    if inclusion == "include" and not (await includable(session, source_id, user_id)).allowed:
        name = copy.repository_name or str(source_id)
        raise RepositoryNotIncludableError(
            detail=f"{name} cannot be included here: its Owner has not allowed it, and you are "
            "not an Owner of it. Ask its Owner to allow it, or keep it separate.",
            repositories=[{"id": str(source_id), "name": name}],
        )
    copy.inclusion = inclusion
    await session.flush()
    return copy


def release_sources_of(content: Content) -> list[dict[str, Any]]:
    """What the profile keeps of how a release carried what it is built on: one record for each,
    by name, from `Content.sources`."""
    return [
        {
            "id": str(source_id),
            "name": source["name"],
            "inclusion": source["inclusion"],
            "licence_label": (source["licence"] or {}).get("label"),
            "licence_url": (source["licence"] or {}).get("url"),
        }
        for source_id, source in sorted(
            content.sources.items(), key=lambda item: (item[1]["name"], str(item[0]))
        )
    ]


def recorded_inclusions(profile: RepositoryProfile | None) -> dict[str, str]:
    """How the profile's current public release carried each repository it was built on, by id:
    empty before its first public release."""
    return {s["id"]: s["inclusion"] for s in (profile.release_sources if profile else None) or []}


def included_by(release_sources: Iterable[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    """The records of a release that were carried included."""
    return [s for s in release_sources or [] if s["inclusion"] == "include"]


# --- Flattening --------------------------------------------------------------------------------


def flatten(content: Content, included: set[uuid.UUID]) -> None:
    """Makes B's copies of the repositories in `included` B's own, in place. A row of B is a copy
    of A's when its copy link names A as its origin's tenant: those rows are every entry, stat
    group and stat definition B copied from A (and, for a stat group or definition, the ones B
    merged A's into, which B keeps as its own and now carries). Their links go: the rows are no
    longer copies, so `Content.own` is true of them and a library takes them as B's, with B's
    ids as their origins. Everything about A that only a copy link kept goes with them: what B
    deleted of A's (it is not carried either), the snapshots of A's rows, the attachments taken
    from A (a parent B put on a row it holds is still found, as the edge itself, from the
    prototypes), and A in the repositories B is built on, so the manifest of a library has no A.

    What B holds of other repositories is untouched, A's rows that refer to them included: they
    reach a library through the copy links of those repositories, as before."""
    if not included:
        return
    links = content.links
    gone = {source for source, tenant in links.origin_tenant.items() if tenant in included}
    for kind in ("entity", "stat_group", "stat_definition"):
        copied = getattr(links, kind)
        for local_id in [local for local, origin in copied.items() if origin in gone]:
            del copied[local_id]
        if kind in links.deleted:
            links.deleted[kind] -= gone
            if not links.deleted[kind]:
                del links.deleted[kind]
    links.merged -= gone
    for source in gone:
        links.snapshots.pop(source, None)
        links.origin_tenant.pop(source, None)
    for tenant in included:
        links.attachments.pop(tenant, None)
    links.copies -= included


# --- Changing the choice -----------------------------------------------------------------------


@dataclass(frozen=True)
class InclusionChange:
    """A repository carried differently from how the last public release carried it."""

    repository_id: uuid.UUID
    name: str
    before: str
    after: str

    def as_json(self) -> dict[str, str]:
        return {
            "repository_id": str(self.repository_id),
            "name": self.name,
            "before": self.before,
            "after": self.after,
        }


def inclusion_changes(
    before: Iterable[Mapping[str, Any]] | None, after: Mapping[uuid.UUID, Mapping[str, Any]]
) -> list[InclusionChange]:
    """The repositories in `after` (`Content.sources`: what a release would record) whose choice
    differs from the one `before` records (the profile's `release_sources`: what the current
    public release recorded). A change is breaking, because the rows a library holds change
    origin: from separate to included they arrive as B's, and the other way they leave B's.

    Nothing is a change before the first public release (`before` is none), and a repository that
    is new since the release (it has no record) is not one either: its rows are added, which
    updates are for. A record is about the repositories a release was made against, so a
    repository whose last public release was made before this was recorded has no baseline and
    no change is found (ADR 0431 names it)."""
    if before is None:
        return []
    recorded = {uuid.UUID(s["id"]): s["inclusion"] for s in before}
    return [
        InclusionChange(source_id, now["name"], recorded[source_id], now["inclusion"])
        for source_id, now in sorted(after.items(), key=lambda i: (i[1]["name"], str(i[0])))
        if source_id in recorded and recorded[source_id] != now["inclusion"]
    ]
