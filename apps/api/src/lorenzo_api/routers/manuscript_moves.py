"""Conditional cross-parent moves with replay-safe structural checkpoints (ADR 0344)."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from lorenzo_api.campaign_access import is_tenant_author
from lorenzo_api.client_ids import existing_in_tenant, insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    EntityNotFoundError,
    InvalidKindRequestError,
    ManuscriptMoveConflictError,
    ManuscriptMovePreconditionRequiredError,
    PreconditionFailedError,
)
from lorenzo_api.models import (
    Chapter,
    Edition,
    Entity,
    ManuscriptMove,
    ManuscriptPlacement,
    SceneTelling,
    WritingReviewGrant,
)
from lorenzo_api.routers.writing import author, entry, manuscript_payloads, result

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class MoveRequest(BaseModel):
    source_parent_id: uuid.UUID | None
    destination_parent_id: uuid.UUID | None
    source_version: str | None = Field(default=None, max_length=200)
    destination_version: str | None = Field(default=None, max_length=200)
    before_element_id: uuid.UUID | None = None


class MoveAcknowledgement(BaseModel):
    operation_id: uuid.UUID
    entry_id: uuid.UUID
    source_parent_id: uuid.UUID | None
    destination_parent_id: uuid.UUID | None


class MoveCheckpoint(MoveAcknowledgement):
    checkpoint: dict[str, Any]


async def edition_of(session: SessionDep, id: uuid.UUID | None) -> uuid.UUID | None:
    seen: set[uuid.UUID] = set()
    while id is not None and id not in seen:
        seen.add(id)
        if await session.get(Edition, id):
            return id
        placement = await session.get(ManuscriptPlacement, id)
        id = placement.parent_entity_id if placement else None
    return None


async def reviewers_of(
    session: SessionDep, tenant_id: uuid.UUID, parent: uuid.UUID | None
) -> set[uuid.UUID]:
    edition = await edition_of(session, parent)
    if edition is None:
        return set()
    people = await session.scalars(
        select(WritingReviewGrant.user_id).where(
            WritingReviewGrant.tenant_id == tenant_id, WritingReviewGrant.edition_id == edition
        )
    )
    return {
        person
        for person in people
        if not await is_tenant_author(session, tenant_id=tenant_id, user_id=person)
    }


def require_version(sent: str | None, current: str) -> None:
    if sent is None:
        raise ManuscriptMovePreconditionRequiredError(
            detail="Read both outlines before moving this entry."
        )
    if sent != current:
        raise PreconditionFailedError(
            detail="An outline changed. Read it again before moving this entry."
        )


@router.post("/entries/{id}/moves/{operation_id}")
async def move(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    operation_id: uuid.UUID,
    body: MoveRequest,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> MoveAcknowledgement:
    await author(session, tenant_id, user)
    moved = await entry(session, tenant_id, id, user, lock=True)
    fingerprint = hashlib.sha256(
        json.dumps(
            {"entry": str(id), "version": if_match, "body": body.model_dump(mode="json")},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    previous = await existing_in_tenant(session, ManuscriptMove, operation_id, tenant_id)
    response.headers["Cache-Control"] = "private, no-store"
    if previous:
        if (
            previous.actor_id != user.id
            or previous.entry_id != id
            or previous.request_hash != fingerprint
        ):
            raise ClientIdUnavailableError(detail="That move id is already in use.")
        return MoveAcknowledgement.model_validate(previous.acknowledgement)
    if not await session.get(Chapter, id) and not await session.get(SceneTelling, id):
        raise InvalidKindRequestError(detail="Move a Chapter or Scene telling.")
    placement = await session.get(ManuscriptPlacement, id)
    source = placement.parent_entity_id if placement else None
    target = body.destination_parent_id
    if source != body.source_parent_id:
        raise PreconditionFailedError(detail="This entry has moved. Read its current outline.")
    if source == target:
        raise ManuscriptMoveConflictError(
            detail="Choose a different parent, or reorder this outline."
        )
    if target is None and body.before_element_id is not None:
        raise InvalidKindRequestError(detail="Unassigned writing has no insertion position.")
    # Lock bundles before evaluating versions; prose edits cannot change anchors mid-move.
    await manuscript_payloads(session, tenant_id, id, lock=True)
    current = await result(session, tenant_id, id, user, response)
    require_version(if_match, current.version)
    parents: dict[uuid.UUID, Entity] = {}
    outlines: dict[uuid.UUID, list[uuid.UUID]] = {}
    payload_ids: dict[uuid.UUID, set[uuid.UUID]] = {}
    for parent_id in sorted({p for p in (source, target) if p is not None}):
        parents[parent_id] = await entry(session, tenant_id, parent_id, user, lock=True)
        if not await session.get(Edition, parent_id) and not await session.get(Chapter, parent_id):
            raise InvalidKindRequestError(detail="Choose an Edition or Chapter as the destination.")
        _, payloads = await manuscript_payloads(session, tenant_id, parent_id, lock=True)
        outline = await result(session, tenant_id, parent_id, user, response)
        require_version(
            body.source_version if parent_id == source else body.destination_version,
            outline.version,
        )
        outlines[parent_id] = [el.id for el in outline.elements]
        payload_ids[parent_id] = {p.id for p in payloads}
    ancestor = target
    while ancestor is not None:
        if ancestor == id:
            raise ManuscriptMoveConflictError(
                detail="A Chapter cannot contain itself or an ancestor."
            )
        above = await session.get(ManuscriptPlacement, ancestor)
        ancestor = above.parent_entity_id if above else None
    source_reviewers = await reviewers_of(session, tenant_id, source)
    target_reviewers = await reviewers_of(session, tenant_id, target)
    if not target_reviewers.issubset(source_reviewers):
        raise ManuscriptMoveConflictError(
            detail="This move would add reviewers. Review the Edition's sharing first."
        )
    before = {str(parent): [str(el) for el in ids] for parent, ids in outlines.items()}
    if source is not None:
        outlines[source].remove(id)
    if target is not None:
        ids = outlines[target]
        if body.before_element_id is not None and body.before_element_id not in ids:
            raise PreconditionFailedError(
                detail="The insertion position changed. Read the destination again."
            )
        position = (
            ids.index(body.before_element_id) if body.before_element_id is not None else len(ids)
        )
        ids.insert(position, id)
    # All checks precede mutation. Payloads, their order and all notes stay untouched.
    await session.execute(
        delete(ManuscriptPlacement).where(
            ManuscriptPlacement.tenant_id == tenant_id,
            ManuscriptPlacement.parent_entity_id.in_(parents),
        )
    )
    for parent_id, ids in outlines.items():
        anchor = None
        for position, child_id in reversed(list(enumerate(ids))):
            if child_id in payload_ids[parent_id]:
                anchor = child_id
            else:
                session.add(
                    ManuscriptPlacement(
                        tenant_id=tenant_id,
                        child_entity_id=child_id,
                        parent_entity_id=parent_id,
                        before_payload_id=anchor,
                        position=position,
                    )
                )
    for row in [moved, *parents.values()]:
        row.updated_at = datetime.now(UTC)
        row.updated_by = user.id
    acknowledgement = MoveAcknowledgement(
        operation_id=operation_id,
        entry_id=id,
        source_parent_id=source,
        destination_parent_id=target,
    )
    await insert_with_client_id(
        session,
        ManuscriptMove(
            id=operation_id,
            tenant_id=tenant_id,
            entry_id=id,
            actor_id=user.id,
            request_hash=fingerprint,
            acknowledgement=acknowledgement.model_dump(mode="json"),
            checkpoint={
                "before": before,
                "after": {str(parent): [str(el) for el in ids] for parent, ids in outlines.items()},
            },
        ),
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    del response.headers["ETag"]
    return acknowledgement


@router.get("/entries/{id}/moves/{operation_id}")
async def read_move(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    operation_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> MoveCheckpoint:
    await author(session, tenant_id, user)
    await entry(session, tenant_id, id, user)
    receipt = await existing_in_tenant(session, ManuscriptMove, operation_id, tenant_id)
    if receipt is None or receipt.entry_id != id:
        raise EntityNotFoundError(detail="No such move checkpoint.")
    response.headers["Cache-Control"] = "private, no-store"
    return MoveCheckpoint(**receipt.acknowledgement, checkpoint=receipt.checkpoint)
