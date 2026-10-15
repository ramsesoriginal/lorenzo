"""Flips between private and public - ADR 0289, RFC 0037 §6, RFC 0038 §7.

The rules that must hold when a repository's visibility changes, as functions of a session. The
routes that call them, the preview switch and the dialogs are RFC 0038's (D5) and RFC 0036's (T7);
`PATCH .../profile` still refuses `public` until they are built. No commit here: the caller
commits, and a refusal anywhere leaves nothing written, which is what makes the first release
atomic with the visibility.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.exceptions import (
    BuiltOnNotPublicError,
    PublicCopiesWouldBeCutOffError,
    PublicRepositoriesBuiltOnItError,
    RepositoryAlreadyPrivateError,
    RepositoryAlreadyPublicError,
)
from lorenzo_api.models import RepositorySubscription, Tenant
from lorenzo_api.repository_built_on import built_on_not_public, public_dependents
from lorenzo_api.repository_delisting import refuse_if_delisted
from lorenzo_api.repository_grants import notify_tenant_admins
from lorenzo_api.repository_profiles import profile_of
from lorenzo_api.repository_publishing import Published, publish_release
from lorenzo_api.repository_releases import lock_repository
from lorenzo_api.schemas.repositories import PublishRequest

__all__ = ["MadePrivate", "count_public_grants", "make_private", "make_public"]


async def make_public(
    session: AsyncSession, *, repository: Tenant, user_id: uuid.UUID, body: PublishRequest
) -> Published:
    """Makes the repository public and makes its release, together or not at all: there is no
    public repository without a release, and the release is made as any publish makes one
    (`publish_release`, its document and its gates included). `409` if it already is public, and
    `409 built-on-not-public` naming each repository it is built on that is not (with whether the
    caller owns it): a library copying it could not be granted a private one. `409
    repository-delisted` while the platform's operators have it off Discover. The libraries that
    already read it live keep their grants and links; their next update check reads the release,
    and the notice they get says so."""
    refuse_if_delisted(repository)
    await lock_repository(session, repository.id)
    profile = await profile_of(session, repository.id)
    if profile.visibility == "public":
        raise RepositoryAlreadyPublicError(detail=f"Repository {repository.id} is already public")
    not_public = await built_on_not_public(session, repository.id, user_id)
    if not_public:
        raise BuiltOnNotPublicError(
            detail="Every repository this one is built on has to be public first, so that a "
            "library can copy it in one action: " + ", ".join(r["name"] for r in not_public),
            repositories=not_public,
        )
    profile.visibility = "public"
    profile.updated_by = user_id
    await session.flush()
    published = await publish_release(
        session, repository=repository, user_id=user_id, body=body, flipped=True
    )
    await record_activity(
        session,
        tenant_id=repository.id,
        actor_id=user_id,
        action="repository.made_public",
        target_type="tenant",
        target_id=repository.id,
        detail=f"release={published.release.number},label={published.release.label}",
    )
    return published


async def count_public_grants(session: AsyncSession, repository_id: uuid.UUID) -> int:
    """How many libraries hold a grant they gave themselves by copying the repository."""
    return int(
        await session.scalar(
            select(func.count())
            .select_from(RepositorySubscription)
            .where(
                RepositorySubscription.repository_tenant_id == repository_id,
                RepositorySubscription.source == "public",
            )
        )
        or 0
    )


@dataclass(frozen=True)
class MadePrivate:
    # The grants that were revoked: those a library gave itself by copying the repository.
    revoked: int


async def make_private(
    session: AsyncSession,
    *,
    repository: Tenant,
    user_id: uuid.UUID,
    acknowledge_revokes: bool,
) -> MadePrivate:
    """Makes the repository private. `409` if it already is, `409 public-repositories-built-on-it`
    naming the public repositories built on it (making it private would leave a public stack no
    one can copy), and `409 public-copies-would-be-cut-off` with the number of libraries until
    `acknowledge_revokes` says the Owner has been told it. Then every grant a library gave itself
    by copying it is revoked, each library's Owners and Organizers are told as for any revoke, and
    the visibility changes. The copies stay, as after any revoke; the grants the Owner made by
    invitation stay and read it live again; its documents are kept under retention and nothing
    reads them while it is private."""
    await lock_repository(session, repository.id)
    profile = await profile_of(session, repository.id)
    if profile.visibility != "public":
        raise RepositoryAlreadyPrivateError(detail=f"Repository {repository.id} is already private")
    dependents = await public_dependents(session, repository.id)
    if dependents:
        raise PublicRepositoriesBuiltOnItError(
            detail="Make these private first, or they could no longer be copied: "
            + ", ".join(d["name"] for d in dependents),
            repositories=dependents,
        )
    libraries = list(
        await session.scalars(
            select(RepositorySubscription.subscriber_tenant_id).where(
                RepositorySubscription.repository_tenant_id == repository.id,
                RepositorySubscription.source == "public",
            )
        )
    )
    if libraries and not acknowledge_revokes:
        raise PublicCopiesWouldBeCutOffError(
            detail=f"{len(libraries)} librar{'y' if len(libraries) == 1 else 'ies'} copied this "
            "repository while it was public. They keep what they copied and lose its updates. "
            "Make it private again, saying you acknowledge it.",
            libraries=len(libraries),
        )
    await session.execute(
        delete(RepositorySubscription).where(
            RepositorySubscription.repository_tenant_id == repository.id,
            RepositorySubscription.source == "public",
        )
    )
    profile.visibility = "private"
    profile.updated_by = user_id
    await session.flush()
    await record_activity(
        session,
        tenant_id=repository.id,
        actor_id=user_id,
        action="repository.made_private",
        target_type="tenant",
        target_id=repository.id,
        detail=f"revoked={len(libraries)}",
    )
    # One notice a library, here and now: past a few hundred libraries this is the asynchronous
    # fan-out of RFC 0038 section 6 (D6), which takes this loop over.
    await notify_tenant_admins(
        session,
        recipient_tenant_ids=libraries,
        current_tenant_id=repository.id,
        type="repository_revoked",
        title=f"{repository.name} is no longer shared with your library",
        body=(
            "It is no longer public. What your library already copied from it stays yours. It "
            "will not get updates from it unless it is invited again."
        ),
        created_by=user_id,
    )
    return MadePrivate(len(libraries))
