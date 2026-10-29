"""Carrier manuscripts and ordered references, separate from composition (ADR 0379)."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from lorenzo_api.client_ids import existing_in_tenant, insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_parents import replace_parents
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    EntityNotFoundError,
    ManuscriptMoveConflictError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    Carrier,
    CarrierCoverage,
    Chapter,
    Edition,
    Entity,
    Information,
    Payload,
    PayloadDescription,
    PayloadPicture,
    Scene,
    SceneTelling,
)
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.manuscript_moves import require_version
from lorenzo_api.routers.story_sessions import create_entry
from lorenzo_api.routers.writing import (
    Element,
    NewManuscript,
    WritingEntry,
    author,
    entry,
    manuscript_payloads,
    result,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


async def carrier_entry(
    session: SessionDep, tenant: uuid.UUID, id: uuid.UUID, user: CurrentUser, *, lock: bool = False
) -> Entity:
    row = await entry(session, tenant, id, user, lock=lock)
    if not await session.get(Carrier, id):
        raise EntityNotFoundError(detail="No such Carrier.")
    return row


@router.post("/carriers", status_code=201)
async def create_carrier(
    tenant_id: uuid.UUID,
    body: NewManuscript,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> WritingEntry:
    await author(session, tenant_id, user)
    old = await existing_in_tenant(session, Entity, body.id, tenant_id)
    if old:
        if (
            old.created_by != user.id
            or old.name != body.name
            or not await session.get(Carrier, body.id)
        ):
            raise ClientIdUnavailableError(detail="That creation id is already in use.")
        response.status_code = 200
    else:
        await create_entry(session, tenant_id, user, body.id, body.name)
        session.add(Carrier(entity_id=body.id, tenant_id=tenant_id))
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, body.id, user, response)


async def coverage_rows(
    session: SessionDep, tenant: uuid.UUID, id: uuid.UUID
) -> list[CarrierCoverage]:
    return list(
        await session.scalars(
            select(CarrierCoverage)
            .where(CarrierCoverage.tenant_id == tenant, CarrierCoverage.carrier_id == id)
            .order_by(CarrierCoverage.position, CarrierCoverage.id)
        )
    )


async def target_element(
    session: SessionDep, tenant: uuid.UUID, row: CarrierCoverage, user: CurrentUser
) -> Element | None:
    target = row.target_entity_id
    if row.target_payload_id:
        if not await session.get(
            PayloadDescription, row.target_payload_id
        ) and not await session.get(PayloadPicture, row.target_payload_id):
            return None
        info = await session.scalar(
            select(Information)
            .join(Payload, Payload.information_id == Information.id)
            .where(
                Payload.id == row.target_payload_id,
                Information.tenant_id == tenant,
                Information.type == "manuscript",
            )
            .options(selectinload(Information.knowledge_links))
        )
        if not info:
            return None
        vis = await resolve_information_visibility(session, tenant_id=tenant, user_id=user.id)
        if not vis.can_see(info):
            return None
        target = info.entity_id
    if target is None:
        return None
    try:
        entity = await entry(session, tenant, target, user)
    except EntityNotFoundError:
        return None
    if not any(
        [
            await session.get(model, target) is not None
            for model in (Edition, Chapter, Scene, SceneTelling)
        ]
    ):
        return None
    return Element(
        id=row.id,
        kind="coverage",
        name=entity.name,
        target_id=target,
        payload_id=row.target_payload_id,
    )


async def covered_elements(
    session: SessionDep, tenant: uuid.UUID, id: uuid.UUID, user: CurrentUser, own: list[Element]
) -> list[Element]:
    rows = await coverage_rows(session, tenant, id)
    targets = {row.id: await target_element(session, tenant, row, user) for row in rows}
    elements = []
    # Missing local anchors (for example after an imported update) follow the direct prose.
    own_ids = {element.id for element in own}
    for anchor in [*own, None]:
        for row in rows:
            effective_anchor = row.before_payload_id if row.before_payload_id in own_ids else None
            if effective_anchor == (anchor.id if anchor else None) and targets[row.id]:
                elements.append(targets[row.id])
        if anchor:
            elements.append(anchor)
    return [element for element in elements if element is not None]


class CoverageElement(BaseModel):
    id: uuid.UUID
    target_entity_id: uuid.UUID | None = None
    target_payload_id: uuid.UUID | None = None


class CoverageOrder(BaseModel):
    elements: list[CoverageElement] = Field(max_length=10000)


@router.put("/carriers/{id}/coverage")
async def arrange_coverage(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    body: CoverageOrder,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> WritingEntry:
    await author(session, tenant_id, user)
    source = await carrier_entry(session, tenant_id, id, user, lock=True)
    info, payloads = await manuscript_payloads(session, tenant_id, id, lock=True)
    if info:
        await authorize_information_edit(session, tenant_id=tenant_id, user=user, information=info)
    current = await result(session, tenant_id, id, user, response)
    rows = await coverage_rows(session, tenant_id, id)
    own = {p.id for p in payloads}
    if {el.id for el in current.elements} != own | {row.id for row in rows}:
        raise ManuscriptMoveConflictError(
            detail="The entire Carrier outline must be readable to arrange it."
        )
    requested = body.elements
    if len({el.id for el in requested}) != len(requested):
        raise ManuscriptMoveConflictError(detail="Each outline occurrence needs its own identity.")
    if {el.id for el in requested if not el.target_entity_id and not el.target_payload_id} != own:
        raise ManuscriptMoveConflictError(
            detail="Keep all direct text and pictures in this outline."
        )
    old = {row.id: row for row in rows}
    new_rows = []
    anchor = None
    for position, el in reversed(list(enumerate(requested))):
        if el.id in own:
            if el.target_entity_id or el.target_payload_id:
                raise ManuscriptMoveConflictError(
                    detail="A text block cannot also be a coverage reference."
                )
            anchor = el.id
            continue
        if bool(el.target_entity_id) == bool(el.target_payload_id):
            raise ManuscriptMoveConflictError(
                detail="Choose whole writing or one text or picture block."
            )
        known = await existing_in_tenant(session, CarrierCoverage, el.id, tenant_id)
        if known and (
            known.carrier_id != id
            or known.target_entity_id != el.target_entity_id
            or known.target_payload_id != el.target_payload_id
        ):
            raise ClientIdUnavailableError(detail="That coverage identity is already in use.")
        row = CarrierCoverage(
            id=el.id,
            tenant_id=tenant_id,
            carrier_id=id,
            target_entity_id=el.target_entity_id,
            target_payload_id=el.target_payload_id,
            before_payload_id=anchor,
            position=position,
        )
        if await target_element(session, tenant_id, row, user) is None:
            raise EntityNotFoundError(detail="That writing is not available for coverage.")
        new_rows.append(row)
    unchanged = [el.id for el in requested] == [el.id for el in current.elements] and all(
        row.id in old
        and old[row.id].target_entity_id == row.target_entity_id
        and old[row.id].target_payload_id == row.target_payload_id
        for row in new_rows
    )
    if unchanged and if_match is not None:
        return current
    require_version(if_match, current.version)
    await session.execute(delete(CarrierCoverage).where(CarrierCoverage.carrier_id == id))
    for row in new_rows:
        await insert_with_client_id(session, row)
    ordered = [el.id for el in requested if el.id in own]
    floor = min((p.order for p in payloads), default=0) - len(payloads) - 1
    for n, payload in enumerate(payloads):
        payload.order = floor + n
    await session.flush()
    for payload in payloads:
        payload.order = ordered.index(payload.id)
    source.updated_at = datetime.now(UTC)
    source.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, id, user, response)


class CarrierParents(BaseModel):
    parent_ids: list[uuid.UUID]


@router.put("/carriers/{id}/parents")
async def carrier_parents(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    body: CarrierParents,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> WritingEntry:
    await author(session, tenant_id, user)
    row = await carrier_entry(session, tenant_id, id, user, lock=True)
    current = await result(session, tenant_id, id, user, response)
    require_version(if_match, current.version)
    for parent in body.parent_ids:
        await carrier_entry(session, tenant_id, parent, user)
    await replace_parents(
        session, tenant_id=tenant_id, entity=row, parent_ids=body.parent_ids, user_id=user.id
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, id, user, response)
