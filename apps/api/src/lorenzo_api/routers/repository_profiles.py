"""A repository's profile and cover - ADR 0213, RFC 0038 §2.

Two sides under /tenants/{tenant_id}, as in routers/repositories.py: the repository's own
(`/profile`, which any member reads and an Owner edits) and a granted library's
(`/repositories/{repository_id}/profile`, through the gated read, ADR 0118).
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import Response

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_context,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    ProfilePictureNotFoundError,
    PublicRepositoriesNotAvailableError,
    RepositoryNotFoundError,
)
from lorenzo_api.models import ProfilePicture, RepositoryProfile, Tenant
from lorenzo_api.profile_pictures import read_and_validate_upload
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_profiles import (
    delete_repository_cover,
    profile_of,
    profile_out,
    set_repository_cover,
)
from lorenzo_api.routers.repositories import _require_owner, _require_repository
from lorenzo_api.schemas.repository_profiles import RepositoryProfileOut, RepositoryProfileUpdate

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["repositories"])

# What a PATCH may change, in the order the activity log names it.
_FIELDS = ("visibility", "preview", "summary", "licence", "credits", "tags", "system", "languages")


def _not_found(tenant_id: uuid.UUID, repository_id: uuid.UUID) -> RepositoryNotFoundError:
    return RepositoryNotFoundError(
        detail=f"No published repository {repository_id} is granted to tenant {tenant_id}"
    )


def _cover_response(picture: ProfilePicture) -> Response:
    return Response(content=picture.data, media_type=picture.file_type)


# --- The repository's own side -----------------------------------------------------------


@router.get("/profile")
async def get_profile(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)], session: SessionDep
) -> RepositoryProfileOut:
    """What the repository says about itself, for any of its members: private, with the preview at
    `showcase` and nothing else said, until its Owner says more."""
    await _require_repository(session, tenant_id)
    return profile_out(await profile_of(session, tenant_id))


@router.patch("/profile")
async def update_profile(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    body: RepositoryProfileUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> RepositoryProfileOut:
    """An Owner changes what the profile says; only the fields named are touched. `visibility:
    "public"` is refused, in the same request as everything else in it (so nothing is kept),
    until the gates that come before a public repository are built (RFC 0038 §1)."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    await _require_repository(session, tenant_id)
    if body.visibility == "public":
        raise PublicRepositoriesNotAvailableError(
            detail="Public repositories are not available yet. This repository stays private."
        )
    profile = await profile_of(session, tenant_id)
    changed = [name for name in _FIELDS if name in body.model_fields_set]
    for name in changed:
        value = getattr(body, name)
        if name == "licence":
            profile.licence_label = value.label if value else None
            profile.licence_url = value.url if value else None
        elif name == "credits":
            profile.credits = [credit.model_dump() for credit in value]
        else:
            setattr(profile, name, value)
    if changed:
        profile.updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="repository.profile_updated",
            target_type="tenant",
            target_id=tenant_id,
            detail=f"fields={','.join(changed)}",
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    await session.refresh(profile)
    return profile_out(profile)


@router.get("/profile/cover")
async def get_cover(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)], session: SessionDep
) -> Response:
    """The cover picture, for any member. `404` if there is none."""
    await _require_repository(session, tenant_id)
    profile = await profile_of(session, tenant_id)
    if profile.cover_picture_id is None:
        raise ProfilePictureNotFoundError(detail=f"No cover picture for repository {tenant_id}")
    return _cover_response(await session.get_one(ProfilePicture, profile.cover_picture_id))


@router.put("/profile/cover", status_code=204)
async def set_cover(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
    file: UploadFile,
) -> None:
    """An Owner sets or replaces the cover: the types and the size cap of every profile picture
    (ADR 0056), and one picture is kept for each repository."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    await _require_repository(session, tenant_id)
    data, file_type = await read_and_validate_upload(file)
    await set_repository_cover(session, tenant_id=tenant_id, data=data, file_type=file_type)
    (await profile_of(session, tenant_id)).updated_by = user.id
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="repository.profile_cover_set",
        target_type="tenant",
        target_id=tenant_id,
    )
    await session.commit()


@router.delete("/profile/cover", status_code=204)
async def remove_cover(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """An Owner removes the cover. Removing what is not there is not an error."""
    await _require_owner(session, tenant_id=tenant_id, user=user)
    await _require_repository(session, tenant_id)
    if await delete_repository_cover(session, tenant_id=tenant_id):
        (await profile_of(session, tenant_id)).updated_by = user.id
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="repository.profile_cover_removed",
            target_type="tenant",
            target_id=tenant_id,
        )
    await session.commit()


# --- A granted library's side ---------------------------------------------------------------


@router.get("/repositories/{repository_id}/profile")
async def get_repository_profile(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
) -> RepositoryProfileOut:
    """The profile of a repository granted to this library and published, through the gated read
    (ADR 0118): what its Owner says of it, so the library can tell what it holds. `404` for any
    other."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise _not_found(tenant_id, repository_id)
        profile = await session.get(RepositoryProfile, repository_id)
        repository = await session.get_one(Tenant, repository_id)
        return profile_out(profile, stamp=repository.updated_at)


@router.get("/repositories/{repository_id}/profile/cover")
async def get_repository_cover(
    tenant_id: Annotated[uuid.UUID, Depends(get_tenant_context)],
    repository_id: uuid.UUID,
    session: SessionDep,
) -> Response:
    """The cover of a repository granted to this library and published, as above."""
    async with reading_repository(session, repository_id) as allowed:
        if not allowed:
            raise _not_found(tenant_id, repository_id)
        profile = await session.get(RepositoryProfile, repository_id)
        if profile is None or profile.cover_picture_id is None:
            raise ProfilePictureNotFoundError(
                detail=f"No cover picture for repository {repository_id}"
            )
        return _cover_response(await session.get_one(ProfilePicture, profile.cover_picture_id))
