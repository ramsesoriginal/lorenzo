import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_context
from lorenzo_api.exceptions import PayloadContentNotFoundError, PayloadNotFoundError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Information, Payload

# get_tenant_context here, not per-route (ADR 0020's revised guidance) -
# every route on this router needs it and none read its return value, the
# textbook case FastAPI's own docs give for a router-level dependency.
router = APIRouter(
    prefix="/tenants/{tenant_id}/payloads",
    tags=["payloads"],
    dependencies=[Depends(get_tenant_context)],
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


@router.get("/{payload_id}/content", name="payload_content")
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
