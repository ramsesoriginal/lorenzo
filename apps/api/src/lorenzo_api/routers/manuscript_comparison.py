"""Permission-gated saved direct manuscript comparison (ADR 0398)."""

import hashlib
import json
import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.campaign_access import is_tenant_author
from lorenzo_api.dependencies import CurrentUser, SessionDep, get_tenant_or_404
from lorenzo_api.description_payloads import write_description
from lorenzo_api.exceptions import (
    InformationManagementForbiddenError,
    InvalidRepositoryUpdateError,
    PayloadPreconditionRequiredError,
    PreconditionFailedError,
    RepositoryNotFoundError,
)
from lorenzo_api.information_bundles import touch_bundle
from lorenzo_api.manuscript_comparison import (
    bundle,
    chapter_contexts,
    standalone,
    state,
    update_reason,
)
from lorenzo_api.models import Payload, RepositoryCopy, RepositoryCopyLinkEntity
from lorenzo_api.repository_access import reading_repository
from lorenzo_api.repository_content import load_content
from lorenzo_api.repository_upstream import load_upstream
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.information import locked_information
from lorenzo_api.routers.writing import author, entry, manuscript_payloads

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
    version: str | None = None
    update_allowed: bool = False
    update_reason: str | None = None
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
    # Read identity maps only, not every retained manuscript's prose baseline.
    links = await session.execute(
        select(
            RepositoryCopyLinkEntity.entity_id,
            RepositoryCopyLinkEntity.source_id,
            RepositoryCopyLinkEntity.manuscript_baseline["identities"],
        ).where(
            RepositoryCopyLinkEntity.tenant_id == tenant_id,
            RepositoryCopyLinkEntity.source_tenant_id == link.source_tenant_id,
            RepositoryCopyLinkEntity.entity_id.is_not(None),
        )
    )
    identities = {}
    for local_id, source_id, payload_ids in links:
        identities[str(local_id)] = str(source_id)
        identities.update(payload_ids or {})
    local_context = chapter_contexts(local_content, identities, entries={id}).get(id)
    upstream_context = chapter_contexts(source.content, entries={link.source_id}).get(
        link.source_id
    )
    unchanged_composition = (
        saved.get("composition") is not None
        and saved["composition"] == local_context == upstream_context
    )
    reason = update_reason(
        saved["bundle"],
        local,
        upstream,
        unchanged_composition
        or (
            saved.get("composition") is None
            and standalone(local_content, id)
            and standalone(source.content, link.source_id)
        ),
    )
    version = (
        '"'
        + hashlib.sha256(
            json.dumps(
                [saved, local, upstream, reason, local_context, upstream_context],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        + '"'
    )
    response.headers["ETag"] = version
    return ManuscriptComparison(
        version=version,
        update_allowed=reason is None,
        update_reason=reason,
        state=state(saved["bundle"], local, upstream),
        repository_name=copy.repository_name if copy else None,
        base=saved["bundle"],
        local=local,
        upstream=upstream,
    )


class ManuscriptUpdateChoice(BaseModel):
    choice: Literal["local", "upstream"]


@router.post("", status_code=204)
async def accept_manuscript_update(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    body: ManuscriptUpdateChoice,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    if if_match is None:
        raise PayloadPreconditionRequiredError(
            detail="Compare the manuscript and send its ETag as If-Match."
        )
    await author(session, tenant_id, user)
    await entry(session, tenant_id, id, user, lock=True)
    link = await session.scalar(
        select(RepositoryCopyLinkEntity)
        .where(
            RepositoryCopyLinkEntity.tenant_id == tenant_id,
            RepositoryCopyLinkEntity.entity_id == id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if link is None:
        raise InvalidRepositoryUpdateError(detail="This manuscript has no copy baseline.")
    comparison = await compare_manuscript(tenant_id, id, Response(), session, user)
    if if_match != comparison.version:
        raise PreconditionFailedError(detail="The manuscript or repository changed. Compare again.")
    if not comparison.update_allowed or comparison.upstream is None:
        raise InvalidRepositoryUpdateError(
            detail=comparison.update_reason or "This manuscript cannot take text updates."
        )
    saved = link.manuscript_baseline
    assert saved is not None
    info = await locked_information(session, uuid.UUID(saved["information_id"]), tenant_id)
    await authorize_information_edit(session, tenant_id=tenant_id, user=user, information=info)
    if body.choice == "upstream":
        identities = {origin: uuid.UUID(local) for local, origin in saved["identities"].items()}
        for source_payload in comparison.upstream["payloads"]:
            if source_payload["kind"] != "description":
                continue
            payload = await session.scalar(
                select(Payload)
                .where(
                    Payload.id == identities[source_payload["id"]],
                    Payload.tenant_id == tenant_id,
                    Payload.information_id == info.id,
                )
                .options(selectinload(Payload.description))
            )
            assert payload is not None
            await write_description(
                session,
                payload=payload,
                content=source_payload["fields"]["content"],
                locale=source_payload["fields"]["locale"],
            )
        info.title = comparison.upstream["title"]
        touch_bundle(info)
    link.manuscript_baseline = {**saved, "bundle": comparison.upstream}
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="manuscript.repository_updated",
        target_type="entity",
        target_id=id,
        detail=f"choice={body.choice};repository_id={link.source_tenant_id}",
    )
    await session.commit()
