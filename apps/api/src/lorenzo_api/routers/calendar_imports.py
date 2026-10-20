"""Read-only plans and atomic, repeatable calendar imports (ADR 0311)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path
from lorenzo_calendar.document import CalendarDocument

from lorenzo_api.calendar_imports import apply_import, export_document, prepare
from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_context
from lorenzo_api.schemas.calendar_imports import (
    CalendarImportApply,
    CalendarImportPlan,
    CalendarImportReceipt,
    CalendarImportRequest,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}/calendar-imports",
    tags=["calendar imports"],
    dependencies=[Depends(get_tenant_context)],
)


@router.post("/plan")
async def plan_calendar_import(
    tenant_id: uuid.UUID, body: CalendarImportRequest, session: SessionDep, user: CurrentUser
) -> CalendarImportPlan:
    return (await prepare(session, user, tenant_id, body)).plan


@router.post("")
async def apply_calendar_import(
    tenant_id: uuid.UUID, body: CalendarImportApply, session: SessionDep, user: CurrentUser
) -> CalendarImportReceipt:
    receipt = await apply_import(session, user, tenant_id, body)
    await session.commit()
    return receipt


@router.get("/{source_key}/document")
async def export_calendar_import(
    tenant_id: uuid.UUID,
    source_key: Annotated[str, Path(pattern=r"^[a-z][a-z0-9-]{0,63}$")],
    session: SessionDep,
    user: CurrentUser,
) -> CalendarDocument:
    return await export_document(session, user, tenant_id, source_key)
