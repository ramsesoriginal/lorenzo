"""What another tenant reads of a repository - ADR 0286, RFC 0037 §4 and §5.

A private repository is read live, as ADR 0118 drew it: the rows as they are now. A public one
is read through its current release: the document made when it was released, so that what its
author edits after is seen by nobody until the next release. `load_upstream` is the one function
that tells the two apart, and everything a library does with a repository before and after
copying it (the copy planner, the update engine, the manifest, browsing) reads through it. The
engines take a `Content` and cannot tell which they were given.

Every function here runs inside `reading_repository` (ADR 0118), which is where a library may
see the repository's rows, the profile that says which kind it is, and its release documents.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import PublicRepositoryHasNoReleaseError
from lorenzo_api.models import RepositoryCopy, RepositoryProfile, StatValueType
from lorenzo_api.release_document_store import (
    ReleaseDocumentNotFoundError,
    read_release_content,
    read_release_copies,
)
from lorenzo_api.repository_content import Content, load_content
from lorenzo_api.repository_releases import ReleaseRef, current_release
from lorenzo_api.schemas.repositories import EntityKindName

__all__ = [
    "EntityRow",
    "StatDefinitionRow",
    "StatGroupRow",
    "Upstream",
    "entity_rows",
    "is_public",
    "load_upstream",
    "stat_group_rows",
    "upstream_copies",
]

# The order a browse names an entry's kinds in, as `GET .../entities` has always answered.
_KIND_ORDER: tuple[EntityKindName, ...] = ("item", "item_instance", "being", "character", "fact")


@dataclass(frozen=True)
class Upstream:
    """A repository as another tenant reads it: its content, and the release that content is
    (the one a copy records as taken). A private repository's content is its rows now, and
    its release is the newest, if it has made one."""

    content: Content
    release: ReleaseRef | None
    public: bool


async def is_public(session: AsyncSession, repository_id: uuid.UUID) -> bool:
    """Whether the repository's profile says `public`. A repository with no profile row is
    private, as the profile's own default is."""
    visibility = await session.scalar(
        select(RepositoryProfile.visibility).where(RepositoryProfile.tenant_id == repository_id)
    )
    return visibility == "public"


def _no_release(repository_id: uuid.UUID, why: str) -> PublicRepositoryHasNoReleaseError:
    return PublicRepositoryHasNoReleaseError(
        detail=f"Repository {repository_id} is public and {why}: nothing to read yet"
    )


async def _current_document_release(session: AsyncSession, repository_id: uuid.UUID) -> ReleaseRef:
    release = await current_release(session, repository_id)
    if release is None:
        raise _no_release(repository_id, "has not made a release")
    return release


async def load_upstream(session: AsyncSession, repository_id: uuid.UUID) -> Upstream:
    """The repository as a library reads it: the current release's document if it is public,
    its rows now if it is private. `409 public-repository-has-no-release` for a public one with
    no release, or whose current release has no document: nothing is read live instead, since
    that would show edits no release has announced."""
    if not await is_public(session, repository_id):
        return Upstream(
            await load_content(session, repository_id),
            await current_release(session, repository_id),
            public=False,
        )
    release = await _current_document_release(session, repository_id)
    try:
        content = await read_release_content(
            session, tenant_id=repository_id, release_id=release.id
        )
    except ReleaseDocumentNotFoundError:
        raise _no_release(repository_id, f"its release {release.label} has no document") from None
    return Upstream(content, release, public=True)


async def upstream_copies(session: AsyncSession, repository_id: uuid.UUID) -> set[uuid.UUID]:
    """The repositories the repository is built on: what it has copied now, if it is private,
    and what it had copied when its current release was made, if it is public. A document
    carries the same set as the copy records, so the manifest of a public repository is the one
    that release was made against."""
    if not await is_public(session, repository_id):
        return set(
            await session.scalars(
                select(RepositoryCopy.repository_tenant_id).where(
                    RepositoryCopy.tenant_id == repository_id
                )
            )
        )
    release = await _current_document_release(session, repository_id)
    try:
        return await read_release_copies(session, tenant_id=repository_id, release_id=release.id)
    except ReleaseDocumentNotFoundError:
        raise _no_release(repository_id, f"its release {release.label} has no document") from None


# --- Browsing a document -----------------------------------------------------------------------


@dataclass(frozen=True)
class EntityRow:
    id: uuid.UUID
    name: str
    kinds: list[EntityKindName]
    prototype_ids: list[uuid.UUID]


@dataclass(frozen=True)
class StatDefinitionRow:
    id: uuid.UUID
    name: str
    value_type: StatValueType
    enum_values: list[str]


@dataclass(frozen=True)
class StatGroupRow:
    id: uuid.UUID
    name: str
    priority: int
    mandatory: bool
    definitions: list[StatDefinitionRow]


def entity_rows(
    content: Content, q: str | None = None, *, public_only: bool = False
) -> list[EntityRow]:
    """The entries of a `Content` as a browse lists them: by name and then id, `q` a
    case-insensitive part of the name, kinds in the order the live browse gives them, and
    parents in each entry's own order. What the live browse reads from the tables, from the
    document."""
    prototypes: dict[uuid.UUID, list[uuid.UUID]] = {}
    for entity_id, prototype_id in content.prototypes:
        if not public_only or content.entry_audiences.get(prototype_id, True):
            prototypes.setdefault(entity_id, []).append(prototype_id)
    needle = q.casefold() if q is not None else None
    return [
        EntityRow(
            id=entity_id,
            name=name,
            kinds=[k for k in _KIND_ORDER if k in content.kinds.get(entity_id, ())],
            prototype_ids=prototypes.get(entity_id, []),
        )
        for entity_id, name in sorted(content.entities.items(), key=lambda e: (e[1], str(e[0])))
        if (needle is None or needle in name.casefold())
        and (not public_only or content.entry_audiences.get(entity_id, True))
    ]


def stat_group_rows(content: Content) -> list[StatGroupRow]:
    """The stat groups of a `Content`, highest priority first and then by name, each with its
    definitions by name and an enum's values in their order."""
    definitions: dict[uuid.UUID, list[StatDefinitionRow]] = {g: [] for g in content.groups}
    for definition_id, definition in sorted(
        content.definitions.items(), key=lambda d: (d[1]["name"], str(d[0]))
    ):
        values = sorted(content.enum_values.get(definition_id, []), key=lambda v: (v[1], v[0]))
        definitions[definition["group"]].append(
            StatDefinitionRow(
                id=definition_id,
                name=definition["name"],
                value_type=definition["value_type"],
                enum_values=[value for value, _ in values],
            )
        )
    return [
        StatGroupRow(
            id=group_id,
            name=group["name"],
            priority=group["priority"],
            mandatory=group["mandatory"],
            definitions=definitions[group_id],
        )
        for group_id, group in sorted(
            content.groups.items(), key=lambda g: (-g[1]["priority"], g[1]["name"], str(g[0]))
        )
    ]
