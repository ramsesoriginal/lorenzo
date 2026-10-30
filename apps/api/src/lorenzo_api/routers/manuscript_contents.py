"""Conditional presentation settings and structural contents (ADR 0381)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    EventOrderPreconditionRequiredError,
    InvalidKindRequestError,
    PreconditionFailedError,
)
from lorenzo_api.manuscript_contents import (
    ContentsRow,
    ContentsSettings,
    contents_tree,
    contents_version,
    visible_contents,
)
from lorenzo_api.manuscript_redirects import require_unjoined
from lorenzo_api.models import Edition, ManuscriptContents
from lorenzo_api.routers.chapter_numbering import numbering_context
from lorenzo_api.routers.writing import author

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class ManuscriptContentsOut(BaseModel):
    settings: ContentsSettings
    version: str
    root_id: uuid.UUID
    rows: list[ContentsRow]
    displayed: bool
    root_enabled: bool
    contents_chapters: list[uuid.UUID]


async def read_contents(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID, user: CurrentUser, response: Response
) -> ManuscriptContentsOut:
    root, allowed, placements = await numbering_context(session, tenant_id, id, user)
    settings, rows = await contents_tree(session, tenant_id, root, allowed, placements)
    own = settings.get(id, ContentsSettings())
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["ETag"] = contents_version(own)
    return ManuscriptContentsOut(
        settings=own,
        version=contents_version(own),
        root_id=root,
        rows=rows,
        root_enabled=settings.get(root, ContentsSettings()).enabled,
        contents_chapters=[
            entry_id for entry_id, value in settings.items() if value.role == "contents"
        ],
        displayed=visible_contents(root, id, settings, rows) is not None,
    )


@router.get("/entries/{id}/contents")
async def get_contents(
    tenant_id: uuid.UUID, id: uuid.UUID, response: Response, session: SessionDep, user: CurrentUser
) -> ManuscriptContentsOut:
    return await read_contents(session, tenant_id, id, user, response)


@router.put("/entries/{id}/contents")
async def put_contents(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    body: ContentsSettings,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ManuscriptContentsOut:
    await author(session, tenant_id, user)
    await require_unjoined(session, id)
    current = await read_contents(session, tenant_id, id, user, response)
    if await session.get(Edition, id) and body.role != "chapter":
        raise InvalidKindRequestError(
            detail="Special Chapter roles belong to Chapters, not Editions."
        )
    if not if_match:
        raise EventOrderPreconditionRequiredError(
            detail="Read the contents settings before changing them."
        )
    if body == current.settings:
        return current
    if if_match != current.version:
        raise PreconditionFailedError(
            detail="The contents settings changed. Read them again before saving."
        )
    row = await session.get(ManuscriptContents, id)
    if row:
        row.settings = body.model_dump(mode="json")
    else:
        session.add(
            ManuscriptContents(
                entity_id=id, tenant_id=tenant_id, settings=body.model_dump(mode="json")
            )
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await read_contents(session, tenant_id, id, user, response)
