"""A repository's profile and its cover - ADR 0213, RFC 0038 §2. Core mechanics only, like
profile_pictures.py: no authorisation, no commit; the routes in
routers/repository_profiles.py do both."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import ProfilePicture, RepositoryProfile
from lorenzo_api.schemas.repository_profiles import CreditOut, LicenceOut, RepositoryProfileOut

__all__ = [
    "delete_repository_cover",
    "profile_out",
    "profile_of",
    "set_repository_cover",
]


async def profile_of(session: AsyncSession, tenant_id: uuid.UUID) -> RepositoryProfile:
    """The repository's own profile. It is made with the repository and by the migration for
    the ones that existed; a repository that has none for any other reason gets its private,
    default one here, the first time it is asked for."""
    profile = await session.get(RepositoryProfile, tenant_id)
    if profile is None:
        profile = RepositoryProfile(tenant_id=tenant_id)
        session.add(profile)
        await session.flush()
        await session.refresh(profile)
    return profile


def profile_out(
    profile: RepositoryProfile | None, *, stamp: datetime | None = None
) -> RepositoryProfileOut:
    """What a client reads. `None` is a repository with no row yet, read through the gated read,
    which cannot make one: it reads as the defaults, stamped as `stamp`."""
    profile = profile or RepositoryProfile(
        visibility="private",
        preview="showcase",
        summary="",
        credits=[],
        tags=[],
        languages=[],
        updated_at=stamp or datetime.now(UTC),
    )
    return RepositoryProfileOut(
        visibility=profile.visibility,
        preview=profile.preview,
        summary=profile.summary,
        licence=(
            LicenceOut(label=profile.licence_label, url=profile.licence_url)
            if profile.licence_label is not None
            else None
        ),
        credits=[
            CreditOut(name=c["name"], role=c.get("role"), url=c.get("url")) for c in profile.credits
        ],
        tags=list(profile.tags),
        system=profile.system,
        languages=list(profile.languages),
        has_cover=profile.cover_picture_id is not None,
        updated_at=profile.updated_at,
    )


async def set_repository_cover(
    session: AsyncSession, *, tenant_id: uuid.UUID, data: bytes, file_type: str
) -> None:
    """Sets or replaces the cover: one picture row for each repository, kept in the same table
    as the other profile pictures (ADR 0056)."""
    profile = await profile_of(session, tenant_id)
    if profile.cover_picture_id is not None:
        picture = await session.get_one(ProfilePicture, profile.cover_picture_id)
        picture.data, picture.file_type = data, file_type
        return
    picture = ProfilePicture(data=data, file_type=file_type)
    session.add(picture)
    await session.flush()
    profile.cover_picture_id = picture.id


async def delete_repository_cover(session: AsyncSession, *, tenant_id: uuid.UUID) -> bool:
    """Removes the cover and its picture. A no-op, answering `False`, where there is none (a play
    tenant has no profile): callers need not check first."""
    profile = await session.get(RepositoryProfile, tenant_id)
    if profile is None or profile.cover_picture_id is None:
        return False
    picture = await session.get_one(ProfilePicture, profile.cover_picture_id)
    profile.cover_picture_id = None
    await session.flush()
    await session.delete(picture)
    return True
