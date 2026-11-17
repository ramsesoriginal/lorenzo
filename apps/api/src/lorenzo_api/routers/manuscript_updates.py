"""Atomic connected manuscript repository reviews (ADR 0438)."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    InvalidRepositoryUpdateError,
    PayloadPreconditionRequiredError,
    PreconditionFailedError,
)
from lorenzo_api.manuscript_applying import apply
from lorenzo_api.manuscript_review import CompositionReview, review
from lorenzo_api.models import Information, ManuscriptRepositoryUpdate
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.writing import author, entry

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing/entries/{id}/repository-updates",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


@asynccontextmanager
async def snapshot(
    parent: AsyncSession, tenant: uuid.UUID, user: CurrentUser
) -> AsyncIterator[AsyncSession]:
    # Authentication has already queried its request session. A dedicated transaction sets
    # isolation before its first read, while retaining exactly the restricted application role.
    async with AsyncSession(bind=parent.bind, expire_on_commit=False) as session:
        await session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        await session.execute(
            text("SELECT set_config('app.user_id', :user, true)"), {"user": str(user.id)}
        )
        await set_tenant_rls_context(session, tenant)
        try:
            await author(session, tenant, user)
            yield session
        except DBAPIError as error:
            await session.rollback()
            if getattr(error.orig, "sqlstate", None) in {"40001", "40P01"}:
                raise PreconditionFailedError(
                    detail="The composition changed during review. Compare again."
                ) from error
            if getattr(error.orig, "sqlstate", "").startswith("23"):
                raise InvalidRepositoryUpdateError(
                    detail="These choices conflict with a retained reference. Review the dependent "
                    "writing together."
                ) from error
            raise


@router.get("")
async def compare_manuscript_composition(
    tenant_id: uuid.UUID, id: uuid.UUID, response: Response, session: SessionDep, user: CurrentUser
) -> CompositionReview:
    async with snapshot(session, tenant_id, user) as current:
        result = (await review(current, tenant_id, id, user)).result
        response.headers["ETag"] = result.version
        response.headers["Cache-Control"] = "private, no-store"
        return result


class Choices(BaseModel):
    choices: dict[str, Literal["local", "upstream"]] = Field(min_length=1)


class Accepted(BaseModel):
    checkpoint_id: uuid.UUID


@router.post("")
async def accept_manuscript_composition(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    body: Choices,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> Accepted:
    if if_match is None:
        raise PayloadPreconditionRequiredError(
            detail="Compare the composition and send its ETag as If-Match."
        )
    async with snapshot(session, tenant_id, user) as current:
        reviewed = await review(current, tenant_id, id, user)
        if if_match != reviewed.result.version:
            raise PreconditionFailedError(
                detail="The composition or repository changed. Compare again."
            )
        checkpoint = await apply(current, tenant_id, id, user, reviewed, body.choices)
        await current.commit()
        response.headers["Cache-Control"] = "private, no-store"
        return Accepted(checkpoint_id=checkpoint)


@router.get("/checkpoints/{checkpoint_id}")
async def manuscript_update_checkpoint(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    checkpoint_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> dict[str, Any]:
    await author(session, tenant_id, user)
    await entry(session, tenant_id, id, user)
    row = await session.scalar(
        select(ManuscriptRepositoryUpdate).where(
            ManuscriptRepositoryUpdate.tenant_id == tenant_id,
            ManuscriptRepositoryUpdate.entry_id == id,
            ManuscriptRepositoryUpdate.id == checkpoint_id,
        )
    )
    if row is None:
        raise InvalidRepositoryUpdateError(detail="This update checkpoint is not available.")
    for entry_id in row.checkpoint["entries"]:
        await entry(session, tenant_id, uuid.UUID(entry_id), user)
    for information_id in row.checkpoint["information"]:
        info = await session.scalar(
            select(Information).where(
                Information.tenant_id == tenant_id, Information.id == uuid.UUID(information_id)
            )
        )
        if info is None:
            raise InvalidRepositoryUpdateError(
                detail="This checkpoint's writing is no longer available."
            )
        await authorize_information_edit(
            session, tenant_id=tenant_id, user=user, information=info, history_read=True
        )
    response.headers["Cache-Control"] = "private, no-store"
    return row.checkpoint
