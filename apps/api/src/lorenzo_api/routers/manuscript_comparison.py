"""Permission-gated saved direct manuscript comparison (ADR 0398)."""

import uuid
from typing import Any, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select

from lorenzo_api.campaign_access import is_tenant_author
from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_or_404
from lorenzo_api.exceptions import InformationManagementForbiddenError, RepositoryNotFoundError
from lorenzo_api.manuscript_comparison import bundle, state
from lorenzo_api.models import RepositoryCopy, RepositoryCopyLinkEntity
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import load_content
from lorenzo_api.repository_upstream import load_upstream
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.writing import entry, manuscript_payloads

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing/entries/{id}/repository-comparison",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class ManuscriptComparison(BaseModel):
    state: Literal[
        "not_copied",
        "no_baseline",
        "local_unavailable",
        "unchanged",
        "local",
        "upstream",
        "matching",
        "conflict",
    ]
    repository_name: str | None = None
    base: dict[str, Any] | None = None
    local: dict[str, Any] | None = None
    upstream: dict[str, Any] | None = None


@router.get("")
async def compare_manuscript(
    tenant_id: uuid.UUID, id: uuid.UUID, response: Response, session: SessionDep, user: CurrentUser
) -> ManuscriptComparison:
    await entry(session, tenant_id, id, user)
    if not await is_tenant_author(session, tenant_id=tenant_id, user_id=user.id):
        raise InformationManagementForbiddenError(
            detail="Only Authors can compare copied manuscripts."
        )
    response.headers["Cache-Control"] = "private, no-store"
    link = await session.scalar(
        select(RepositoryCopyLinkEntity).where(
            RepositoryCopyLinkEntity.tenant_id == tenant_id,
            RepositoryCopyLinkEntity.entity_id == id,
        )
    )
    if link is None:
        return ManuscriptComparison(state="not_copied")
    info, _ = await manuscript_payloads(session, tenant_id, id, lock=True)
    if info is None:
        return ManuscriptComparison(state="local_unavailable")
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=info, history_read=True
    )
    saved = link.manuscript_baseline
    if saved is None or saved.get("format") != 1:
        return ManuscriptComparison(state="no_baseline")
    if saved["information_id"] != str(info.id):
        return ManuscriptComparison(state="local_unavailable")
    copy = await session.get(RepositoryCopy, (tenant_id, link.source_tenant_id))
    async with reading_repository(session, link.source_tenant_id) as allowed:
        if not allowed:
            raise RepositoryNotFoundError()
        source = await load_upstream(session, link.source_tenant_id)
        upstream = bundle(source.content, link.source_id)
    local_content = await load_content(session, tenant_id)
    local = bundle(local_content, id, saved["identities"])
    if local is None:
        return ManuscriptComparison(state="local_unavailable")
    return ManuscriptComparison(
        state=state(saved["bundle"], local, upstream),
        repository_name=copy.repository_name if copy else None,
        base=saved["bundle"],
        local=local,
        upstream=upstream,
    )
