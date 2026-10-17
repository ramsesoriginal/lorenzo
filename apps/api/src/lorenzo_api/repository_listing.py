"""The facts a listing shows of a repository's current release - ADR 0292.

Written to the repository's profile when a release is published and when an earlier one is made
current, from the `Content` that was loaded or read for it, so that Discover is one query over the
profiles and never opens a document. No commit here.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import RepositoryRelease
from lorenzo_api.repository_content import Content
from lorenzo_api.repository_profiles import profile_of

__all__ = ["set_listing_facts"]


async def set_listing_facts(
    session: AsyncSession,
    repository_id: uuid.UUID,
    *,
    release: RepositoryRelease,
    content: Content,
) -> None:
    """The release's label and date, and the size of its content: entries and stat definitions."""
    profile = await profile_of(session, repository_id)
    profile.release_label = release.label
    profile.released_at = release.created_at
    profile.entry_count = sum(content.entry_audiences.get(e, True) for e in content.entities)
    profile.stat_definition_count = len(content.definitions)
    await session.flush()
