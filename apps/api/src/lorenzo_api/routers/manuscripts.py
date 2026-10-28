"""Saved manuscript history, gated by current edit access (ADR 0328)."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from lorenzo_api.dependencies import CurrentUser, ParamsDep, SessionDep, get_tenant_or_404
from lorenzo_api.exceptions import InformationNotFoundError
from lorenzo_api.models import ManuscriptRevision
from lorenzo_api.routers.entities import authorize_information_edit, get_information_or_404

router = APIRouter(
    prefix="/tenants/{tenant_id}/information/{information_id}/revisions",
    tags=["manuscripts"],
    dependencies=[Depends(get_tenant_or_404)],
)


class ManuscriptRevisionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    created_at: datetime


class ManuscriptRevisionOut(ManuscriptRevisionSummary):
    snapshot: dict[str, Any]


async def authorize_history(
    session: SessionDep, tenant_id: uuid.UUID, information_id: uuid.UUID, user: CurrentUser
) -> None:
    information = await get_information_or_404(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )


@router.get("")
async def list_manuscript_revisions(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
) -> Page[ManuscriptRevisionSummary]:
    await authorize_history(session, tenant_id, information_id, user)
    response.headers["Cache-Control"] = "private, no-store"
    page: Page[ManuscriptRevisionSummary] = await apaginate(
        session,
        select(ManuscriptRevision.id, ManuscriptRevision.created_at)
        .where(
            ManuscriptRevision.tenant_id == tenant_id,
            ManuscriptRevision.information_id == information_id,
        )
        .order_by(ManuscriptRevision.created_at.desc(), ManuscriptRevision.id.desc()),
        params=params,
    )

    return page


@router.get("/{revision_id}")
async def get_manuscript_revision(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    revision_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ManuscriptRevisionOut:
    await authorize_history(session, tenant_id, information_id, user)
    revision = await session.scalar(
        select(ManuscriptRevision).where(
            ManuscriptRevision.id == revision_id,
            ManuscriptRevision.tenant_id == tenant_id,
            ManuscriptRevision.information_id == information_id,
        )
    )
    if revision is None:
        raise InformationNotFoundError(detail="No such saved manuscript revision.")
    response.headers["Cache-Control"] = "private, no-store"
    return ManuscriptRevisionOut.model_validate(revision)
