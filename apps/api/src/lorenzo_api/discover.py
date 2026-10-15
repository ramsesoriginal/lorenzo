"""Discover: the listing of public repositories - ADR 0292, RFC 0038 section 4.

One query over the profiles of the repositories that are public, published and have a release, and
the tenant row (name, slug), with no ranking: by name or by the date of the latest release, never
by how often a repository was copied. Nothing of the content is read, only what a repository says
of itself and the facts of its current release that a publish wrote to its profile
(`repository_listing.set_listing_facts`). The profile of a public repository is readable by
`discover_read`, a policy that reaches no other table.

A hard maximum page size and a hard maximum depth cap what one caller can walk of the directory.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, any_, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import DiscoverTooDeepError
from lorenzo_api.models import RepositoryProfile, Tenant, TenantKind
from lorenzo_api.schemas.discover import (
    DiscoverFacetOut,
    DiscoverFacetsOut,
    DiscoverItemOut,
    DiscoverReleaseOut,
    DiscoverSort,
    PublisherOut,
)

__all__ = [
    "MAX_DEPTH",
    "MAX_PAGE_SIZE",
    "Listed",
    "facets",
    "item_out",
    "listed",
    "listing_of",
    "search",
]

# The most one request may ask for, and the furthest into a listing it may go (page times size).
MAX_PAGE_SIZE = 50
MAX_DEPTH = 1000
FACET_LIMIT = 100


@dataclass(frozen=True)
class Listed:
    profile: RepositoryProfile
    tenant: Tenant


def listed() -> Select[tuple[RepositoryProfile, Tenant]]:
    """The repositories that are listed: public, published, with a release and not delisted by the
    platform's operators (ADR 0303). Deprecated ones leave when that state exists (RFC 0038 D8)."""
    return (
        select(RepositoryProfile, Tenant)
        .join(Tenant, Tenant.id == RepositoryProfile.tenant_id)
        .where(
            RepositoryProfile.visibility == "public",
            RepositoryProfile.release_label.is_not(None),
            Tenant.kind == TenantKind.REPOSITORY,
            Tenant.published_at.is_not(None),
            Tenant.delisted_at.is_(None),
        )
    )


def item_out(
    profile: RepositoryProfile, tenant: Tenant, publishers: list[PublisherOut]
) -> DiscoverItemOut:
    assert profile.release_label is not None and profile.released_at is not None
    return DiscoverItemOut(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        summary=profile.summary,
        tags=list(profile.tags),
        system=profile.system,
        languages=list(profile.languages),
        has_cover=profile.cover_picture_id is not None,
        release=DiscoverReleaseOut(label=profile.release_label, released_at=profile.released_at),
        entries=profile.entry_count,
        stat_definitions=profile.stat_definition_count,
        publishers=publishers,
    )


def _like(word: str) -> str:
    """`word` as the middle of an ILIKE pattern, with its own wildcards made plain."""
    escaped = word.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def search(
    session: AsyncSession,
    *,
    q: str | None,
    tag: str | None,
    system: str | None,
    language: str | None,
    sort: DiscoverSort,
    page: int,
    size: int,
) -> tuple[list[Listed], int]:
    """One page of the listing, and how many repositories match. `q` is a case-insensitive part
    of the name, the summary or a tag; `tag`, `system` and `language` narrow it exactly (a tag in
    lower case, a language as its code). `DiscoverTooDeepError` past `MAX_DEPTH`."""
    size = max(1, min(size, MAX_PAGE_SIZE))
    page = max(1, page)
    if page * size > MAX_DEPTH:
        raise DiscoverTooDeepError(
            detail=f"A listing goes at most {MAX_DEPTH} repositories deep. Narrow it with a word, "
            "a tag, a game system or a language."
        )
    stmt = listed()
    if q and q.strip():
        pattern = _like(q.strip())
        stmt = stmt.where(
            or_(
                Tenant.name.ilike(pattern, escape="\\"),
                RepositoryProfile.summary.ilike(pattern, escape="\\"),
                func.array_to_string(RepositoryProfile.tags, " ").ilike(pattern, escape="\\"),
            )
        )
    if tag:
        stmt = stmt.where(literal(tag.strip().lower()) == any_(RepositoryProfile.tags))
    if system:
        stmt = stmt.where(func.lower(RepositoryProfile.system) == system.strip().lower())
    if language:
        stmt = stmt.where(literal(language.strip().lower()) == any_(RepositoryProfile.languages))
    total = int(await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    order = (
        (func.lower(Tenant.name), Tenant.id)
        if sort == "name"
        else (RepositoryProfile.released_at.desc(), Tenant.id)
    )
    rows = await session.execute(stmt.order_by(*order).limit(size).offset((page - 1) * size))
    return [Listed(p, t) for p, t in rows.all()], total


_LISTED_SQL = (
    "FROM repository_profile p JOIN tenant t ON t.id = p.tenant_id "
    "WHERE p.visibility = 'public' AND p.release_label IS NOT NULL "
    "AND t.kind = 'repository' AND t.published_at IS NOT NULL AND t.delisted_at IS NULL"
)


async def facets(session: AsyncSession, *, enabled: bool) -> DiscoverFacetsOut:
    """The tags, systems and languages in use among the listed repositories, most used first."""

    async def count(expression: str) -> list[DiscoverFacetOut]:
        rows = await session.execute(
            text(
                f"SELECT value, count(*) AS n FROM (SELECT {expression} AS value {_LISTED_SQL}) v "
                f"WHERE value IS NOT NULL AND value <> '' GROUP BY value "
                f"ORDER BY n DESC, value LIMIT {FACET_LIMIT}"
            )
        )
        return [DiscoverFacetOut(value=value, count=n) for value, n in rows.all()]

    return DiscoverFacetsOut(
        enabled=enabled,
        tags=await count("unnest(p.tags)"),
        systems=await count("lower(p.system)"),
        languages=await count("unnest(p.languages)"),
    )


async def listing_of(session: AsyncSession, repository_id: uuid.UUID) -> Listed | None:
    """One listed repository, or none: not public, not published, or no release yet."""
    row = (await session.execute(listed().where(Tenant.id == repository_id))).first()
    return Listed(row[0], row[1]) if row else None
