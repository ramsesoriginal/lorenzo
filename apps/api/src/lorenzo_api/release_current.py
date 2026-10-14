"""Making an earlier release current again - ADR 0288, RFC 0037 §5.

A public repository's libraries read its current release's document. A bad release is undone by
pointing the repository at one whose document is still kept: a rollback that writes no content
and loses none. The released rows are recomputed from that document with the same functions a
publish uses, so "Edited since" always compares the live content with the release that is
current, and the detector runs between the release that was current and the one chosen, as it
runs between the last release and a new one: what it finds is what a library built on the first
and updated to the second would lose, and is acknowledged the same way.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import (
    ReleaseHasBreakingChangesError,
    ReleaseNotFoundError,
    ReleaseNotRetainedError,
)
from lorenzo_api.models import RepositoryRelease, Tenant
from lorenzo_api.release_document import ReleaseDocumentCorruptError
from lorenzo_api.release_document_store import ReleaseDocumentNotFoundError, read_release_content
from lorenzo_api.repository_digest import (
    Breaking,
    compare,
    detect,
    digest_of,
    live_rows,
    replace_stored_rows,
    split,
    stored_rows,
)
from lorenzo_api.repository_listing import set_listing_facts
from lorenzo_api.repository_releases import current_release, lock_repository, set_current_release

__all__ = ["MadeCurrent", "make_release_current"]


@dataclass(frozen=True)
class MadeCurrent:
    release: RepositoryRelease
    # False when the release already was current and nothing was done.
    changed: bool
    previous_id: uuid.UUID | None
    breaking: list[Breaking]
    warnings: list[Breaking]


async def make_release_current(
    session: AsyncSession,
    *,
    repository: Tenant,
    release_id: uuid.UUID,
    acknowledge_breaking: bool,
) -> MadeCurrent:
    """Points `repository` at `release_id`. `404` for a release it did not make, `409
    release-not-retained` when its document is gone, `409 release-has-breaking-changes` when the
    move breaks what libraries on the current release hold and `acknowledge_breaking` is not
    said. Locks the repository's row first, so it is taken one after a publish. Flushes; the
    caller records it, tells the libraries and commits."""
    await lock_repository(session, repository.id)
    release = await session.scalar(
        select(RepositoryRelease).where(
            RepositoryRelease.tenant_id == repository.id, RepositoryRelease.id == release_id
        )
    )
    if release is None:
        raise ReleaseNotFoundError(detail=f"This repository has no release {release_id}")
    current = await current_release(session, repository.id)
    if current is not None and current.id == release.id:
        return MadeCurrent(release, False, current.id, [], [])

    try:
        content = await read_release_content(
            session, tenant_id=repository.id, release_id=release.id
        )
    except ReleaseDocumentNotFoundError:
        raise ReleaseNotRetainedError(
            detail=f"The content of release {release.label} is no longer kept, so it cannot be "
            "made current again"
        ) from None
    rows = live_rows(content)
    if release.digest is not None and digest_of(rows.values()) != release.digest:
        raise ReleaseDocumentCorruptError(
            f"the document of release {release.id} does not hash to the digest it was made with"
        )

    baseline = current is not None and current.digest is not None
    hits: list[Breaking] = []
    warnings: list[Breaking] = []
    if baseline:
        hits, warnings = split(detect(compare(await stored_rows(session, repository.id), rows)))
    if hits and not acknowledge_breaking:
        raise ReleaseHasBreakingChangesError(
            detail=f"{len(hits)} of the changes between release {current.label if current else ''} "
            f"and release {release.label} break what libraries built on the first hold. Look at "
            "them, then make it current again, saying you acknowledge it.",
            breaking_rows=[b.as_json() for b in hits],
        )

    await replace_stored_rows(session, repository.id, rows.values())
    await set_current_release(session, repository, release.id)
    await set_listing_facts(session, repository.id, release=release, content=content)
    return MadeCurrent(release, True, current.id if current else None, hits, warnings)
