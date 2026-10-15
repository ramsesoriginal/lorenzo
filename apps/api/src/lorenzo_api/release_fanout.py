"""Telling the libraries of a repository what it did: the fan-out of an announcement - ADR 0301,
RFC 0038 section 6.

A release, a rollback to an earlier release and the flip to private each owe every library that
holds the repository a notice to its Owners and Organizers. Done in the request that made the
release, that is two statements and more a library, which holds the repository's row for as long
as it runs and fails the request, after the release is committed, once there are a few thousand
libraries. So the request writes one row (`announce`) in the transaction of what it announces,
and the notices are written afterwards, a chunk of libraries and the cursor that says how far the
announcement has got in one transaction (`drain_chunk`), by whoever comes next:

- the process that made the release, after its response (`drain_after_response`): a hint, since a
  Cloud Run instance has no CPU guaranteed once the response is out and may be shut down;
- the process that starts, and then any process on an authenticated request, at most once a
  minute (`sweep`, `schedule_sweep`): what guarantees that a drain that stopped is finished, with
  nothing new on the deployment.

A drain that stops anywhere, a worker killed with a chunk half written, resumes from the cursor
and tells nobody twice and nobody never: the notices of a chunk and the move of the cursor are one
commit. Nothing is unique on `notification`: that guarantee is all there is.
"""

import asyncio
import contextlib
import time
import uuid
from collections.abc import Sequence
from datetime import timedelta
from enum import Enum
from typing import Any, cast

import structlog
from fastapi import BackgroundTasks
from sqlalchemy import delete, func, select, text, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.config import get_settings
from lorenzo_api.db import async_session_factory
from lorenzo_api.dependencies import set_tenant_rls_context
from lorenzo_api.models import ReleaseFanout
from lorenzo_api.notifications import create_tenant_admins_notification

__all__ = [
    "Outcome",
    "announce",
    "drain",
    "drain_after_response",
    "drain_chunk",
    "reset_sweep_gate",
    "schedule_sweep",
    "start_sweeping",
    "stop_sweeping",
    "sweep",
]

logger = structlog.get_logger()

# Where `announce` leaves the announcements this request made, for `drain_after_response`.
_HINTS = "release_fanouts"

# A finished announcement is kept this long, and then the start-up sweep removes it.
FINISHED_KEPT = timedelta(days=7)


class Outcome(Enum):
    # Nothing pending that this drain could take: none, or the one asked for is being drained.
    IDLE = "idle"
    # A chunk was written and its cursor moved.
    WROTE = "wrote"
    # Another drain moved the cursor first: this chunk was thrown away.
    LOST = "lost"


async def announce(
    session: AsyncSession,
    *,
    repository_id: uuid.UUID,
    release_id: uuid.UUID | None,
    type: str,
    title: str,
    body: str,
    created_by: uuid.UUID,
    recipients: Sequence[uuid.UUID],
) -> ReleaseFanout | None:
    """Writes the announcement of `title` and `body` to `recipients`, the libraries as they are
    now (the grants of a flip to private are gone by the time anyone drains it), in the caller's
    transaction, which is the repository's own: one statement, however many libraries. Nothing to
    announce when there is nobody to tell. No commit; the routes call `drain_after_response` once
    they have committed."""
    if not recipients:
        return None
    fanout = ReleaseFanout(
        tenant_id=repository_id,
        release_id=release_id,
        type=type,
        title=title,
        body=body,
        created_by=created_by,
        recipients=sorted(set(recipients), key=str),
    )
    session.add(fanout)
    await session.flush()
    session.info.setdefault(_HINTS, []).append(fanout.id)
    return fanout


def drain_after_response(background_tasks: BackgroundTasks, session: AsyncSession) -> None:
    """Asks for the announcements this request wrote to be drained once its response is sent, in
    this process. A hint: if the process stops first, the next sweep finishes them."""
    for fanout_id in session.info.pop(_HINTS, []):
        background_tasks.add_task(drain, fanout_id)


async def _set_sweeping(session: AsyncSession) -> None:
    """Opens the sweep policies of `release_fanout` for this transaction: the only place the
    setting is made, and nothing else reads it."""
    await session.execute(text("SELECT set_config('app.fanout_sweep', 'on', true)"))


