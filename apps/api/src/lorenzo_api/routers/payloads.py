import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from lorenzo_api.db import get_db_session
from lorenzo_api.dependencies import get_tenant_context
from lorenzo_api.models import Payload

router = APIRouter(prefix="/tenants/{tenant_id}/payloads", tags=["payloads"])


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
    session: AsyncSession = Depends(get_db_session),
    _tenant: uuid.UUID = Depends(get_tenant_context),
) -> Response:
    """Raw bytes for a picture/document payload, with the correct
    Content-Type - and Content-Disposition for documents - rather than
    embedding the bytes inline in a JSON response. See ADR 0020.
    """
    payload = await session.get(
        Payload,
        payload_id,
        options=[selectinload(Payload.picture), selectinload(Payload.document)],
    )
    if payload is None or payload.tenant_id != tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Payload not found")

    if payload.picture is not None:
        return Response(content=payload.picture.data, media_type=payload.picture.file_type)
    if payload.document is not None:
        return Response(
            content=payload.document.data,
            media_type=payload.document.file_type,
            headers={
                "content-disposition": _content_disposition(
                    "attachment", payload.document.filename
                )
            },
        )
    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Payload has no binary content")
