"""GET /tenants/{t}/entities/export (ADR 0262, RFC 0039 W3): every entry of a tenant, in cursor
pages, for a client that holds the tenant on its device.

Its own router and registered before `entities`, since `/{entity_id}` there would take "export".
Open to who may open the list (`require_tenant_participant`); the information of each entry is
filtered with the same rule as `GET .../entities/{id}` (`visible_information_clause`, ADR 0109).
"""

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import ColumnElement, select
from sqlalchemy.orm import selectinload

from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
)
from lorenzo_api.entity_access import entity_id_among
from lorenzo_api.entity_export import (
    decode_cursor,
    encode_cursor,
    etag_header,
    export_token,
    matches_if_none_match,
    read_revision,
)
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.exceptions import ExportChangedError
from lorenzo_api.information_visibility import (
    resolve_information_visibility,
    visible_information_clause,
)
from lorenzo_api.models import (
    Entity,
    EntityStat,
    EntityStatGroup,
    Information,
    Payload,
    PayloadDocument,
    PayloadPicture,
)
from lorenzo_api.routers.entities import kinds_of, parents_of
from lorenzo_api.schemas.entities import InformationOut
from lorenzo_api.schemas.entity_export import (
    EntityExportOut,
    EntityExportPage,
    EntityExportStatOut,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}/entities",
    tags=["entities"],
    dependencies=[Depends(get_tenant_or_404)],
)

DEFAULT_PAGE_SIZE = 200
MAX_PAGE_SIZE = 500


async def _information_of(
    session: SessionDep,
    request: Request,
    *,
    tenant_id: uuid.UUID,
    entity_ids: Sequence[uuid.UUID],
    visible: ColumnElement[bool],
) -> dict[uuid.UUID, list[InformationOut]]:
    """The information of each entry that the caller may read, in `order`. Picture and document
    bytes are never loaded: their payloads carry a `url`."""
    found: dict[uuid.UUID, list[InformationOut]] = {entity_id: [] for entity_id in entity_ids}
    if not entity_ids:
        return found
    stmt = (
        select(Information)
        .where(
            Information.tenant_id == tenant_id,
            entity_id_among(Information.entity_id, entity_ids),
            visible,
        )
        .order_by(Information.entity_id, Information.order)
        .options(
            selectinload(Information.author),
            selectinload(Information.payloads).selectinload(Payload.description),
            selectinload(Information.payloads).selectinload(Payload.number),
            selectinload(Information.payloads)
            .selectinload(Payload.picture)
            .load_only(PayloadPicture.payload_id, PayloadPicture.file_type),
            selectinload(Information.payloads)
            .selectinload(Payload.document)
            .load_only(
                PayloadDocument.payload_id, PayloadDocument.filename, PayloadDocument.file_type
            ),
        )
    )
    for information in (await session.scalars(stmt)).all():
        found[information.entity_id].append(InformationOut.from_information(information, request))
    return found


def _stat_value(stat: EntityStat) -> int | str | float | bool:
    for value in (stat.value_int, stat.value_text, stat.value_float, stat.value_bool):
        if value is not None:
            return value
    raise ValueError(f"Stat {stat.stat_definition_id} of {stat.entity_id} holds no value")


@router.get("/export")
async def export_entities(
    tenant_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    cursor: Annotated[
        str | None,
        Query(description="The `next_cursor` of the previous page; leave out for the first."),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    if_none_match: Annotated[str | None, Header()] = None,
) -> EntityExportPage:
    """Every entry of the tenant, `limit` at a time in id order, each with what a mirror is
    written back from (ADR 0262): kinds, link name, parents, stat groups, the values it holds
    itself by definition id, and the information the caller may read.

    The `ETag` is the tenant's revision joined to a digest of what the caller may read. On the
    first page `If-None-Match` with that token answers `304`: nothing the mirror holds has
    changed. A cursor remembers the token its export began with; if the token has moved by the
    time it is used the answer is `409` and the export starts again. Responses are gzipped when
    the client asks for it.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    revision = await read_revision(session, tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    token = export_token(revision, visibility)
    headers = {"ETag": etag_header(token), "Cache-Control": "private, no-cache"}

    after: uuid.UUID | None = None
    if cursor is not None:
        began_with, after = decode_cursor(cursor)
        if began_with != token:
            raise ExportChangedError(
                detail="The repository changed since this export began; start again"
            )
    elif matches_if_none_match(if_none_match, token):
        return Response(status_code=304, headers=headers)  # type: ignore[return-value]
    response.headers.update(headers)

    stmt = (
        select(Entity)
        .where(Entity.tenant_id == tenant_id, visible_entry_clause(visibility, Entity.id))
        .order_by(Entity.id)
        .limit(limit + 1)
        .options(selectinload(Entity.slug))
    )
    if after is not None:
        stmt = stmt.where(Entity.id > after)
    rows = list((await session.scalars(stmt)).all())
    entities, more = rows[:limit], len(rows) > limit
    ids = [entity.id for entity in entities]

    kinds = await kinds_of(session, ids)
    parents = await parents_of(session, ids, visibility)
    information = await _information_of(
        session,
        request,
        tenant_id=tenant_id,
        entity_ids=ids,
        visible=visible_information_clause(visibility),
    )
    stats: dict[uuid.UUID, list[EntityExportStatOut]] = {entity_id: [] for entity_id in ids}
    groups: dict[uuid.UUID, list[uuid.UUID]] = {entity_id: [] for entity_id in ids}
    if ids:
        own = select(EntityStat).where(entity_id_among(EntityStat.entity_id, ids))
        for stat in (await session.scalars(own.order_by(EntityStat.stat_definition_id))).all():
            stats[stat.entity_id].append(
                EntityExportStatOut(
                    stat_definition_id=stat.stat_definition_id,
                    value=_stat_value(stat),
                    updated_at=stat.updated_at,
                )
            )
        linked = select(EntityStatGroup.entity_id, EntityStatGroup.stat_group_id).where(
            entity_id_among(EntityStatGroup.entity_id, ids)
        )
        for entity_id, group_id in (
            await session.execute(linked.order_by(EntityStatGroup.stat_group_id))
        ).tuples():
            groups[entity_id].append(group_id)

    return EntityExportPage(
        revision=token,
        items=[
            EntityExportOut(
                id=entity.id,
                name=entity.name,
                slug=entity.slug.slug if entity.slug is not None else None,
                kinds=kinds[entity.id],
                parent_ids=parents[entity.id],
                stat_group_ids=groups[entity.id],
                stats=stats[entity.id],
                information=information[entity.id],
                created_at=entity.created_at,
                updated_at=entity.updated_at,
            )
            for entity in entities
        ],
        next_cursor=encode_cursor(token, entities[-1].id) if more else None,
    )