async def drain_chunk(session: AsyncSession, fanout_id: uuid.UUID | None = None) -> Outcome:
    """Takes the oldest pending announcement (that of `fanout_id`, if given) nobody else holds,
    `FOR UPDATE SKIP LOCKED`, tells the Owners and Organizers of the next chunk of its libraries
    and moves its cursor, compared and set, in one transaction, which it commits. The caller has
    nothing to commit."""
    settings = get_settings()
    await _set_sweeping(session)
    stmt = select(ReleaseFanout).where(ReleaseFanout.done_at.is_(None))
    if fanout_id is not None:
        stmt = stmt.where(ReleaseFanout.id == fanout_id)
    row = (
        await session.scalars(
            stmt.order_by(ReleaseFanout.created_at, ReleaseFanout.id)
            .limit(1)
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
        )
    ).first()
    if row is None:
        await session.rollback()
        return Outcome.IDLE
    start = row.cursor
    chunk = row.recipients[start : start + settings.release_fanout_chunk_size]
    for library_id in chunk:
        # Membership is readable under its own library's context only, and a notice is read back
        # under it too: each library is written under its own, flushed before the next.
        await set_tenant_rls_context(session, library_id)
        await create_tenant_admins_notification(
            session,
            tenant_id=library_id,
            type=row.type,
            title=row.title,
            body=row.body,
            created_by=row.created_by,
        )
        await session.flush()
    end = start + len(chunk)
    finished = end >= len(row.recipients)
    advance = (
        update(ReleaseFanout)
        .where(ReleaseFanout.id == row.id, ReleaseFanout.cursor == start)
        .values(cursor=end, updated_at=func.now(), done_at=func.now() if finished else None)
        .execution_options(synchronize_session=False)
    )
    moved = cast("CursorResult[Any]", await session.execute(advance))
    if moved.rowcount != 1:
        await session.rollback()
        return Outcome.LOST
    await session.commit()
    session.expunge_all()
    return Outcome.WROTE


async def drain(fanout_id: uuid.UUID | None = None, *, chunks: int | None = None) -> int:
    """Drains the announcement `fanout_id`, or every pending one oldest first, a chunk a
    transaction on a session of its own, until nothing is left or `chunks` chunks are written.
    Returns the chunks written. Never raises: what stops a drain is logged and left for the
    next, which resumes from the cursor."""
    written = 0
    try:
        async with async_session_factory() as session:
            while chunks is None or written < chunks:
                if await drain_chunk(session, fanout_id) is not Outcome.WROTE:
                    break
                written += 1
    except Exception:
        logger.exception("release_fanout_drain_failed", fanout_id=str(fanout_id or ""))
    return written


# --- The sweep ----------------------------------------------------------------------------------

# When this process last started a sweep, on the monotonic clock, and whether one is running.
_last_sweep: float | None = None
_sweeping = False
_startup_sweep: asyncio.Task[int] | None = None


def reset_sweep_gate() -> None:
    """For tests: this process has not swept yet."""
    global _last_sweep, _sweeping
    _last_sweep = None
    _sweeping = False


async def sweep(*, prune: bool = False) -> int:
    """Finishes announcements that stopped, of every repository, in bounded work: at most
    `release_fanout_sweep_chunks` chunks, the rest left for the next sweep. Pending rows are one
    read of a partial index, so with none this costs that query. `prune` also removes finished
    rows kept longer than `FINISHED_KEPT`. Returns the chunks written; never raises."""
    global _last_sweep, _sweeping
    if _sweeping:
        return 0
    _sweeping = True
    _last_sweep = time.monotonic()
    try:
        written = await drain(chunks=get_settings().release_fanout_sweep_chunks)
        if prune:
            await _prune()
        return written
    finally:
        _sweeping = False


async def _prune() -> None:
    try:
        async with async_session_factory() as session:
            await _set_sweeping(session)
            await session.execute(
                delete(ReleaseFanout).where(
                    ReleaseFanout.done_at.is_not(None),
                    ReleaseFanout.done_at < func.now() - FINISHED_KEPT,
                )
            )
            await session.commit()
    except Exception:
        logger.exception("release_fanout_prune_failed")


def schedule_sweep(background_tasks: BackgroundTasks) -> None:
    """On an authenticated request: a sweep after its response, unless this process has swept
    within `release_fanout_sweep_interval_seconds`. Claims the interval now, so a burst of
    requests starts one sweep and not one each. Called from `get_current_user` only, so an
    unauthenticated path and the health checks never cost a query."""
    global _last_sweep
    interval = get_settings().release_fanout_sweep_interval_seconds
    now = time.monotonic()
    if _sweeping or (_last_sweep is not None and now - _last_sweep < interval):
        return
    _last_sweep = now
    background_tasks.add_task(sweep)


def start_sweeping() -> None:
    """At process start: finish what the process before it left, off the start-up path."""
    global _startup_sweep
    _startup_sweep = asyncio.create_task(sweep(prune=True))


async def stop_sweeping() -> None:
    """At process stop: a sweep still running is cut off, which loses nothing (its chunk is
    uncommitted) and is finished by the next process."""
    global _startup_sweep
    task, _startup_sweep = _startup_sweep, None
    if task is not None and not task.done():
        task.cancel()
    if task is not None:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task
