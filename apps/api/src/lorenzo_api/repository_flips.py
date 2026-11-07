"""Flips between private, protected and public - ADR 0289, ADR 0433, RFC 0037 §6, RFC 0038 §7,
RFC 0051.

The rules that must hold when a repository's visibility changes, as functions of a session. The
routes that call them, the preview switch and the dialogs are RFC 0038's (D5) and RFC 0036's (T7);
`PATCH .../profile` still refuses a flip. No commit here: the caller commits, and a refusal anywhere
leaves nothing written, which is what makes the first release atomic with the visibility.

Three visibilities, six flips:

- private to public and private to protected make the first release with the flip, together or not
  at all (`make_public`, `make_protected`);
- protected to public makes a release too (`make_public`): a repository that is read through its
  release document is made public by the same steps, the summary and the terms line included;
- public to protected ends Discover and every visitor's read and turns the grants libraries gave
  themselves into `protected` ones, which read nothing alone (`make_protected`);
- public or protected to private revokes what libraries gave themselves, refused while a public or
  protected repository is built on it without including it (`make_private`).
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.exceptions import (
    BuiltOnNotPublicError,
    PublicCopiesWouldBeCutOffError,
    PublicRepositoriesBuiltOnItError,
    RepositoryAlreadyPrivateError,
    RepositoryAlreadyProtectedError,
    RepositoryAlreadyPublicError,
)
from lorenzo_api.models import RepositorySubscription, Tenant
from lorenzo_api.release_fanout import announce
from lorenzo_api.repository_built_on import built_on_not_public, public_dependents
from lorenzo_api.repository_delisting import refuse_if_delisted
from lorenzo_api.repository_deprecation import refuse_if_deprecated
from lorenzo_api.repository_profiles import profile_of
from lorenzo_api.repository_publishing import Published, publish_release
from lorenzo_api.repository_reach import revoke_protected_through, sync_reach
from lorenzo_api.repository_releases import lock_repository
from lorenzo_api.schemas.repositories import PublishRequest

__all__ = [
    "MadePrivate",
    "MadeProtected",
    "count_public_grants",
    "make_private",
    "make_protected",
    "make_public",
]


def _refuse_if_built_on_not_reached(not_reached: list[dict[str, Any]]) -> None:
    if not_reached:
        raise BuiltOnNotPublicError(
            detail="Every repository this one is built on has to be public or protected, or "
            "included in this one, so that a library can copy it in one action: "
            + ", ".join(str(r["name"]) for r in not_reached),
            repositories=not_reached,
        )


async def _turn_grants(
    session: AsyncSession, repository_id: uuid.UUID, *, source: str, to: str
) -> int:
    """The grants libraries gave themselves, `source` turned into `to` (a repository that is
    protected holds none as `public`, and one that is public none as `protected`): the one update
    the repository's side may make of a grant, which the policy allows for these two words only."""
    result = await session.execute(
        update(RepositorySubscription)
        .where(
            RepositorySubscription.repository_tenant_id == repository_id,
            RepositorySubscription.source == source,
        )
        .values(source=to)
    )
    return int(getattr(result, "rowcount", 0) or 0)


async def make_public(
    session: AsyncSession, *, repository: Tenant, user_id: uuid.UUID, body: PublishRequest
) -> Published:
    """Makes the repository public and makes its release, together or not at all: there is no
    public repository without a release, and the release is made as any publish makes one
    (`publish_release`, its document and its gates included). A protected repository is made
    public the same way, with a release of its own, and the grants its libraries wrote for
    themselves as `protected` become `public` ones. `409` if it already is public, and `409
    built-on-not-public` naming each repository it is built on that cannot be reached (with
    whether the caller owns it): a library copying it could not be granted a private one. `409
    repository-delisted` while the platform's operators have it off Discover. `409
    repository-deprecated` while its Owner has it retired. The libraries that already read it live
    keep their grants and links; their next update check reads the release, and the notice they
    get says so."""
    refuse_if_delisted(repository)
    refuse_if_deprecated(repository)
    await lock_repository(session, repository.id)
    profile = await profile_of(session, repository.id)
    if profile.visibility == "public":
        raise RepositoryAlreadyPublicError(detail=f"Repository {repository.id} is already public")
    _refuse_if_built_on_not_reached(await built_on_not_public(session, repository.id, user_id))
    was_protected = profile.visibility == "protected"
    profile.visibility = "public"
    profile.updated_by = user_id
    await session.flush()
    if was_protected:
        await _turn_grants(session, repository.id, source="protected", to="public")
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


@dataclass(frozen=True)
class MadeProtected:
    # The release made with the flip, for a repository that was private; none for a public one,
    # which has its releases already.
    published: Published | None
    # The grants libraries had given themselves while it was public, now `protected` ones.
    turned: int


