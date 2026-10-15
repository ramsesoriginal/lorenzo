"""Discover: the listing, its facets and a repository's storefront - ADR 0292, RFC 0038 section 4.

For any signed-in user, with or without a library. `GET /discover/repositories` lists the public
repositories (by name or by the date of their latest release, never by how often they were
copied), `GET /discover/facets` says what the listing can be narrowed by, and `GET
/discover/repositories/{id}` is a repository's page. Nothing of what a repository holds is read
here: what is looked at before copying is the preview (RFC 0038 section 5) and the rest of what a
public repository offers is under `/repositories/{id}`.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from lorenzo_api.config import get_settings
from lorenzo_api.dependencies import NO_TENANT, PublicReader, SessionDep
from lorenzo_api.discover import (
    MAX_PAGE_SIZE,
    facets,
    item_out,
    listing_of,
    search,
)
from lorenzo_api.exceptions import RepositoryNotFoundError
from lorenzo_api.repository_profiles import profile_out
from lorenzo_api.repository_publishers import publishers_of, report_mailto
from lorenzo_api.schemas.discover import (
    DiscoverFacetsOut,
    DiscoverPageOut,
    DiscoverSort,
    StorefrontOut,
)

router = APIRouter(prefix="/discover", tags=["discover"])


@router.get("/repositories")
async def list_public_repositories(
    session: SessionDep,
    user: PublicReader,
    q: Annotated[str | None, Query(max_length=100)] = None,
    tag: Annotated[str | None, Query(max_length=100)] = None,
    system: Annotated[str | None, Query(max_length=100)] = None,
    language: Annotated[str | None, Query(max_length=35)] = None,
    sort: DiscoverSort = "name",
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1)] = 20,
) -> DiscoverPageOut:
    """The public repositories, a page at a time: by `name` or by the date of the latest
    `released`, never by popularity. `q` is a case-insensitive part of the name, the summary or a
    tag; `tag`, `system` and `language` narrow it exactly. A page is at most 50 repositories (a
    bigger `size` is that), and a listing goes at most 1000 deep: `422 discover-too-deep`, narrow
    it. Listed are repositories that are public, published and have a release. Each says who
    published it, by its Owners' accounts (`publishers`, ADR 0299)."""
    found, total = await search(
        session,
        q=q,
        tag=tag,
        system=system,
        language=language,
        sort=sort,
        page=page,
        size=size,
    )
    clamped = max(1, min(size, MAX_PAGE_SIZE))
    publishers = await publishers_of(
        session, [f.tenant.id for f in found], current_tenant_id=NO_TENANT
    )
    return DiscoverPageOut(
        items=[item_out(f.profile, f.tenant, publishers[f.tenant.id]) for f in found],
        total=total,
        page=max(1, page),
        size=clamped,
        pages=-(-total // clamped),
    )


@router.get("/facets")
async def discover_facets(session: SessionDep, user: PublicReader) -> DiscoverFacetsOut:
    """The tags, game systems and languages in use among the listed repositories, the most used
    first, at most a hundred of each, for the filters of the listing."""
    return await facets(session, enabled=get_settings().public_repositories_enabled)


@router.get("/repositories/{repository_id}")
async def get_storefront(
    repository_id: uuid.UUID, session: SessionDep, user: PublicReader
) -> StorefrontOut:
    """A listed repository's page: its listing entry (with who published it, by its Owners'
    accounts), its long description, its profile and, where the deployment sets a report address,
    a `mailto:` for the Report link.
    `404` for one that is not listed (private, a draft, or with no release), the same as for one
    that does not exist."""
    found = await listing_of(session, repository_id)
    if found is None:
        raise RepositoryNotFoundError(detail=f"No public repository {repository_id}")
    publishers = await publishers_of(session, [repository_id], current_tenant_id=NO_TENANT)
    return StorefrontOut(
        item=item_out(found.profile, found.tenant, publishers[repository_id]),
        description=found.tenant.description,
        profile=profile_out(found.profile, stamp=found.tenant.updated_at),
        report_mailto=report_mailto(
            get_settings().report_address, name=found.tenant.name, repository_id=repository_id
        ),
    )
