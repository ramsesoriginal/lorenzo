"""Move one text or picture of a manuscript to another Chapter or Edition (ADR 0520)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import ManuscriptMoveConflictError
from lorenzo_api.manuscript_access import require_no_new_readers
from lorenzo_api.models import (
    Chapter,
    Edition,
    Information,
    Knowledge,
    ManuscriptPlacement,
)
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.manuscript_extraction import place
from lorenzo_api.routers.manuscript_joins import same_inner, same_outer
from lorenzo_api.routers.manuscript_moves import require_version
from lorenzo_api.routers.writing import author, children, entry, manuscript_payloads, result

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class MoveBlock(BaseModel):
    destination_id: uuid.UUID
    destination_version: str = Field(max_length=200)
    before_element_id: uuid.UUID | None = None


class BlockMoveAcknowledgement(BaseModel):
    payload_id: uuid.UUID
    source_id: uuid.UUID
    destination_id: uuid.UUID


@router.post("/entries/{id}/payloads/{payload_id}/move")
async def move_block(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    payload_id: uuid.UUID,
    body: MoveBlock,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> BlockMoveAcknowledgement:
    """Moves a text or picture of a Chapter's or Edition's manuscript into another one's.

    The two outlines are read as the caller last saw them (`If-Match` for the source, the body for
    the destination); the two must be shared alike, as in a join; the block lands before
    `before_element_id` or at the end.
    """
    await author(session, tenant_id, user)
    destination_id = body.destination_id
    if id == destination_id:
        raise ManuscriptMoveConflictError(detail="Choose another Chapter to move this to.")
    rows = {
        key: await entry(session, tenant_id, key, user, lock=True)
        for key in sorted({id, destination_id})
    }
    for key in (id, destination_id):
        if not await session.get(Chapter, key) and not await session.get(Edition, key):
            raise ManuscriptMoveConflictError(detail="Move between Chapters or Editions.")
    response.headers["Cache-Control"] = "private, no-store"
    bundles = {}
    outlines = {}
    for key in sorted(rows):
        info, payloads = await manuscript_payloads(session, tenant_id, key, lock=True)
        if info:
            await authorize_information_edit(
                session, tenant_id=tenant_id, user=user, information=info
            )
        bundles[key] = (info, payloads)
        outline = await result(session, tenant_id, key, user, response)
        require_version(if_match if key == id else body.destination_version, outline.version)
        outlines[key] = [el.id for el in outline.elements]
        links = await children(session, tenant_id, key)
        if set(outlines[key]) != {p.id for p in payloads} | {p.child_entity_id for p in links}:
            raise ManuscriptMoveConflictError(
                detail="Read the complete outlines before moving writing."
            )
    source_info, source_payloads = bundles[id]
    destination_info, destination_payloads = bundles[destination_id]
    moved = next((p for p in source_payloads if p.id == payload_id), None)
    if moved is None or source_info is None:
        raise ManuscriptMoveConflictError(detail="That text or picture is not in this Chapter.")
    before = body.before_element_id
    if before is not None and before not in outlines[destination_id]:
        raise ManuscriptMoveConflictError(detail="Choose a place in the destination outline.")
    if not await same_outer(session, id, destination_id):
        raise ManuscriptMoveConflictError(
            detail="These Chapters have different sharing. Review their audiences before moving."
        )
    if destination_info and not same_inner(source_info, destination_info):
        raise ManuscriptMoveConflictError(
            detail="These manuscripts have different sharing or authorship. Review them first."
        )
    await require_no_new_readers(
        session, tenant_id, id, destination_id, source_info, destination_info
    )
    if destination_info is None:
        destination_info = Information(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entity_id=destination_id,
            title=source_info.title,
            type="manuscript",
            created_by=source_info.created_by,
            is_public=source_info.is_public,
            shared_with_participants=source_info.shared_with_participants,
        )
        session.add(destination_info)
        await session.flush()
        for grant in source_info.knowledge_links:
            session.add(
                Knowledge(
                    tenant_id=tenant_id,
                    information_id=destination_info.id,
                    knower_entity_id=grant.knower_entity_id,
                    knower_player_id=grant.knower_player_id,
                )
            )
    rest = [x for x in outlines[id] if x != payload_id]
    target = list(outlines[destination_id])
    target.insert(target.index(before) if before is not None else len(target), payload_id)
    # Stage the orders first so the unique (information, order) never collides while they change.
    for payloads in (source_payloads, destination_payloads):
        floor = min((p.order for p in payloads), default=0) - len(payloads) - 1
        for n, payload in enumerate(payloads):
            payload.order = floor + n
    await session.flush()
    by_id = {p.id: p for p in [*source_payloads, *destination_payloads]}
    moved.information_id = destination_info.id
    for info, ids in ((source_info, rest), (destination_info, target)):
        for n, payload in enumerate(by_id[x] for x in ids if x in by_id):
            payload.order = n
            payload.updated_at = datetime.now(UTC)
        info.updated_at = datetime.now(UTC)
    await session.execute(
        delete(ManuscriptPlacement).where(
            ManuscriptPlacement.tenant_id == tenant_id,
            ManuscriptPlacement.parent_entity_id.in_(rows),
        )
    )
    place(session, tenant_id, id, rest, {x for x in rest if x in by_id})
    place(session, tenant_id, destination_id, target, {x for x in target if x in by_id})
    for row in rows.values():
        row.updated_at = datetime.now(UTC)
        row.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    if "ETag" in response.headers:
        del response.headers["ETag"]
    return BlockMoveAcknowledgement(
        payload_id=payload_id, source_id=id, destination_id=destination_id
    )
