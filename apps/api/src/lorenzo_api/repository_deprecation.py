"""Deprecating a repository - ADR 0383, RFC 0038 section 7.

An Owner retires a repository without cutting off the libraries that use it: `tenant.deprecated_at`
(beside `published_at` and `delisted_at`, which the gate and the listing look at) says so, with an
optional message. A deprecated repository leaves Discover, is closed to anyone who holds no grant
to it and refuses new copies; a library that holds it (a grant, which a copy of a public
repository always writes) keeps reading it and keeps its updates. The same state is undone by
`undeprecate_repository`, and the libraries are told both ways through the release fan-out
(ADR 0301).

Core mechanics only, like `repository_delisting.py`: no authorisation (the router has it), no
commit. The caller is in the repository's own RLS context, which is where its log, its fan-out row
and its copies are read.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.exceptions import RepositoryDeprecatedError
from lorenzo_api.models import RepositoryCopy, RepositorySubscription, Tenant
from lorenzo_api.release_fanout import announce
from lorenzo_api.schemas.repository_profiles import DeprecatedNoticeOut, DeprecatedOut

__all__ = [
    "copy_refusal",
    "deprecate_repository",
    "deprecated_notice",
    "deprecated_out",
    "holders_of",
    "is_deprecated",
    "refuse_if_deprecated",
    "undeprecate_repository",
]


def is_deprecated(repository: Tenant) -> bool:
    return repository.deprecated_at is not None


def refuse_if_deprecated(repository: Tenant) -> None:
    """`409 repository-deprecated` while the Owner has the repository retired: what would make it
    public, which would list it nowhere and open it to nobody."""
    if repository.deprecated_at is not None:
        raise RepositoryDeprecatedError(
            detail="This repository is retired, so it cannot be made public. Bring it back first."
        )


def copy_refusal(name: str, message: str | None) -> RepositoryDeprecatedError:
    """The refusal of a new copy of a retired repository, naming the Owner's message when there is
    one. Raised only for a library that can read the repository (a holder): the gate makes it
    `404` for everyone else, so the message reaches nobody who may not read it."""
    detail = (
        f"{name} was retired by its Owner and can no longer be copied. "
        "Libraries that already copied it keep their copy and its updates."
    )
    if message:
        detail += f" Message: {message}"
    return RepositoryDeprecatedError(detail=detail)


def deprecated_out(repository: Tenant) -> DeprecatedOut | None:
    """What a member of the repository reads of it being retired, and nobody else: the message
    and when. Never who."""
    if repository.deprecated_at is None:
        return None
    return DeprecatedOut(message=repository.deprecated_message, at=repository.deprecated_at)


def deprecated_notice(repository: Tenant | None) -> DeprecatedNoticeOut | None:
    """What a library that holds the repository reads of it being retired: the message."""
    if repository is None or repository.deprecated_at is None:
        return None
    return DeprecatedNoticeOut(message=repository.deprecated_message)


async def holders_of(
    session: AsyncSession, repository_id: uuid.UUID
) -> tuple[list[uuid.UUID], list[uuid.UUID]]:
    """The libraries that hold the repository now, as the notice of a change of state is sent to
    them: those that keep their copy and its updates (a copy and a grant), and the rest (an
    invitation not yet used, or a copy whose grant is gone). In the repository's own context,
    where it reads both its grants and the copies made of it."""
    granted = set(
        await session.scalars(
            select(RepositorySubscription.subscriber_tenant_id).where(
                RepositorySubscription.repository_tenant_id == repository_id
            )
        )
    )
    copied = set(
        await session.scalars(
            select(RepositoryCopy.tenant_id).where(
                RepositoryCopy.repository_tenant_id == repository_id
            )
        )
    )
    updating = sorted(granted & copied, key=str)
    others = sorted((granted | copied) - set(updating), key=str)
    return updating, others


async def deprecate_repository(
    session: AsyncSession,
    *,
    repository: Tenant,
    user_id: uuid.UUID,
    message: str | None,
) -> bool:
    """Retires the repository. Idempotent: retiring a retired one replaces the message and keeps
    the time it was first retired; the libraries are told once, the first time (a later message
    is on the page and in the notice they can read, not another notice). Returns whether it was
    not retired before. The caller commits and then drains the fan-out."""
    newly = repository.deprecated_at is None
    changed = newly or repository.deprecated_message != message
    if newly:
        repository.deprecated_at = datetime.now(UTC)
    repository.deprecated_message = message
    if not changed:
        return False
    # The log holds ids and field names only (ADR 0063): the message is not in it.
    await record_activity(
        session,
        tenant_id=repository.id,
        actor_id=user_id,
        action="repository.deprecated",
        target_type="tenant",
        target_id=repository.id,
    )
    if newly:
        updating, others = await holders_of(session, repository.id)
        suffix = f"\nMessage: {message}" if message else ""
        # A delisted repository reads as unpublished to every library (ADR 0303): nothing they
        # could read, so nothing to tell them.
        if repository.delisted_at is None:
            await announce(
                session,
                repository_id=repository.id,
                release_id=None,
                type="repository_deprecated",
                title=f"{repository.name} was retired by its Owner",
                body=("You keep your copy and its updates; it can no longer be copied." + suffix),
                created_by=user_id,
                recipients=updating,
            )
            await announce(
                session,
                repository_id=repository.id,
                release_id=None,
                type="repository_deprecated",
                title=f"{repository.name} was retired by its Owner",
                body="It can no longer be copied." + suffix,
                created_by=user_id,
                recipients=others,
            )
    return newly


async def undeprecate_repository(
    session: AsyncSession, *, repository: Tenant, user_id: uuid.UUID
) -> bool:
    """Brings the repository back: a no-op, answering `False`, where it is not retired. Logged,
    and the libraries that hold it are told. The caller commits and then drains the fan-out."""
    if repository.deprecated_at is None:
        return False
    repository.deprecated_at = None
    repository.deprecated_message = None
    await record_activity(
        session,
        tenant_id=repository.id,
        actor_id=user_id,
        action="repository.undeprecated",
        target_type="tenant",
        target_id=repository.id,
    )
    if repository.delisted_at is None:
        updating, others = await holders_of(session, repository.id)
        await announce(
            session,
            repository_id=repository.id,
            release_id=None,
            type="repository_undeprecated",
            title=f"{repository.name} is available again",
            body="It can be copied again.",
            created_by=user_id,
            recipients=[*updating, *others],
        )
    return True
