"""The vocabulary check: one read-only route (ADR 0458, RFC 0055).

At the vocabulary's tier, like the stats it reads: any member of the library reads it. It writes,
records and refuses nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import select

from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_entity_or_404,
)
from lorenzo_api.exceptions import StatDefinitionNotFoundError, VocabularyCheckEntryRequiredError
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import Entity, StatDefinition
from lorenzo_api.routers.entities import (
    KindFilter,
    ParentFilter,
    RecursiveFilter,
    entries_statement,
)
from lorenzo_api.routers.stats import _vocabulary_gate
from lorenzo_api.schemas.vocabulary_check import CheckCode, FindingOut
from lorenzo_api.vocabulary_check import (
    Finding,
    scan_entries,
    tie_findings,
    vocabulary_findings,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["vocabulary-check"],
    dependencies=[Depends(_vocabulary_gate)],
)

ALL_CODES: tuple[CheckCode, ...] = (
    "computed-outside-scale",
    "above-hint",
    "formula-chain-depth",
    "unset-input",
    "own-value-shadows-formula",
    "tie",
)


def _out(finding: Finding) -> FindingOut:
    return FindingOut(
        code=finding.code,
        severity=finding.severity,
        entry_id=finding.entry_id,
        stat_definition_id=finding.stat_definition_id,
        message=finding.message,
        details=finding.details,
    )


@router.get("/vocabulary-check")
async def check_vocabulary(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    code: Annotated[
        list[CheckCode] | None,
        Query(description="Only these findings (repeatable); all by default."),
    ] = None,
    entry_id: Annotated[uuid.UUID | None, Query(description="Only this entry.")] = None,
    parent_id: ParentFilter = None,
    recursive: RecursiveFilter = False,
    kind: KindFilter = None,
    stat_definition_id: Annotated[uuid.UUID | None, Query(description="Only this stat.")] = None,
) -> Page[FindingOut]:
    """What a library's stats get wrong without saying so, without refusing, writing or recording
    anything (ADR 0458, RFC 0055). `items` are the findings of a page of the entries scanned (the
    entries and their order are `GET /entities`'s, with the same `kind`, `parent_id` and
    `recursive`, or the one `entry_id`); `total` and `pages` count entries, not findings. An entry
    the caller cannot read is not scanned. The findings about the library's formulas, which are
    no entry's, come on the first page, and only when no entry is asked for. `code` narrows the
    findings, `stat_definition_id` the stat (404 for one that is not the library's). `tie` is read
    for one entry: it is in the default set only with `entry_id`, and a `code` that names it
    without one is a 422."""
    if code and "tie" in code and entry_id is None:
        raise VocabularyCheckEntryRequiredError(
            detail="A tie is read for one entry: give entry_id, or leave tie out of code."
        )
    # `tie` is for one entry, so the default set has it only when an entry is asked for.
    codes = (
        list(dict.fromkeys(code))
        if code
        else [c for c in ALL_CODES if c != "tie" or entry_id is not None]
    )
    if stat_definition_id is not None and not await session.scalar(
        select(StatDefinition.id).where(
            StatDefinition.id == stat_definition_id, StatDefinition.tenant_id == tenant_id
        )
    ):
        raise StatDefinitionNotFoundError(
            detail=f"No stat definition {stat_definition_id} in tenant {tenant_id}"
        )
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    stmt = await entries_statement(
        session,
        tenant_id,
        visibility,
        q=None,
        kind=kind,
        parent_id=parent_id,
        recursive=recursive,
    )
    if entry_id is not None:
        await get_entity_or_404(session, entry_id, tenant_id)
        stmt = stmt.where(Entity.id == entry_id)
    about_the_library = entry_id is None and parent_id is None and not kind

    async def scan(entities: Sequence[Entity]) -> list[FindingOut]:
        found = await scan_entries(
            session,
            tenant_id=tenant_id,
            entities=entities,
            visibility=visibility,
            codes=codes,
            stat_definition_id=stat_definition_id,
        )
        if "tie" in codes and entry_id is not None:
            for entity in entities:
                found += await tie_findings(
                    session,
                    tenant_id=tenant_id,
                    entity=entity,
                    visibility=visibility,
                    stat_definition_id=stat_definition_id,
                )
        if about_the_library and params.page == 1:
            found += await vocabulary_findings(
                session,
                tenant_id=tenant_id,
                codes=codes,
                stat_definition_id=stat_definition_id,
            )
        return [_out(f) for f in found]

    page: Page[FindingOut] = await apaginate(session, stmt, params, transformer=scan)
    return page
