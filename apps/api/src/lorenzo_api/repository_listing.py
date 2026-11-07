"""The facts a listing shows of a repository's current release - ADR 0292.

Written to the repository's profile when a release is published and when an earlier one is made
current, from the `Content` that was loaded or read for it, so that Discover is one query over the
profiles and never opens a document. No commit here.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.models import RepositoryRelease
from lorenzo_api.repository_content import Content, public_entry
from lorenzo_api.repository_inclusion import release_sources_of
from lorenzo_api.repository_profiles import profile_of

__all__ = ["set_listing_facts"]


async def set_listing_facts(
    session: AsyncSession,
    repository_id: uuid.UUID,
    *,
    release: RepositoryRelease,
    content: Content,
    public: bool,
) -> None:
    """The release's label and date, and the size of its content: entries and stat definitions.
    For the release of a public repository, which is the one a library reads, also how it carries
    each repository it is built on (ADR 0431): the storefront names what it includes from that, and
    a later release compares its choices with it."""
    profile = await profile_of(session, repository_id)
    profile.release_label = release.label
    profile.released_at = release.created_at
    profile.entry_count = sum(public_entry(content, e) for e in content.entities)
    profile.stat_definition_count = len(content.definitions)
    if public:
        profile.release_sources = release_sources_of(content)
    await session.flush()