async def make_protected(
    session: AsyncSession,
    *,
    repository: Tenant,
    user_id: uuid.UUID,
    body: PublishRequest,
    acknowledge_revokes: bool,
) -> MadeProtected:
    """Makes the repository protected (ADR 0433). A private one is made protected with its first
    release, together or not at all, as a public one is (`publish_release`): a library reads a
    protected repository through its release document. `409 built-on-not-public` naming each
    repository it is built on that cannot be reached (a protected repository's own sources follow
    the stack rule), `409 repository-delisted` and `409 repository-deprecated` as for a public one.

    A public one stays as it is, without a new release, and leaves Discover and every visitor's
    read. The libraries that copied it by themselves keep what they copied and keep a `protected`
    grant, which reads nothing alone: they read it again only through a public repository built on
    it that they hold, so the ones that held it for itself alone lose its updates. `409
    public-copies-would-be-cut-off` with the number until `acknowledge_revokes` says the Owner has
    been told, and those libraries are told once it is done. The libraries that hold a protected
    repository through this one, if it was public, lose that path (`revoke_protected_through`)."""
    refuse_if_delisted(repository)
    refuse_if_deprecated(repository)
    await lock_repository(session, repository.id)
    profile = await profile_of(session, repository.id)
    if profile.visibility == "protected":
        raise RepositoryAlreadyProtectedError(
            detail=f"Repository {repository.id} is already protected"
        )
    _refuse_if_built_on_not_reached(await built_on_not_public(session, repository.id, user_id))
    if profile.visibility == "private":
        profile.visibility = "protected"
        profile.updated_by = user_id
        await session.flush()
        published = await publish_release(
            session, repository=repository, user_id=user_id, body=body, flipped=True
        )
        await record_activity(
            session,
            tenant_id=repository.id,
            actor_id=user_id,
            action="repository.made_protected",
            target_type="tenant",
            target_id=repository.id,
            detail=f"release={published.release.number},label={published.release.label}",
        )
        return MadeProtected(published, 0)

    # Public to protected.
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
            "repository while it was public. They keep what they copied. From now on they get its "
            "updates only through a public repository built on it that they hold, and lose them "
            "if they hold none. Make it protected again, saying you acknowledge it.",
            libraries=len(libraries),
        )
    over = list(repository.released_over)
    turned = await _turn_grants(session, repository.id, source="public", to="protected")
    profile.visibility = "protected"
    # Not listed is a fact about a public repository only (the profile's check): the flip puts it
    # back, and a protected repository is on no listing whatever it says (ADR 0432, ADR 0433).
    profile.listed = True
    profile.updated_by = user_id
    await session.flush()
    # It no longer lets libraries read the protected repositories its release lists.
    await sync_reach(session, repository.id)
    await revoke_protected_through(session, repository.id, over)
    await record_activity(
        session,
        tenant_id=repository.id,
        actor_id=user_id,
        action="repository.made_protected",
        target_type="tenant",
        target_id=repository.id,
        detail=f"turned={turned}",
    )
    await announce(
        session,
        repository_id=repository.id,
        release_id=None,
        type="repository_revoked",
        title=f"{repository.name} is no longer public",
        body=(
            "It is protected now. What your library already copied from it stays yours. Its "
            "updates reach your library only through a public repository built on it that your "
            "library holds."
        ),
        created_by=user_id,
        recipients=libraries,
    )
    return MadeProtected(None, turned)


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
    naming the public or protected repositories built on it that do not include it (making it
    private would leave a stack no one can copy), and `409 public-copies-would-be-cut-off` with the
    number of libraries until `acknowledge_revokes` says the Owner has been told it. Then every
    grant a library gave itself by copying it is revoked, each library's Owners and Organizers are
    told as for any revoke, and the visibility changes. The copies stay, as after any revoke; the
    grants the Owner made by invitation stay and read it live again; its documents are kept under
    retention and nothing reads them while it is private.

    A protected repository is made private the same way, and the `protected` rows libraries wrote
    for it go with it (there is no public repository left that lists it, or it could not be made
    private). The libraries that held a protected repository through this one, if it was public,
    lose that path (`revoke_protected_through`, ADR 0433)."""
    await lock_repository(session, repository.id)
    profile = await profile_of(session, repository.id)
    if profile.visibility == "private":
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
    over = list(repository.released_over) if repository.released_public else []
    await session.execute(
        delete(RepositorySubscription).where(
            RepositorySubscription.repository_tenant_id == repository.id,
            RepositorySubscription.source.in_(("public", "protected")),
        )
    )
    profile.visibility = "private"
    # Not listed is a fact about a public repository only (the profile's check): it starts listed
    # again if it is made public again (ADR 0432).
    profile.listed = True
    profile.updated_by = user_id
    await session.flush()
    # It no longer lets libraries read the protected repositories its release lists (ADR 0433).
    await sync_reach(session, repository.id)
    await revoke_protected_through(session, repository.id, over)
    await record_activity(
        session,
        tenant_id=repository.id,
        actor_id=user_id,
        action="repository.made_private",
        target_type="tenant",
        target_id=repository.id,
        detail=f"revoked={len(libraries)}",
    )
    # The libraries whose grants were just deleted, as read above: the snapshot of the
    # announcement is what tells them, since the grants are no longer there to be read (ADR 0301).
    await announce(
        session,
        repository_id=repository.id,
        release_id=None,
        type="repository_revoked",
        title=f"{repository.name} is no longer shared with your library",
        body=(
            "It is no longer public. What your library already copied from it stays yours. It "
            "will not get updates from it unless it is invited again."
        ),
        created_by=user_id,
        recipients=libraries,
    )
    return MadePrivate(len(libraries))
