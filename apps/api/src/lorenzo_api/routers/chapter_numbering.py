"""Conditional numbering settings and authorized labels (ADR 0380)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel
from sqlalchemy import select

from lorenzo_api.chapter_numbering import NumberingSettings, projection, settings_version
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.exceptions import (
    EventOrderPreconditionRequiredError,
    InvalidKindRequestError,
    PreconditionFailedError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.manuscript_redirects import require_unjoined
from lorenzo_api.models import Chapter, Edition, Entity, ManuscriptNumbering, ManuscriptPlacement
from lorenzo_api.routers.writing import author, entry

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class ChapterNumberingOut(BaseModel):
    settings: NumberingSettings
    version: str
    root_id: uuid.UUID
    labels: dict[uuid.UUID, str]


async def numbering_context(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID, user: CurrentUser
) -> tuple[uuid.UUID, set[uuid.UUID], list[ManuscriptPlacement]]:
    await entry(session, tenant_id, id, user)
    if not await session.get(Chapter, id) and not await session.get(Edition, id):
        raise InvalidKindRequestError(detail="Choose an Edition or Chapter for numbering.")
    vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
    visible = set(
        await session.scalars(
            select(Entity.id).where(
                Entity.tenant_id == tenant_id, visible_entry_clause(vis, Entity.id)
            )
        )
    )
    links = list(
        await session.scalars(
            select(ManuscriptPlacement).where(ManuscriptPlacement.tenant_id == tenant_id)
        )
    )
    parents = {p.child_entity_id: p.parent_entity_id for p in links}
    root = id
    seen = {id}
    while root in parents and parents[root] in visible and parents[root] not in seen:
        root = parents[root]
        seen.add(root)
    return root, visible, links


async def read_numbering(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID, user: CurrentUser, response: Response
) -> ChapterNumberingOut:
    root, visible, links = await numbering_context(session, tenant_id, id, user)
    row = await session.get(ManuscriptNumbering, id)
    settings = NumberingSettings.model_validate(row.settings) if row else NumberingSettings()
    version = settings_version(settings)
    response.headers["ETag"] = version
    response.headers["Cache-Control"] = "private, no-store"
    return ChapterNumberingOut(
        settings=settings,
        version=version,
        root_id=root,
        labels=await projection(session, tenant_id, root, visible, links),
    )


@router.get("/entries/{id}/numbering")
async def get_numbering(
    tenant_id: uuid.UUID, id: uuid.UUID, response: Response, session: SessionDep, user: CurrentUser
) -> ChapterNumberingOut:
    return await read_numbering(session, tenant_id, id, user, response)


@router.put("/entries/{id}/numbering")
async def put_numbering(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    body: NumberingSettings,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ChapterNumberingOut:
    await author(session, tenant_id, user)
    await require_unjoined(session, id)
    current = await read_numbering(session, tenant_id, id, user, response)
    if not if_match:
        raise EventOrderPreconditionRequiredError(
            detail="Read the numbering settings before changing them."
        )
    if body == current.settings:
        return current
    if if_match != current.version:
        raise PreconditionFailedError(
            detail="The numbering settings changed. Read them again before saving."
        )
    row = await session.get(ManuscriptNumbering, id)
    if row:
        row.settings = body.model_dump(mode="json")
    else:
        session.add(
            ManuscriptNumbering(
                entity_id=id, tenant_id=tenant_id, settings=body.model_dump(mode="json")
            )
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await read_numbering(session, tenant_id, id, user, response)
