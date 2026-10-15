"""Publishing a repository: the release it makes and what comes with it - ADR 0207, 0208, 0286,
0288, 0289.

`publish_release` is what `PUT /tenants/{id}/published` does, as a function of a session, so
that making a repository public (`repository_flips.make_public`) makes its first release with
exactly the same steps, in the same transaction. No commit here: the caller commits, and a
refusal anywhere leaves nothing written.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.config import get_settings
from lorenzo_api.entity_kinds import unpublishable_sentence
from lorenzo_api.exceptions import (
    BuiltOnBehindError,
    ReleaseHasBreakingChangesError,
    RepositoryHasUnprovenKindsError,
)
from lorenzo_api.models import RepositoryRelease, RepositorySubscription, Tenant
from lorenzo_api.release_document_store import prune_release_documents, store_release_document
from lorenzo_api.repository_built_on import built_on_behind
from lorenzo_api.repository_digest import assess, replace_stored_rows
from lorenzo_api.repository_grants import notify_tenant_admins
from lorenzo_api.repository_listing import set_listing_facts
from lorenzo_api.repository_releases import (
    lock_repository,
    make_release,
    release_notice,
    set_current_release,
)
from lorenzo_api.repository_upstream import is_public
from lorenzo_api.schemas.repositories import PublishRequest

__all__ = ["Published", "publish_release"]


@dataclass(frozen=True)
class Published:
    release: RepositoryRelease
    # Whether a document was written for it: the repository is public.
    public: bool
    # Whether it had been published before.
    was_published: bool


async def publish_release(
    session: AsyncSession,
    *,
    repository: Tenant,
    user_id: uuid.UUID,
    body: PublishRequest,
    flipped: bool = False,
) -> Published:
    """Makes the repository's next release and everything it carries: `409` for an entry of a
    kind no round trip proves, for the label, for breaking changes not acknowledged, and, for a
    public repository, `409 built-on-behind` while a repository it is built on has a release it
    has not taken (ADR 0289). Then the released rows, the document and its files if the
    repository is public, the pointer to the release, retention, the log, and the notice to every
    library it is granted to. `flipped` says the repository was made public by this publish, which
    the notice says."""
    tenant_id = repository.id
    was_published = repository.published_at is not None
    await lock_repository(session, tenant_id)
    assessed = await assess(session, tenant_id)
    if assessed.unproven_kinds:
        raise RepositoryHasUnprovenKindsError(
            detail=unpublishable_sentence(assessed.unproven_kinds),
            entries=[
                {"id": str(e["id"]), "name": e["name"], "kinds": e["kinds"]}
                for e in assessed.unproven_kinds
            ],
        )
    public = await is_public(session, tenant_id)
    if public:
        behind = await built_on_behind(session, tenant_id)
        if behind:
            raise BuiltOnBehindError(
                detail="Update this repository to the current release of each repository it is "
                "built on first, so that a library copying it gets what it was made against: "
                + ", ".join(b.name for b in behind),
                repositories=[b.as_json() for b in behind],
            )
    if assessed.hits and not body.acknowledge_breaking:
        raise ReleaseHasBreakingChangesError(
            detail=f"{len(assessed.hits)} of the changes in this release break what libraries "
            "built on this repository hold. Look at them, then publish again, saying you "
            "acknowledge it.",
            breaking_rows=[b.as_json() for b in assessed.hits],
        )
    release = await make_release(
        session,
        repository=repository,
        user_id=user_id,
        label=body.label,
        notes=body.notes,
        breaking=body.breaking or bool(assessed.hits),
        digest=assessed.digest,
        counts=assessed.counts,
        breaking_rows=[b.as_json() for b in assessed.hits],
        warning_rows=[b.as_json() for b in assessed.warnings],
    )
    await replace_stored_rows(session, tenant_id, assessed.live.values())
    if public:
        # What a library reads of a public repository, written from the load the digest was
        # made from, so the two cannot disagree (ADR 0286).
        await store_release_document(
            session, tenant_id=tenant_id, release_id=release.id, content=assessed.content
        )
    await set_current_release(session, repository, release.id)
    await set_listing_facts(session, tenant_id, release=release, content=assessed.content)
    if public:
        await prune_release_documents(
            session,
            tenant_id=tenant_id,
            keep=get_settings().release_documents_retained,
            current_release_id=release.id,
        )
    repository.published_at = datetime.now(UTC)
    repository.updated_by = user_id
    # The label is in the log, which only the repository's own members read, as it is in
    # the list of releases the libraries read: words the author chose to publish.
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user_id,
        action="repository.published",
        target_type="tenant",
        target_id=tenant_id,
        detail=(
            f"release={release.number},breaking={str(release.breaking).lower()},"
            f"label={release.label}"
        ),
    )
    # A delisted repository reads as unpublished to the libraries, which are told nothing of a
    # release they cannot read (ADR 0303).
    subscribers = (
        []
        if repository.delisted_at is not None
        else (
            await session.scalars(
                select(RepositorySubscription.subscriber_tenant_id).where(
                    RepositorySubscription.repository_tenant_id == tenant_id
                )
            )
        ).all()
    )
    title, notice = release_notice(
        repository_name=repository.name,
        release=release,
        first=not was_published,
        flipped=flipped,
    )
    await notify_tenant_admins(
        session,
        recipient_tenant_ids=subscribers,
        current_tenant_id=tenant_id,
        type="repository_updated" if was_published else "repository_published",
        title=title,
        body=notice,
        created_by=user_id,
    )
    return Published(release, public, was_published)
