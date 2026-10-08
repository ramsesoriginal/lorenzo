"""The release ledger - ADR 0207, RFC 0037 §1.

Publishing a repository makes a release: a number the server assigns, a label
the author chooses (the number, when they do not), notes, and the breaking
flag. These functions make one, say what a library is told about it, and find
the latest, which is what a copy records as the release it last took.

Everything here reads `repository_release` for one repository id, with an
explicit `tenant_id` filter (ADR 0002): as the repository's own member, or for
a library inside `reading_repository` (ADR 0118).
"""

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.exceptions import ReleaseLabelTakenError
from lorenzo_api.models import RepositoryRelease, Tenant

# What a notification carries of a release's notes: a line or two, never the essay.
NOTICE_NOTES_LENGTH = 280

BREAKING_LINE = "This release is marked breaking: it may change things your library already uses."
NOTHING_SAID = "Check its updates to see what changed."
FIRST_PUBLISH_BODY = "You can browse it and copy it into your tenant."


@dataclass(frozen=True)
class ReleaseRef:
    """A release as a copy and an update check name it."""

    id: uuid.UUID
    number: int
    label: str
    created_at: datetime


def _ref(release: RepositoryRelease) -> ReleaseRef:
    return ReleaseRef(release.id, release.number, release.label, release.created_at)


def cut(text: str, limit: int = NOTICE_NOTES_LENGTH) -> str:
    """`text` as it is when it fits, else cut between words, with an ellipsis, in no
    more than `limit` characters."""
    if len(text) <= limit:
        return text
    head = text[: limit - 1]
    # In the middle of a word: back to the word before.
    if not text[limit - 1].isspace() and len(head.split()) > 1:
        head = head.rsplit(None, 1)[0]
    return head.rstrip() + "…"


def release_notice(
    *, repository_name: str, release: RepositoryRelease, first: bool
) -> tuple[str, str]:
    """The title and body the libraries a repository is granted to are told when it
    publishes: the release's label in the title, its notes (cut) and a line when it
    is breaking in the body. The first publish keeps its own words, and adds the
    notes if there are any."""
    said = [cut(release.notes)] if release.notes else []
    if release.breaking:
        said.append(BREAKING_LINE)
    if first:
        return f"{repository_name} is published", "\n\n".join([FIRST_PUBLISH_BODY, *said])
    return (
        f"{repository_name} published release {release.label}",
        "\n\n".join(said) or NOTHING_SAID,
    )


async def _label_in_use(
    session: AsyncSession, repository_id: uuid.UUID, label: str, *, besides: uuid.UUID | None = None
) -> bool:
    stmt = select(RepositoryRelease.id).where(
        RepositoryRelease.tenant_id == repository_id,
        func.lower(RepositoryRelease.label) == func.lower(literal(label)),
    )
    if besides is not None:
        stmt = stmt.where(RepositoryRelease.id != besides)
    return (await session.scalar(stmt.limit(1))) is not None


def _taken(label: str) -> ReleaseLabelTakenError:
    return ReleaseLabelTakenError(
        detail=f"A release of this repository is already called “{label}”, whatever its case. "
        "Give this one another label."
    )


async def make_release(
    session: AsyncSession,
    *,
    repository: Tenant,
    user_id: uuid.UUID,
    label: str | None,
    notes: str | None,
    breaking: bool,
) -> RepositoryRelease:
    """The repository's next release, flushed. Locks the repository's row first, so two
    publishes at once get two numbers. `409` if the label is in use: the default one,
    the number, too."""
    await session.execute(select(Tenant.id).where(Tenant.id == repository.id).with_for_update())
    last = await session.scalar(
        select(func.max(RepositoryRelease.number)).where(
            RepositoryRelease.tenant_id == repository.id
        )
    )
    number = (last or 0) + 1
    chosen = label if label is not None else str(number)
    if await _label_in_use(session, repository.id, chosen):
        raise _taken(chosen)
    release = RepositoryRelease(
        tenant_id=repository.id,
        number=number,
        label=chosen,
        notes=notes,
        breaking=breaking,
        created_by=user_id,
    )
    session.add(release)
    await session.flush()
    await session.refresh(release)
    return release


async def relabel(
    session: AsyncSession, release: RepositoryRelease, label: str
) -> RepositoryRelease:
    """A release's label, changed: `409` if another release of the repository has it.
    A change of case alone is the same release's own label."""
    if await _label_in_use(session, release.tenant_id, label, besides=release.id):
        raise _taken(label)
    release.label = label
    return release


async def latest_release(session: AsyncSession, repository_id: uuid.UUID) -> ReleaseRef | None:
    """The repository's newest release, or none before its first (or for one published
    before there was a ledger)."""
    release = await session.scalar(
        select(RepositoryRelease)
        .where(RepositoryRelease.tenant_id == repository_id)
        .order_by(RepositoryRelease.number.desc())
        .limit(1)
    )
    return _ref(release) if release else None


async def releases_named(
    session: AsyncSession, repository_id: uuid.UUID, ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, ReleaseRef]:
    """Some of the repository's releases by id; one that is gone is not there."""
    wanted = set(ids)
    if not wanted:
        return {}
    return {
        r.id: _ref(r)
        for r in await session.scalars(
            select(RepositoryRelease).where(
                RepositoryRelease.tenant_id == repository_id, RepositoryRelease.id.in_(wanted)
            )
        )
    }
