"""Frames and axes: the closed list, the limits, the write guards and the resolution along a chain
(ADR 0369, 0370).

A frame is an entry with a designation; an entry is on at most one frame per axis. Resolution is per
axis and the nearest explicit row wins; a frame on a frame of the same axis goes on up. Nothing here
is read as containment, a place, a prototype or reach, and no player read calls it.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select, text, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.exceptions import InvalidFrameError
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import EntityFrame, Frame

#: The axes of every library, in the order a read lists them. Widened only by an ADR.
AXES = ("plane", "sphere", "timeline", "universe")
#: A chain of frames of one axis, the entry's own frame included, is at most this long.
MAX_FRAME_DEPTH = 8
#: A library holds at most this many frames and memberships.
MAX_FRAMES_PER_LIBRARY = 2_000
MAX_MEMBERSHIPS_PER_LIBRARY = 20_000


def require_axis(axis: str) -> str:
    """The axis, or a refusal in words: only the platform's axes are written."""
    if axis not in AXES:
        raise InvalidFrameError(detail=f"An axis is one of {', '.join(AXES)}")
    return axis


async def lock_frames(session: AsyncSession, tenant_id: uuid.UUID) -> None:
    """One frame writer at a time per library, so two writes cannot each pass the loop check and
    together make a loop."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended('lorenzo:frames:' || :tenant, 0))"),
        {"tenant": str(tenant_id)},
    )


async def require_room(session: AsyncSession, *, tenant_id: uuid.UUID, frames: bool) -> None:
    """Refuses one more frame or membership beyond the library's limit."""
    model = Frame if frames else EntityFrame
    count = await session.scalar(
        select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
    )
    limit = MAX_FRAMES_PER_LIBRARY if frames else MAX_MEMBERSHIPS_PER_LIBRARY
    if (count or 0) + 1 > limit:
        raise InvalidFrameError(
            detail=f"A library holds at most {limit:,} {'frames' if frames else 'memberships'}"
        )


async def check_membership(
    session: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    axis: str,
    frame_id: uuid.UUID,
) -> None:
    """Refuses putting `entity_id` on `frame_id` when that would make frames of one axis a loop or
    a chain longer than the limit. Read over every row, whoever sees it: it guards the data."""
    if entity_id == frame_id:
        raise InvalidFrameError(detail="An entry cannot be on itself")
    seen = {entity_id}
    length = 1
    node = frame_id
    while True:
        if node in seen:
            raise InvalidFrameError(detail="That would make frames of one axis a loop")
        seen.add(node)
        above = await session.scalar(
            select(EntityFrame.frame_entity_id).where(
                EntityFrame.tenant_id == tenant_id,
                EntityFrame.entity_id == node,
                EntityFrame.axis == axis,
            )
        )
        if above is None:
            return
        if above in seen:
            raise InvalidFrameError(detail="That would make frames of one axis a loop")
        length += 1
        if length > MAX_FRAME_DEPTH:
            raise InvalidFrameError(detail=f"A chain of frames is at most {MAX_FRAME_DEPTH} long")
        node = above


async def frames_along(
    session: AsyncSession,
    vis: InformationVisibility,
    *,
    tenant_id: uuid.UUID,
    chain: list[uuid.UUID],
) -> dict[str, list[uuid.UUID]]:
    """The frames of an entry, by axis, nearest first. `chain` is the entry and what it sits in,
    nearest first, already limited to what the reader sees. Per axis the first node with a row gives
    the frame (a frame the reader cannot see is no row); then that frame's own row on the same axis,
    and so on up to the depth limit, ending quietly on a loop."""
    if not chain:
        return {}
    found = (
        await session.execute(
            select(EntityFrame.entity_id, EntityFrame.axis, EntityFrame.frame_entity_id).where(
                EntityFrame.tenant_id == tenant_id,
                EntityFrame.entity_id.in_(chain),
                EntityFrame.axis.in_(AXES),
                visible_entry_clause(vis, EntityFrame.frame_entity_id),
            )
        )
    ).all()
    rows = {(node, axis): frame for node, axis, frame in found}
    result: dict[str, list[uuid.UUID]] = {}
    for axis in AXES:
        for node in chain:
            if (node, axis) in rows:
                result[axis] = [rows[(node, axis)]]
                break
    for _ in range(MAX_FRAME_DEPTH - 1):
        pairs = [(axis, tail[-1]) for axis, tail in result.items() if len(tail) < MAX_FRAME_DEPTH]
        if not pairs:
            break
        above = (
            await session.execute(
                select(EntityFrame.entity_id, EntityFrame.axis, EntityFrame.frame_entity_id).where(
                    EntityFrame.tenant_id == tenant_id,
                    tuple_(EntityFrame.axis, EntityFrame.entity_id).in_(pairs),
                    visible_entry_clause(vis, EntityFrame.frame_entity_id),
                )
            )
        ).all()
        if not above:
            break
        for node, axis, frame in above:
            tail = result[axis]
            if tail[-1] == node and frame not in tail and frame != chain[0]:
                tail.append(frame)
    return result
