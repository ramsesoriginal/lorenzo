"""What anyone signed in may read of a public repository - ADR 0287, RFC 0038 section 3.

The same reads a granted library has under `/tenants/{tenant_id}/repositories/{id}` (the profile
and its cover, the releases, the entries and stat groups to browse, what it is built on), without
a tenant: a user with no library asks them as they are, and a library asks them before it has
copied. They go through the gated read like every other, whose public branch answers for a
published repository whose profile says `public` and for nothing else, so a private repository, a
draft and one that does not exist are the same `404`. What is read of a public repository is its
current release (ADR 0286).
"""

import uuid

from fastapi import APIRouter
from fastapi.responses import Response
from fastapi_pagination import Page
from sqlalchemy import select

from lorenzo_api.dependencies import ParamsDep, PublicReader, SessionDep
from lorenzo_api.exceptions import ProfilePictureNotFoundError, RepositoryNotFoundError
from lorenzo_api.models import ProfilePicture, RepositoryProfile, Tenant
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_copying import dependencies_of
from lorenzo_api.repository_profiles import profile_out
from lorenzo_api.routers.repositories import entities_page, releases_page, stat_groups_of
from lorenzo_api.schemas.repositories import (
    PublicDependencyOut,
    ReleaseOut,
    RepositoryEntityOut,
    RepositoryStatGroupOut,
)
from lorenzo_api.schemas.repository_profiles import RepositoryProfileOut

router = APIRouter(prefix="/repositories", tags=["repositories"])


def _not_found(repository_id: uuid.UUID) -> RepositoryNotFoundError:
    return RepositoryNotFoundError(detail=f"No public repository {repository_id}")


@router.get("/{repository_id}/profile")
async def get_public_repository_profile(
    repository_id: uuid.UUID, session: SessionDep, user: PublicReader
) -> RepositoryProfileOut:
    """What the Owner of a public repository says of it: summary, licence, credits, tags, system,
    languages. `404` for a repository that is not public and published."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise _not_found(repository_id)
        profile = await session.get(RepositoryProfile, repository_id)
        repository = await session.get_one(Tenant, repository_id)
        return profile_out(profile, stamp=repository.updated_at)


@router.get("/{repository_id}/profile/cover")
async def get_public_repository_cover(
    repository_id: uuid.UUID, session: SessionDep, user: PublicReader
) -> Response:
    """The cover of a public repository, as above."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise _not_found(repository_id)
        profile = await session.get(RepositoryProfile, repository_id)
        if profile is None or profile.cover_picture_id is None:
            raise ProfilePictureNotFoundError(
                detail=f"No cover picture for repository {repository_id}"
            )
        picture = await session.get_one(ProfilePicture, profile.cover_picture_id)
        return Response(content=picture.data, media_type=picture.file_type)


@router.get("/{repository_id}/releases")
async def list_public_repository_releases(
    repository_id: uuid.UUID, session: SessionDep, params: ParamsDep, user: PublicReader
) -> Page[ReleaseOut]:
    """What a public repository has released, newest first (ADR 0207)."""
    return await releases_page(session, repository_id, params, lambda: _not_found(repository_id))


@router.get("/{repository_id}/entities")
async def browse_public_repository_entities(
    repository_id: uuid.UUID,
    session: SessionDep,
    params: ParamsDep,
    user: PublicReader,
    q: str | None = None,
) -> Page[RepositoryEntityOut]:
    """A public repository's entities at its current release: each one's name, kinds and
    prototypes, never its text (ADR 0118, 0286). `q` filters by name."""
    return await entities_page(
        session, repository_id, params, q, lambda: _not_found(repository_id), holder=False
    )


@router.get("/{repository_id}/stat-groups")
async def browse_public_repository_stat_groups(
    repository_id: uuid.UUID, session: SessionDep, user: PublicReader
) -> list[RepositoryStatGroupOut]:
    """A public repository's stat groups and their definitions at its current release."""
    return await stat_groups_of(
        session, repository_id, lambda: _not_found(repository_id), holder=False
    )


@router.get("/{repository_id}/dependencies")
async def list_public_repository_dependencies(
    repository_id: uuid.UUID, session: SessionDep, user: PublicReader
) -> list[PublicDependencyOut]:
    """The repositories a public repository is built on, dependencies first, as `copy-plan`
    orders them, and whether each is public. Copying the repository in one action needs every one
    of them to be (ADR 0287)."""
    steps = await dependencies_of(session, tenant_id=None, repository_id=repository_id)
    slugs = {
        id_: slug
        for id_, slug in await session.execute(
            select(Tenant.id, Tenant.slug).where(Tenant.id.in_([s.repository_id for s in steps]))
        )
    }
    return [
        PublicDependencyOut(
            id=step.repository_id,
            name=step.name,
            slug=slugs[step.repository_id],
            public=step.public,
        )
        for step in steps
        if step.repository_id in slugs
    ]
