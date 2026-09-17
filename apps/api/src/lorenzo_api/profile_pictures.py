"""Shared upload-validation, upsert/delete, and Gravatar-URL logic for
User/Tenant/Campaign profile pictures - see ADR 0056.

Every function here does core mechanics only - no auth, no response
shaping, no commit (matching routers/item_instances.py's own
`_perform_split`/`_perform_set_owner` precedent) - each PUT/DELETE route
calls one of these, then commits itself.
"""

import hashlib
import uuid

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.config import get_settings
from lorenzo_api.exceptions import InvalidProfilePictureError
from lorenzo_api.models import (
    CampaignProfilePicture,
    ProfilePicture,
    TenantProfilePicture,
    UserProfilePicture,
)

# Trusting the client-declared content_type, no deep image-content sniffing -
# the same level of trust payload_picture/payload_document's own file_type
# already gets (ADR 0017).
_ALLOWED_CONTENT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"})


async def read_and_validate_upload(file: UploadFile) -> tuple[bytes, str]:
    """Shared by every PUT .../picture route - content-type allow-list plus
    a size cap (`Settings.profile_picture_max_bytes`), both a 422
    `InvalidProfilePictureError`.
    """
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise InvalidProfilePictureError(
            detail=(
                f"Unsupported content type '{file.content_type}'; expected one of "
                f"{sorted(_ALLOWED_CONTENT_TYPES)}"
            )
        )
    data = await file.read()
    max_bytes = get_settings().profile_picture_max_bytes
    if len(data) > max_bytes:
        raise InvalidProfilePictureError(
            detail=f"Profile picture exceeds the {max_bytes}-byte limit"
        )
    return data, file.content_type


async def upsert_user_profile_picture(
    session: AsyncSession, *, user_id: uuid.UUID, data: bytes, file_type: str
) -> None:
    link = await session.get(UserProfilePicture, user_id)
    if link is not None:
        picture = await session.get_one(ProfilePicture, link.profile_picture_id)
        picture.data, picture.file_type = data, file_type
        return
    picture = ProfilePicture(data=data, file_type=file_type)
    session.add(picture)
    await session.flush()
    session.add(UserProfilePicture(user_id=user_id, profile_picture_id=picture.id))


async def delete_user_profile_picture(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    """No-op if there is no picture to delete - callers (DELETE /me/picture,
    and delete_me's own owner-deletion cleanup) don't need to check first.
    """
    link = await session.get(UserProfilePicture, user_id)
    if link is not None:
        await session.delete(await session.get_one(ProfilePicture, link.profile_picture_id))


async def upsert_tenant_profile_picture(
    session: AsyncSession, *, tenant_id: uuid.UUID, data: bytes, file_type: str
) -> None:
    link = await session.get(TenantProfilePicture, tenant_id)
    if link is not None:
        picture = await session.get_one(ProfilePicture, link.profile_picture_id)
        picture.data, picture.file_type = data, file_type
        return
    picture = ProfilePicture(data=data, file_type=file_type)
    session.add(picture)
    await session.flush()
    session.add(TenantProfilePicture(tenant_id=tenant_id, profile_picture_id=picture.id))


async def delete_tenant_profile_picture(session: AsyncSession, *, tenant_id: uuid.UUID) -> None:
    link = await session.get(TenantProfilePicture, tenant_id)
    if link is not None:
        await session.delete(await session.get_one(ProfilePicture, link.profile_picture_id))


async def upsert_campaign_profile_picture(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    campaign_id: uuid.UUID,
    data: bytes,
    file_type: str,
) -> None:
    link = await session.get(CampaignProfilePicture, campaign_id)
    if link is not None:
        picture = await session.get_one(ProfilePicture, link.profile_picture_id)
        picture.data, picture.file_type = data, file_type
        return
    picture = ProfilePicture(data=data, file_type=file_type)
    session.add(picture)
    await session.flush()
    session.add(
        CampaignProfilePicture(
            campaign_id=campaign_id, tenant_id=tenant_id, profile_picture_id=picture.id
        )
    )


async def delete_campaign_profile_picture(session: AsyncSession, *, campaign_id: uuid.UUID) -> None:
    """No-op if there is no picture - callers (DELETE .../picture, and
    delete_campaign's own owner-deletion cleanup) don't need to check first.
    """
    link = await session.get(CampaignProfilePicture, campaign_id)
    if link is not None:
        await session.delete(await session.get_one(ProfilePicture, link.profile_picture_id))


def gravatar_url(email: str, *, size: int = 200) -> str:
    """See ADR 0056. `d=mp` ("mystery person") means this always resolves
    to *something* even for an email that never registered with Gravatar -
    the only real fallback failure is a user with no email at all.
    """
    # Gravatar's lookup key, not a security use - their API accepts either
    # MD5 or SHA256 of the trimmed, lowercased email; SHA256 avoids relying
    # on a broken hash even for a non-cryptographic lookup.
    email_hash = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{email_hash}?d=mp&s={size}"
