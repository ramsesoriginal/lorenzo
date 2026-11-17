"""Saved manuscript export previews and conditional source downloads (ADR 0478)."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import PayloadPreconditionRequiredError, PreconditionFailedError
from lorenzo_api.manuscript_export import ExportSnapshot, assemble, source_archive

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing export"],
    dependencies=[Depends(get_tenant_or_404)],
)


@asynccontextmanager
async def snapshot_session(
    parent: AsyncSession, tenant: uuid.UUID, user: CurrentUser
) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(bind=parent.bind, expire_on_commit=False) as session:
        await session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        await session.execute(
            text("SELECT set_config('app.user_id', :user, true)"), {"user": str(user.id)}
        )
        await set_tenant_rls_context(session, tenant)
        yield session


async def preview(
    parent: AsyncSession,
    tenant: uuid.UUID,
    id: uuid.UUID,
    user: CurrentUser,
    response: Response,
    if_match: str | None,
    *,
    review: bool,
) -> ExportSnapshot:
    async with snapshot_session(parent, tenant, user) as session:
        result = await assemble(session, tenant, id, user, review=review)
        if if_match is not None and if_match != result.version:
            raise PreconditionFailedError(
                detail="The saved writing changed. Refresh the export preview."
            )
        response.headers["ETag"] = result.version
        response.headers["Cache-Control"] = "private, no-store"
        return result


@router.get("/entries/{id}/export")
async def export_preview(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ExportSnapshot:
    return await preview(session, tenant_id, id, user, response, if_match, review=False)


@router.get("/reviews/{id}/export")
async def review_export_preview(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ExportSnapshot:
    return await preview(session, tenant_id, id, user, response, if_match, review=True)


async def download(
    parent: AsyncSession,
    tenant: uuid.UUID,
    id: uuid.UUID,
    user: CurrentUser,
    if_match: str | None,
    *,
    review: bool,
) -> Response:
    if if_match is None:
        raise PayloadPreconditionRequiredError(
            detail="Open the export preview before downloading its source."
        )
    headers = Response()
    snapshot = await preview(parent, tenant, id, user, headers, if_match, review=review)
    return Response(
        content=source_archive(snapshot),
        media_type="application/zip",
        headers={
            "ETag": snapshot.version,
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="writing-{id}.zip"',
        },
    )


@router.get(
    "/entries/{id}/export/source",
    response_class=Response,
    responses={
        200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def export_source(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> Response:
    return await download(session, tenant_id, id, user, if_match, review=False)


@router.get(
    "/reviews/{id}/export/source",
    response_class=Response,
    responses={
        200: {"content": {"application/zip": {"schema": {"type": "string", "format": "binary"}}}}
    },
)
async def review_export_source(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> Response:
    return await download(session, tenant_id, id, user, if_match, review=True)
