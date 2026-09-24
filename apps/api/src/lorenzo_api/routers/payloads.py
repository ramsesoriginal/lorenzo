import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_context,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.description_payloads import write_description
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    PayloadContentNotFoundError,
    PayloadKindNotEditableError,
    PayloadNotFoundError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Information, Payload
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.schemas.payloads import (
    PayloadDescriptionOut,
    PayloadDescriptionUpdate,
    description_payload_out,
)

# get_tenant_or_404 at the router level, get_tenant_context on the content
# read only (ADR 0101). The read always needed a tenant Membership (ADR
# 0020); the description PATCH uses self-or-managed plus sight of the row
# instead, like routers/information.py, so it must not.
router = APIRouter(
    prefix="/tenants/{tenant_id}/payloads",
    tags=["payloads"],
    dependencies=[Depends(get_tenant_or_404)],
)


def _content_disposition(disposition_type: str, filename: str) -> str:
    # Same encoding Starlette's own FileResponse uses for a filename it
    # can't losslessly quote as a plain ASCII token - see
    # starlette.responses.FileResponse.__init__. Not exposed as a public
    # helper there, so replicated rather than depended on across a private
    # boundary.
    quoted = quote(filename)
    if quoted != filename:
        return f"{disposition_type}; filename*=utf-8''{quoted}"
    return f'{disposition_type}; filename="{filename}"'


@router.get(
    "/{payload_id}/content",
    name="payload_content",
    dependencies=[Depends(get_tenant_context)],
)
async def get_payload_content(
    tenant_id: uuid.UUID,
    payload_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    """Raw bytes for a picture/document payload, with the correct
    Content-Type - and Content-Disposition for documents - rather than
    embedding the bytes inline in a JSON response. See ADR 0020.

    Same information_visibility check as GET /entities/{id} (ADR 0028's
    addendum) - a payload is only as visible as the Information it
    belongs to. "Doesn't exist," "wrong tenant," and "exists but you can't
    see its information" all raise the exact same PayloadNotFoundError,
    same body - matching get_tenant_context's own established precedent
    (ADR 0023) of not letting a caller distinguish "not found" from
    "found, but not for you."
    """
    stmt = (
        select(Payload)
        .where(Payload.id == payload_id, Payload.tenant_id == tenant_id)
        .options(
            selectinload(Payload.picture),
            selectinload(Payload.document),
            selectinload(Payload.information).selectinload(Information.knowledge_links),
        )
    )
    payload = (await session.execute(stmt)).scalar_one_or_none()
    if payload is None:
        raise PayloadNotFoundError(detail=f"No payload with id {payload_id} in tenant {tenant_id}")

    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    if not visibility.can_see(payload.information):
        raise PayloadNotFoundError(detail=f"No payload with id {payload_id} in tenant {tenant_id}")

    if payload.picture is not None:
        return Response(content=payload.picture.data, media_type=payload.picture.file_type)
    if payload.document is not None:
        return Response(
            content=payload.document.data,
            media_type=payload.document.file_type,
            headers={
                "content-disposition": _content_disposition("attachment", payload.document.filename)
            },
        )
    raise PayloadContentNotFoundError(
        detail=f"Payload {payload_id} has no picture or document content"
    )


async def _get_payload_for_edit_or_404(
    session: SessionDep, payload_id: uuid.UUID, tenant_id: uuid.UUID
) -> Payload:
    stmt = (
        select(Payload)
        .where(Payload.id == payload_id, Payload.tenant_id == tenant_id)
        .options(
            selectinload(Payload.description),
            selectinload(Payload.information).selectinload(Information.knowledge_links),
        )
        # updated_at is set by the database on write - a re-read must
        # replace the identity-map copy (expire_on_commit=False).
        .execution_options(populate_existing=True)
    )
    payload = (await session.execute(stmt)).scalar_one_or_none()
    if payload is None:
        raise PayloadNotFoundError(detail=f"No payload with id {payload_id} in tenant {tenant_id}")
    return payload


@router.patch("/{payload_id}")
async def update_payload(
    tenant_id: uuid.UUID,
    payload_id: uuid.UUID,
    body: PayloadDescriptionUpdate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> PayloadDescriptionOut:
    """Replaces a description payload's text and/or locale - ADR 0101, the
    endpoint RFC 0027's description editor needs. Check order: the payload
    exists (404), sight of its Information row or authorship (404, like a
    missing payload), standing over the entity (403), description kind
    (409 - other kinds aren't editable yet), If-Match against the payload's
    own updated_at (412).

    The text goes through description_payloads.write_description, the one
    write path for it; `content` is stored as given. Not logged (ADR 0084:
    descriptive content).
    """
    payload = await _get_payload_for_edit_or_404(session, payload_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=payload.information
    )
    if payload.description is None:
        raise PayloadKindNotEditableError(
            detail=f"Payload {payload_id} is not a description payload"
        )
    check_if_match(if_match, updated_at=payload.updated_at)

    await write_description(session, payload=payload, content=body.content, locale=body.locale)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    payload = await _get_payload_for_edit_or_404(session, payload_id, tenant_id)
    response.headers["ETag"] = etag_for(payload.updated_at)
    return description_payload_out(payload)
