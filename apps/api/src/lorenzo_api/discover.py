"""Discover: the listing of public repositories - ADR 0292, RFC 0038 section 4.

One query over the profiles of the repositories that are public, published and have a release, and
the tenant row (name, slug), with no ranking: by name or by the date of the latest release, never
by how often a repository was copied. Nothing of the content is read, only what a repository says
of itself and the facts of its current release that a publish wrote to its profile
(`repository_listing.set_listing_facts`). The profile of a public repository is readable by
`discover_read`, a policy that reaches no other table.

A public repository whose Owner turned listing off (ADR 0432) is left out of the listing, its facets
and its search, by `listed()`, `_LISTED_SQL` and `discover_read`, which say the same thing; its
storefront is still read by its address (`storefront_of`).

A hard maximum page size and a hard maximum depth cap what one caller can walk of the directory.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import Select, any_, func, literal, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import DiscoverTooDeepError
from lorenzo_api.models import RepositoryProfile, Tenant, TenantKind
from lorenzo_api.repository_access import reading_repository
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
    "public_repository",
    "search",
    "storefront_of",
]

# The most one request may ask for, and the furthest into a listing it may go (page times size).
MAX_PAGE_SIZE = 50
MAX_DEPTH = 1000
FACET_LIMIT = 100


@dataclass(frozen=True)
class Listed:
    profile: RepositoryProfile
    tenant: Tenant


def public_repository() -> Select[tuple[RepositoryProfile, Tenant]]:
    """The repositories a signed-in user may open by their address: public, published, with a
    release, not delisted by the platform's operators (ADR 0303) and not retired by their Owner
    (ADR 0384), whether or not they are on Discover. A storefront is read through this."""
    return (
        select(RepositoryProfile, Tenant)
        .join(Tenant, Tenant.id == RepositoryProfile.tenant_id)
        .where(
            RepositoryProfile.visibility == "public",
            RepositoryProfile.release_label.is_not(None),
            Tenant.kind == TenantKind.REPOSITORY,
            Tenant.published_at.is_not(None),
            Tenant.delisted_at.is_(None),
            Tenant.deprecated_at.is_(None),
        )
    )


def listed() -> Select[tuple[RepositoryProfile, Tenant]]:
    """The repositories Discover lists: those above whose Owner has not turned listing off (ADR
    0432). The listing, its facets and its search read this and nothing else; `_LISTED_SQL` and the
    `discover_read` policy say the same thing."""
    return public_repository().where(RepositoryProfile.listed.is_(True))


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
        systems=list(profile.systems or []),
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
        wanted = system.strip().lower()
        stmt = stmt.where(
            or_(
                func.lower(RepositoryProfile.system) == wanted,
                literal(wanted) == any_(RepositoryProfile.systems),
            )
        )
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
    "AND t.kind = 'repository' AND t.published_at IS NOT NULL AND t.delisted_at IS NULL "
    "AND t.deprecated_at IS NULL AND p.listed"
)


# What a repository says of its game system: the label its Owner wrote and the slugs of the
# systems its release carries, each once (ADR 0453).
_SYSTEM_VALUES = (
    "ARRAY(SELECT DISTINCT s FROM unnest(ARRAY[lower(p.system)] || p.systems) s "
    "WHERE s IS NOT NULL)"
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
        systems=await count(f"unnest({_SYSTEM_VALUES})"),
        languages=await count("unnest(p.languages)"),
    )


async def storefront_of(session: AsyncSession, repository_id: uuid.UUID) -> Listed | None:
    """One repository a visitor may open by its address, or none: not public, not published, no
    release yet, delisted or retired. Whether Discover lists it is not asked (ADR 0432): an
    unlisted repository is opened by its address like any public one.

    It is read through the gated read, whose public branch answers for a published repository whose
    profile says `public` and is not delisted or retired, and not through `discover_read`, which
    answers only for what is listed. The caller reads what it needs of the result (the publishers,
    which switch the context) after this returns."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            return None
        row = (await session.execute(public_repository().where(Tenant.id == repository_id))).first()
    return Listed(row[0], row[1]) if row else None
