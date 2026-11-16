"""The one-time Gravatar copy (ADR 0439).

When an account's verified email is first cached (ADR 0075) and the account has no picture, the
API asks Gravatar once for the picture of a SHA-256 of the email, and keeps what it gets as the
account's own profile picture (ADR 0056). `gravatar_checked_at` records that the question was
asked, so it is never asked again; deleting the picture does not bring it back, and no browser
ever talks to Gravatar. Nothing here may fail a login.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.config import get_settings
from lorenzo_api.models.user import User
from lorenzo_api.models.user_profile_picture import UserProfilePicture
from lorenzo_api.profile_pictures import ALLOWED_IMAGE_CONTENT_TYPES, upsert_user_profile_picture

logger = structlog.get_logger()

# Short: this runs inside the first request of a new account, and a slow Gravatar must not make
# that request slow.
_TIMEOUT_SECONDS = 3.0
_SIZE = 200


@dataclass(frozen=True)
class Found:
    data: bytes
    content_type: str


Outcome = Found | Literal["none", "failed"]
"""`none`: Gravatar has no picture for it (a definite answer). `failed`: no definite answer."""


def avatar_url(base_url: str, email: str) -> str:
    """`d=404` makes Gravatar answer 404 for an email with no picture, instead of a default image
    that would be copied as if it were the person's."""
    digest = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    return f"{base_url.rstrip('/')}/avatar/{digest}?d=404&s={_SIZE}"


async def fetch(base_url: str, email: str) -> Outcome:
    """One request, no redirects, an image type and size as allowed for an upload."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS, follow_redirects=False) as http:
            response = await http.get(avatar_url(base_url, email))
    except httpx.HTTPError as exc:
        logger.info("gravatar_fetch_failed", error=type(exc).__name__)
        return "failed"
    if response.status_code == 404:
        return "none"
    if response.status_code != 200:
        logger.info("gravatar_fetch_failed", status=response.status_code)
        return "failed"
    content_type = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if (
        content_type not in ALLOWED_IMAGE_CONTENT_TYPES
        or len(response.content) > get_settings().profile_picture_max_bytes
        or not response.content
    ):
        logger.info("gravatar_fetch_unusable", content_type=content_type)
        return "failed"
    return Found(response.content, content_type)


async def copy_once(session: AsyncSession, user: User, *, base_url: str | None = None) -> None:
    """Asks once for the account's Gravatar and keeps it, if the account has none of its own.

    Does nothing when it was asked before, when the account has no email, or when the deployment
    has turned the lookup off. The marker is set on a definite answer only, so a Gravatar outage
    is asked again at the next first-cache attempt. Never raises.
    """
    settings = get_settings()
    if (
        not settings.gravatar_lookup_enabled
        or user.email is None
        or user.gravatar_checked_at is not None
    ):
        return
    try:
        if await session.get(UserProfilePicture, user.id) is None:
            outcome = await fetch(base_url or settings.gravatar_base_url, user.email)
            if outcome == "failed":
                return
            if isinstance(outcome, Found):
                await upsert_user_profile_picture(
                    session,
                    user_id=user.id,
                    data=outcome.data,
                    file_type=outcome.content_type,
                )
        user.gravatar_checked_at = datetime.now(UTC)
        await session.commit()
    except Exception:  # noqa: BLE001 - nothing here may fail a login
        logger.warning("gravatar_copy_failed", user_id=str(user.id), exc_info=True)
        await session.rollback()
