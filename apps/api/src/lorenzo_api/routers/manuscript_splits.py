"""Conditional, retry-safe text splits at conservative paragraph boundaries (ADR 0346)."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field

from lorenzo_api.client_ids import existing_in_tenant, insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    ManuscriptMoveConflictError,
    PayloadPreconditionRequiredError,
    PreconditionFailedError,
)
from lorenzo_api.manuscript_split_points import split_points
from lorenzo_api.models import ManuscriptSplit, Payload, PayloadDescription
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.writing import author, entry, manuscript_payloads, result

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class SplitPoint(BaseModel):
    offset: int
    following: str


class SplitPoints(BaseModel):
    source: str
    version: str
    points: list[SplitPoint]
    explanation: str | None = None


class SplitText(BaseModel):
    payload_id: uuid.UUID
    second_payload_id: uuid.UUID
    offset: int = Field(ge=1)


class SplitAcknowledgement(BaseModel):
    operation_id: uuid.UUID
    entry_id: uuid.UUID
    first_payload_id: uuid.UUID
    second_payload_id: uuid.UUID


async def text_payload(
    session: SessionDep, id: uuid.UUID, payloads: list[Payload]
) -> PayloadDescription:
    if id not in {p.id for p in payloads}:
        raise ManuscriptMoveConflictError(detail="Choose a text block in this manuscript.")
    description = await session.get(PayloadDescription, id)
    if description is None:
        raise ManuscriptMoveConflictError(detail="Choose a text block, not a picture.")
    return description


@router.get("/entries/{id}/payloads/{payload_id}/split-points")
async def available(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    payload_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SplitPoints:
    await author(session, tenant_id, user)
    await entry(session, tenant_id, id, user)
    info, payloads = await manuscript_payloads(session, tenant_id, id, lock=True)
    if info is None:
        raise ManuscriptMoveConflictError(detail="This entry has no manuscript text to split.")
    await authorize_information_edit(session, tenant_id=tenant_id, user=user, information=info)
    description = await text_payload(session, payload_id, payloads)
    current = await result(session, tenant_id, id, user, response)
    if current.uses_scene_manuscript:
        raise ManuscriptMoveConflictError(
            detail="Open the source Scene to split its shared manuscript."
        )
    points = [
        SplitPoint(offset=offset, following=description.content[offset : offset + 100].strip())
        for offset in split_points(description.content)
    ]
    response.headers["Cache-Control"] = "private, no-store"
    return SplitPoints(
        source=description.content,
        version=current.version,
        points=points,
        explanation=None
        if points
        else (
            "No safe paragraph boundary here. Keep compound blocks and dependent footnotes "
            "together; you can still extract the whole text block."
        ),
    )


@router.post("/entries/{id}/splits/{operation_id}")
async def split(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    operation_id: uuid.UUID,
    body: SplitText,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SplitAcknowledgement:
    await author(session, tenant_id, user)
    row = await entry(session, tenant_id, id, user, lock=True)
    info, payloads = await manuscript_payloads(session, tenant_id, id, lock=True)
    if info is None:
        raise ManuscriptMoveConflictError(detail="This entry has no manuscript text to split.")
    await authorize_information_edit(session, tenant_id=tenant_id, user=user, information=info)
    fingerprint = hashlib.sha256(
        json.dumps(
            {"entry": str(id), "version": if_match, "body": body.model_dump(mode="json")},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    previous = await existing_in_tenant(session, ManuscriptSplit, operation_id, tenant_id)
    response.headers["Cache-Control"] = "private, no-store"
    if previous:
        if (
            previous.actor_id != user.id
            or previous.entry_id != id
            or previous.request_hash != fingerprint
        ):
            raise ClientIdUnavailableError(detail="That split id is already in use.")
        return SplitAcknowledgement(
            operation_id=operation_id,
            entry_id=id,
            first_payload_id=previous.first_payload_id,
            second_payload_id=previous.second_payload_id,
        )
    current = await result(session, tenant_id, id, user, response)
    if current.uses_scene_manuscript:
        raise ManuscriptMoveConflictError(
            detail="Open the source Scene to split its shared manuscript."
        )
    if if_match is None:
        raise PayloadPreconditionRequiredError(detail="Read the saved text before splitting it.")
    if if_match != current.version:
        raise PreconditionFailedError(
            detail="This manuscript changed. Reopen the outline before splitting it."
        )
    description = await text_payload(session, body.payload_id, payloads)
    if body.offset not in split_points(description.content):
        raise ManuscriptMoveConflictError(
            detail=(
                "This boundary would change the text's structure or separate a footnote. "
                "Choose a safe paragraph boundary."
            )
        )
    if await existing_in_tenant(session, Payload, body.second_payload_id, tenant_id):
        raise ClientIdUnavailableError(detail="That text block id is already in use.")
    original = description.content
    # Checkpoint before changing text; keep all interim order numbers disjoint.
    floor = min(p.order for p in payloads) - len(payloads) - 1
    for index, payload in enumerate(payloads):
        payload.order = floor + index
    await session.flush()
    position = next(n for n, payload in enumerate(payloads) if payload.id == body.payload_id)
    second = Payload(
        id=body.second_payload_id, tenant_id=tenant_id, information_id=info.id, order=position + 1
    )
    await insert_with_client_id(session, second)
    session.add(
        PayloadDescription(
            payload_id=second.id,
            tenant_id=tenant_id,
            locale=description.locale,
            content=original[body.offset :],
        )
    )
    description.content = original[: body.offset]
    for index, payload in enumerate(payloads):
        payload.order = index if index <= position else index + 1
        payload.updated_at = datetime.now(UTC)
    info.updated_at = row.updated_at = datetime.now(UTC)
    row.updated_by = user.id
    await insert_with_client_id(
        session,
        ManuscriptSplit(
            id=operation_id,
            tenant_id=tenant_id,
            entry_id=id,
            first_payload_id=body.payload_id,
            second_payload_id=second.id,
            actor_id=user.id,
            request_hash=fingerprint,
        ),
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    del response.headers["ETag"]
    return SplitAcknowledgement(
        operation_id=operation_id,
        entry_id=id,
        first_payload_id=body.payload_id,
        second_payload_id=body.second_payload_id,
    )
