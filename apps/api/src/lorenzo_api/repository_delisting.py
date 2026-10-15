"""Delisting a repository - ADR 0297, RFC 0038 section 6.

The platform's operators take a repository off Discover: it closes to new copies and to every
library and visitor reading it from outside (it reads as unpublished, `tenant.delisted_at` beside
`published_at` is what the gate and the listing look at), and its own members read and edit it as
ever and are told. Libraries that copied it keep their copies. The same call relists it, and
suspending an account delists every repository its holder is an Owner of.

Core mechanics only, like `repository_grants.py`: no authorisation (the `/admin` router has it),
no commit. A repository's log and its Owners' notifications are written in the repository's own
RLS context, which each function here sets and takes away again.
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import NO_TENANT, set_tenant_rls_context
from lorenzo_api.exceptions import RepositoryDelistedError
from lorenzo_api.models import Membership, MembershipRole, Tenant, TenantKind
from lorenzo_api.notifications import create_tenant_owners_notification
from lorenzo_api.schemas.repository_profiles import DelistedOut

__all__ = [
    "SUSPENSION_REASON",
    "delist_owned_by",
    "delist_repository",
    "delisted_out",
    "is_delisted",
    "refuse_if_delisted",
    "relist_repository",
]

# What a repository says when it was delisted because its Owner was suspended.
SUSPENSION_REASON = "Its Owner's account was suspended"


def is_delisted(repository: Tenant) -> bool:
    return repository.delisted_at is not None


def refuse_if_delisted(repository: Tenant) -> None:
    """`409 repository-delisted` while the platform's operators have the repository off Discover:
    what would make it public, which would list it nowhere and open it to nobody."""
    if repository.delisted_at is not None:
        raise RepositoryDelistedError(
            detail="The platform's operators took this repository off Discover, so it cannot be "
            f"made public until they list it again. Reason: {repository.delist_reason}"
        )


def delisted_out(repository: Tenant) -> DelistedOut | None:
    """What a member of the repository reads of it being delisted, and nobody else: the reason and
    when. Never who: the operators are the platform's, not a person."""
    if repository.delisted_at is None or repository.delist_reason is None:
        return None
    return DelistedOut(reason=repository.delist_reason, at=repository.delisted_at)


@asynccontextmanager
async def _in_repository(session: AsyncSession, repository_id: uuid.UUID) -> AsyncIterator[None]:
    """The repository's own RLS context, for its log and its Owners' notifications. What is
    pending belongs to the context it was added under, so it is written before each change."""
    await session.flush()
    await set_tenant_rls_context(session, repository_id)
    try:
        yield
        await session.flush()
    finally:
        await set_tenant_rls_context(session, NO_TENANT)


async def delist_repository(
    session: AsyncSession,
    *,
    repository: Tenant,
    operator_id: uuid.UUID,
    reason: str,
    keep_reason: bool = False,
) -> bool:
    """Takes the repository off Discover. Idempotent: delisting a delisted repository updates the
    reason and the operator (unless `keep_reason`, which a suspension asks, so that it never
    overwrites the words of an operator) and writes the log again; its Owners are told when it
    was listed before, once. Returns whether it was listed before. The caller commits."""
    newly = repository.delisted_at is None
    if not newly and keep_reason:
        return False
    if newly:
        repository.delisted_at = datetime.now(UTC)
    repository.delisted_by = operator_id
    repository.delist_reason = reason
    async with _in_repository(session, repository.id):
        await record_activity(
            session,
            tenant_id=repository.id,
            actor_id=operator_id,
            action="repository.delisted",
            target_type="tenant",
            target_id=repository.id,
        )
        if newly:
            await create_tenant_owners_notification(
                session,
                tenant_id=repository.id,
                type="repository_delisted",
                title=f"{repository.name} was taken off Discover and closed to new copies",
                body=(
                    f"Reason: {reason}\n"
                    "Libraries that copied it keep their copies, and cannot update from it "
                    "until it is listed again."
                ),
                created_by=None,
            )
    return newly


async def relist_repository(
    session: AsyncSession, *, repository: Tenant, operator_id: uuid.UUID
) -> bool:
    """Lists the repository again: a no-op, answering `False`, where it is not delisted. Logged,
    and its Owners are told. The caller commits."""
    if repository.delisted_at is None:
        return False
    repository.delisted_at = None
    repository.delisted_by = None
    repository.delist_reason = None
    async with _in_repository(session, repository.id):
        await record_activity(
            session,
            tenant_id=repository.id,
            actor_id=operator_id,
            action="repository.relisted",
            target_type="tenant",
            target_id=repository.id,
        )
        await create_tenant_owners_notification(
            session,
            tenant_id=repository.id,
            type="repository_relisted",
            title=f"{repository.name} is listed again",
            body="It is open to new copies again, and libraries that copied it can update from it.",
            created_by=None,
        )
    return True


async def owned_repositories(session: AsyncSession, user_id: uuid.UUID) -> list[Tenant]:
    """The repositories `user_id` is an Owner of. A membership is read under RLS for the tenant it
    is in or for the user it is of (ADR 0022), and the operator is neither: the read is made as
    the user it is about, for this one query, and the operator's own id is put back."""
    await session.flush()
    operator = await session.scalar(text("SELECT current_setting('app.user_id', true)"))
    await session.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})
    await set_tenant_rls_context(session, NO_TENANT)
    try:
        return list(
            await session.scalars(
                select(Tenant)
                .join(Membership, Membership.tenant_id == Tenant.id)
                .where(
                    Membership.user_id == user_id,
                    Membership.role == MembershipRole.OWNER,
                    Tenant.kind == TenantKind.REPOSITORY,
                )
                .order_by(Tenant.name, Tenant.id)
            )
        )
    finally:
        await session.execute(
            text("SELECT set_config('app.user_id', :u, true)"), {"u": operator or ""}
        )


async def delist_owned_by(
    session: AsyncSession, *, user_id: uuid.UUID, operator_id: uuid.UUID
) -> list[uuid.UUID]:
    """Delists every repository `user_id` is an Owner of, as a suspension does (RFC 0038 section
    6): one an operator has delisted already keeps their words. Returns the ids delisted now. A
    repository they only author or organise is not theirs and is left as it is. The caller
    commits."""
    delisted: list[uuid.UUID] = []
    for repository in await owned_repositories(session, user_id):
        if await delist_repository(
            session,
            repository=repository,
            operator_id=operator_id,
            reason=SUSPENSION_REASON,
            keep_reason=True,
        ):
            delisted.append(repository.id)
    return delisted
