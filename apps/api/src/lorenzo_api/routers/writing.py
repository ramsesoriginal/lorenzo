"""Book creation and conditional manuscript composition (ADR 0341)."""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from lorenzo_api.campaign_access import is_tenant_author
from lorenzo_api.client_ids import existing_in_tenant
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    EntityNotFoundError,
    EventOrderPreconditionRequiredError,
    InformationManagementForbiddenError,
    InvalidKindRequestError,
    PreconditionFailedError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.manuscript_redirects import require_unjoined
from lorenzo_api.models import (
    Being,
    Book,
    Chapter,
    Edition,
    Entity,
    Information,
    ManuscriptPlacement,
    ManuscriptRedirect,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    Scene,
    SceneTelling,
    Tenant,
    WritingBiography,
)
from lorenzo_api.routers.story_sessions import create_entry

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class NewManuscript(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str = Field(min_length=1, max_length=300)


class NewBook(NewManuscript):
    first_edition_id: uuid.UUID = Field(default_factory=uuid.uuid4)


class NewEdition(NewManuscript):
    source_edition_id: uuid.UUID


class Element(BaseModel):
    id: uuid.UUID
    kind: Literal["payload", "chapter", "scene_telling"]
    name: str | None = None


class ManuscriptSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str


class JoinedDestination(BaseModel):
    id: uuid.UUID
    name: str
    element_id: uuid.UUID


class WritingEntry(BaseModel):
    id: uuid.UUID
    name: str
    kind: Literal["book", "edition", "chapter", "scene", "scene_telling", "biography"]
    book_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    scene_id: uuid.UUID | None = None
    viewpoint_id: uuid.UUID | None = None
    manuscript_source_id: uuid.UUID | None = None
    uses_scene_manuscript: bool = False
    joined: bool = False
    joined_destination: JoinedDestination | None = None
    editions: list[ManuscriptSummary] = []
    elements: list[Element] = []
    version: str


class Composition(BaseModel):
    elements: list[uuid.UUID]


async def author(session: SessionDep, tenant_id: uuid.UUID, user: CurrentUser) -> None:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    if not await is_tenant_author(session, tenant_id=tenant_id, user_id=user.id):
        raise InformationManagementForbiddenError(
            detail="Only library Authors can arrange manuscripts."
        )
    # Serialize graph mutations, including edition duplication, before taking entry locks.
    await session.scalar(select(Tenant.id).where(Tenant.id == tenant_id).with_for_update())


async def entry(
    session: SessionDep,
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    user: CurrentUser,
    *,
    lock: bool = False,
) -> Entity:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, tenant_id=tenant_id, entity_id=id, user_id=user.id)
    query = select(Entity).where(Entity.id == id, Entity.tenant_id == tenant_id)
    row = await session.scalar(query.with_for_update() if lock else query)
    if row is None or row.tenant_id != tenant_id:
        raise EntityNotFoundError(detail="No such manuscript in this library.")
    return row


async def manuscript_payloads(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID, *, lock: bool = False
) -> tuple[Information | None, list[Payload]]:
    if lock:
        await require_unjoined(session, id)
    stmt = (
        select(Information)
        .where(
            Information.tenant_id == tenant_id,
            Information.entity_id == id,
            Information.type == "manuscript",
        )
        .options(selectinload(Information.knowledge_links))
    )
    info = await session.scalar(stmt.with_for_update() if lock else stmt)
    rows = (
        list(
            await session.scalars(
                select(Payload)
                .where(Payload.information_id == info.id)
                .order_by(Payload.order, Payload.id)
            )
        )
        if info
        else []
    )
    return info, rows


async def children(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID
) -> list[ManuscriptPlacement]:
    return list(
        await session.scalars(
            select(ManuscriptPlacement)
            .where(
                ManuscriptPlacement.tenant_id == tenant_id,
                ManuscriptPlacement.parent_entity_id == id,
            )
            .order_by(ManuscriptPlacement.position, ManuscriptPlacement.child_entity_id)
        )
    )


async def result(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID, user: CurrentUser, response: Response
) -> WritingEntry:
    row = await entry(session, tenant_id, id, user)
    kind: Literal["book", "edition", "chapter", "scene", "scene_telling", "biography"]
    if await session.get(Book, id):
        kind = "book"
    elif await session.get(Edition, id):
        kind = "edition"
    elif await session.get(Chapter, id):
        kind = "chapter"
    elif await session.get(SceneTelling, id):
        kind = "scene_telling"
    elif await session.get(Scene, id):
        kind = "scene"
    elif await session.get(WritingBiography, id):
        kind = "biography"
    else:
        raise EntityNotFoundError(detail="No such writing entry.")
    vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
    info, payloads = await manuscript_payloads(session, tenant_id, id)
    links = await children(session, tenant_id, id)
    visible = set(
        await session.scalars(
            select(Entity.id).where(
                Entity.tenant_id == tenant_id, visible_entry_clause(vis, Entity.id)
            )
        )
    )
    telling = await session.get(SceneTelling, id)
    source_id = telling.scene_entity_id if telling and telling.uses_scene_manuscript else id
    if source_id in visible:
        info, payloads = await manuscript_payloads(session, tenant_id, source_id)
    else:
        info, payloads = None, []
    token = hashlib.sha256(
        repr(
            (
                row.updated_at,
                (telling.uses_scene_manuscript, telling.viewpoint_entity_id) if telling else None,
                [(p.id, p.updated_at, p.order) for p in payloads if info and vis.can_see(info)],
                [
                    (p.child_entity_id, p.before_payload_id, p.position)
                    for p in links
                    if p.child_entity_id in visible
                ],
            )
        ).encode()
    ).hexdigest()
    version = f'W/"{token}"'
    elements: list[Element] = []

    telling_ids = set(
        await session.scalars(
            select(SceneTelling.entity_id).where(SceneTelling.tenant_id == tenant_id)
        )
    )

    def add_links(anchor: uuid.UUID | None) -> None:
        for link in links:
            if link.before_payload_id == anchor and link.child_entity_id in visible:
                elements.append(
                    Element(
                        id=link.child_entity_id,
                        kind="scene_telling"
                        if telling_ids and link.child_entity_id in telling_ids
                        else "chapter",
                    )
                )

    for p in payloads:
        add_links(p.id)
        if info and vis.can_see(info):
            elements.append(Element(id=p.id, kind="payload"))
    add_links(None)
    for el in elements:
        if el.kind != "payload":
            child = await session.get(Entity, el.id)
            assert child is not None
            el.name = child.name
    edition = await session.get(Edition, id)
    book_id = id if kind == "book" else edition.book_entity_id if edition else None
    editions = []
    if book_id and book_id in visible:
        editions = [
            ManuscriptSummary(id=e.id, name=e.name)
            for e in await session.scalars(
                select(Entity)
                .join(Edition, Edition.entity_id == Entity.id)
                .where(Edition.book_entity_id == book_id, Entity.id.in_(visible))
                .order_by(Entity.created_at, Entity.id)
            )
        ]
    response.headers["ETag"] = version
    response.headers["Cache-Control"] = "private, no-store"
    placement = await session.get(ManuscriptPlacement, id)
    redirect = await session.get(ManuscriptRedirect, id)
    destination = None
    if (
        redirect
        and redirect.destination_id in visible
        and not await session.get(ManuscriptRedirect, redirect.destination_id)
    ):
        target_info, target_payloads = await manuscript_payloads(
            session, tenant_id, redirect.destination_id
        )
        anchor = None
        if (
            target_info
            and vis.can_see(target_info)
            and redirect.payload_id in {p.id for p in target_payloads}
        ):
            anchor = redirect.payload_id
        if redirect.child_id in visible:
            child_link = await session.get(ManuscriptPlacement, redirect.child_id)
            if child_link and child_link.parent_entity_id == redirect.destination_id:
                anchor = redirect.child_id
        if anchor:
            target = await session.get(Entity, redirect.destination_id)
            assert target is not None
            destination = JoinedDestination(id=target.id, name=target.name, element_id=anchor)
    return WritingEntry(
        joined=redirect is not None,
        joined_destination=destination,
        scene_id=telling.scene_entity_id
        if telling and telling.scene_entity_id in visible
        else None,
        viewpoint_id=telling.viewpoint_entity_id
        if telling and telling.viewpoint_entity_id in visible
        else None,
        manuscript_source_id=source_id if source_id in visible else None,
        uses_scene_manuscript=bool(telling and telling.uses_scene_manuscript),
        parent_id=placement.parent_entity_id
        if placement and placement.parent_entity_id in visible
        else None,
        id=id,
        name=row.name,
        kind=kind,
        book_id=book_id if book_id in visible else None,
        editions=editions,
        elements=elements,
        version=version,
    )


@router.get("/entries/{id}")
async def read_entry(
    tenant_id: uuid.UUID, id: uuid.UUID, response: Response, session: SessionDep, user: CurrentUser
) -> WritingEntry:
    return await result(session, tenant_id, id, user, response)


@router.post("/books", status_code=201)
async def create_book(
    tenant_id: uuid.UUID, body: NewBook, response: Response, session: SessionDep, user: CurrentUser
) -> WritingEntry:
    await author(session, tenant_id, user)
    old = await existing_in_tenant(session, Entity, body.id, tenant_id)
    if old:
        first = await session.get(Edition, body.first_edition_id)
        if (
            old.created_by != user.id
            or old.name != body.name
            or not first
            or first.book_entity_id != body.id
        ):
            raise ClientIdUnavailableError(detail="That creation id is already in use.")
        response.status_code = 200
    else:
        await create_entry(session, tenant_id, user, body.id, body.name)
        session.add(Book(entity_id=body.id, tenant_id=tenant_id))
        await session.flush()
        await create_entry(session, tenant_id, user, body.first_edition_id, body.name)
        session.add(
            Edition(entity_id=body.first_edition_id, tenant_id=tenant_id, book_entity_id=body.id)
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, body.id, user, response)


@router.post("/chapters", status_code=201)
async def create_chapter(
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
            or not await session.get(Chapter, body.id)
        ):
            raise ClientIdUnavailableError(detail="That creation id is already in use.")
        response.status_code = 200
    else:
        await create_entry(session, tenant_id, user, body.id, body.name)
        session.add(Chapter(entity_id=body.id, tenant_id=tenant_id))
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, body.id, user, response)


@router.put("/entries/{id}/composition")
async def arrange(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    body: Composition,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> WritingEntry:
    await author(session, tenant_id, user)
    row = await entry(session, tenant_id, id, user, lock=True)
    if not await session.get(Edition, id) and not await session.get(Chapter, id):
        raise InvalidKindRequestError(detail="Arrange an Edition or Chapter.")
    _, payloads = await manuscript_payloads(session, tenant_id, id, lock=True)
    current = await result(session, tenant_id, id, user, response)
    if if_match is None:
        raise EventOrderPreconditionRequiredError(
            detail="Read the current outline before arranging it."
        )
    if if_match != current.version:
        raise PreconditionFailedError(detail="This manuscript changed. Read its current outline.")
    ids = body.elements
    own = {p.id for p in payloads}
    if len(ids) != len(set(ids)) or not own.issubset(ids):
        raise InvalidKindRequestError(detail="Include each prose and picture element exactly once.")
    wanted = set(ids) - own
    for child_id in wanted:
        await entry(session, tenant_id, child_id, user)
        await require_unjoined(session, child_id)
        if not await session.get(Chapter, child_id) and not await session.get(
            SceneTelling, child_id
        ):
            raise InvalidKindRequestError(
                detail="Only Chapters or Scene tellings can be placed here."
            )
        link = await session.get(ManuscriptPlacement, child_id)
        if link and link.parent_entity_id != id:
            raise InvalidKindRequestError(
                detail="Remove this entry from its current outline first."
            )
        ancestor: uuid.UUID | None = id
        while ancestor is not None:
            if ancestor == child_id:
                raise InvalidKindRequestError(
                    detail="A Chapter cannot contain itself or an ancestor."
                )
            above = await session.get(ManuscriptPlacement, ancestor)
            ancestor = above.parent_entity_id if above else None
    if ids == [el.id for el in current.elements]:
        return current
    # Unique payload positions use a disjoint temporary range before their final order.
    for n, p in enumerate(payloads):
        p.order = -n - 1
    await session.flush()
    by_id = {p.id: p for p in payloads}
    for n, pid in enumerate(x for x in ids if x in own):
        by_id[pid].order = n
    await session.execute(
        delete(ManuscriptPlacement).where(
            ManuscriptPlacement.parent_entity_id == id, ManuscriptPlacement.tenant_id == tenant_id
        )
    )
    anchor = None
    for n, child_id in reversed(list(enumerate(ids))):
        if child_id in own:
            anchor = child_id
        else:
            session.add(
                ManuscriptPlacement(
                    child_entity_id=child_id,
                    parent_entity_id=id,
                    tenant_id=tenant_id,
                    before_payload_id=anchor,
                    position=n,
                )
            )
    row.updated_at = datetime.now(UTC)
    row.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, id, user, response)


async def copy_manuscript(
    session: SessionDep,
    tenant_id: uuid.UUID,
    source_id: uuid.UUID,
    target: uuid.UUID,
    user: CurrentUser,
) -> dict[uuid.UUID, uuid.UUID]:
    payload_map: dict[uuid.UUID, uuid.UUID] = {}
    info, payloads = await manuscript_payloads(session, tenant_id, source_id, lock=True)
    if info:
        vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
        if not vis.can_see(info):
            raise InformationManagementForbiddenError(
                detail="The entire manuscript must be readable to copy this Edition."
            )
        copied = Information(
            id=uuid.uuid4(),
            entity_id=target,
            tenant_id=tenant_id,
            title=info.title,
            type="manuscript",
            is_public=False,
            created_by=user.id,
        )
        session.add(copied)
        await session.flush()
        for p in payloads:
            new_id = uuid.uuid4()
            payload_map[p.id] = new_id
            session.add(
                Payload(id=new_id, information_id=copied.id, tenant_id=tenant_id, order=p.order)
            )
            await session.flush()
            for model in (PayloadDescription, PayloadPicture, PayloadNumber, PayloadDocument):
                content = await session.get(model, p.id)
                if content:
                    values = {
                        c.name: getattr(content, c.name)
                        for c in model.__table__.columns
                        if c.name not in {"payload_id", "tenant_id"} and c.computed is None
                    }
                    session.add(model(payload_id=new_id, tenant_id=tenant_id, **values))
    return payload_map


@router.post("/editions", status_code=201)
async def duplicate_edition(
    tenant_id: uuid.UUID,
    body: NewEdition,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> WritingEntry:
    await author(session, tenant_id, user)
    await entry(session, tenant_id, body.source_edition_id, user, lock=True)
    source = await session.get(Edition, body.source_edition_id)
    if not source:
        raise EntityNotFoundError(detail="No such Edition.")
    old = await existing_in_tenant(session, Entity, body.id, tenant_id)
    if old:
        marker = await session.get(Edition, body.id)
        if (
            old.created_by != user.id
            or old.name != body.name
            or not marker
            or marker.book_entity_id != source.book_entity_id
        ):
            raise ClientIdUnavailableError(detail="That creation id is already in use.")
        response.status_code = 200
        return await result(session, tenant_id, body.id, user, response)
    # Iterative traversal has no Python recursion or user-facing nesting limit.
    pending = [body.source_edition_id]
    mapping = {body.source_edition_id: body.id}
    payload_map: dict[uuid.UUID, uuid.UUID] = {}
    placements: list[ManuscriptPlacement] = []
    while pending:
        source_id = pending.pop()
        source_entry = await entry(session, tenant_id, source_id, user, lock=True)
        target = mapping[source_id]
        await create_entry(
            session,
            tenant_id,
            user,
            target,
            body.name if source_id == body.source_edition_id else source_entry.name,
        )
        source_telling = await session.get(SceneTelling, source_id)
        session.add(
            Edition(entity_id=target, tenant_id=tenant_id, book_entity_id=source.book_entity_id)
            if source_id == body.source_edition_id
            else SceneTelling(
                entity_id=target,
                tenant_id=tenant_id,
                scene_entity_id=source_telling.scene_entity_id,
                viewpoint_entity_id=source_telling.viewpoint_entity_id,
                uses_scene_manuscript=source_telling.uses_scene_manuscript,
            )
            if source_telling
            else Chapter(entity_id=target, tenant_id=tenant_id)
        )
        source_telling = await session.get(SceneTelling, source_id)
        if not source_telling or not source_telling.uses_scene_manuscript:
            payload_map.update(await copy_manuscript(session, tenant_id, source_id, target, user))
        links = await children(session, tenant_id, source_id)
        placements.extend(links)
        for link in links:
            mapping[link.child_entity_id] = uuid.uuid4()
            pending.append(link.child_entity_id)
        await session.flush()
    for link in placements:
        session.add(
            ManuscriptPlacement(
                child_entity_id=mapping[link.child_entity_id],
                parent_entity_id=mapping[link.parent_entity_id],
                tenant_id=tenant_id,
                before_payload_id=payload_map.get(link.before_payload_id)
                if link.before_payload_id
                else None,
                position=link.position,
            )
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, body.id, user, response)


class NewTelling(NewManuscript):
    scene_id: uuid.UUID
    viewpoint_id: uuid.UUID | None = None
    uses_scene_manuscript: bool = True


async def require_viewpoint(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID | None, user: CurrentUser
) -> None:
    if id is not None:
        await entry(session, tenant_id, id, user)
        if not await session.get(Being, id):
            raise EntityNotFoundError(detail="Choose a Being as the viewpoint.")


@router.post("/tellings", status_code=201)
async def create_telling(
    tenant_id: uuid.UUID,
    body: NewTelling,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> WritingEntry:
    await author(session, tenant_id, user)
    await entry(session, tenant_id, body.scene_id, user)
    if not await session.get(Scene, body.scene_id):
        raise EntityNotFoundError(detail="Choose an existing Scene.")
    await require_viewpoint(session, tenant_id, body.viewpoint_id, user)
    old = await existing_in_tenant(session, Entity, body.id, tenant_id)
    if old:
        marker = await session.get(SceneTelling, body.id)
        if (
            not marker
            or old.created_by != user.id
            or old.name != body.name
            or marker.scene_entity_id != body.scene_id
            or marker.viewpoint_entity_id != body.viewpoint_id
        ):
            raise ClientIdUnavailableError(detail="That creation id is already in use.")
        response.status_code = 200
    else:
        await create_entry(session, tenant_id, user, body.id, body.name)
        session.add(
            SceneTelling(
                entity_id=body.id,
                tenant_id=tenant_id,
                scene_entity_id=body.scene_id,
                viewpoint_entity_id=body.viewpoint_id,
                uses_scene_manuscript=body.uses_scene_manuscript,
            )
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, body.id, user, response)


@router.post("/tellings/{id}/independent")
async def make_independent(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> WritingEntry:
    await author(session, tenant_id, user)
    row = await entry(session, tenant_id, id, user, lock=True)
    telling = await session.get(SceneTelling, id)
    if not telling:
        raise EntityNotFoundError(detail="No such telling.")
    if not telling.uses_scene_manuscript:
        return await result(session, tenant_id, id, user, response)
    await entry(session, tenant_id, telling.scene_entity_id, user, lock=True)
    await manuscript_payloads(session, tenant_id, telling.scene_entity_id, lock=True)
    current = await result(session, tenant_id, id, user, response)
    if if_match is None:
        raise EventOrderPreconditionRequiredError(
            detail="Read this telling before making it independent."
        )
    if if_match != current.version:
        raise PreconditionFailedError(
            detail="The Scene changed. Read its current manuscript first."
        )
    own, _ = await manuscript_payloads(session, tenant_id, id, lock=True)
    if own:
        raise InvalidKindRequestError(detail="This telling already has its own manuscript.")
    await copy_manuscript(session, tenant_id, telling.scene_entity_id, id, user)
    telling.uses_scene_manuscript = False
    row.updated_at = datetime.now(UTC)
    row.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, id, user, response)


class Viewpoint(BaseModel):
    viewpoint_id: uuid.UUID | None


@router.put("/tellings/{id}/viewpoint")
async def change_viewpoint(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    body: Viewpoint,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> WritingEntry:
    await author(session, tenant_id, user)
    row = await entry(session, tenant_id, id, user, lock=True)
    telling = await session.get(SceneTelling, id)
    if not telling:
        raise EntityNotFoundError(detail="No such telling.")
    current = await result(session, tenant_id, id, user, response)
    if if_match is None:
        raise EventOrderPreconditionRequiredError(
            detail="Read the telling before changing its viewpoint."
        )
    if if_match != current.version:
        raise PreconditionFailedError(detail="This telling changed. Read it again.")
    await require_viewpoint(session, tenant_id, body.viewpoint_id, user)
    telling.viewpoint_entity_id = body.viewpoint_id
    row.updated_at = datetime.now(UTC)
    row.updated_by = user.id
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, id, user, response)


@router.post("/biographies", status_code=201)
async def create_biography(
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
            or not await session.get(WritingBiography, body.id)
        ):
            raise ClientIdUnavailableError(detail="That creation id is already in use.")
        response.status_code = 200
    else:
        await create_entry(session, tenant_id, user, body.id, body.name)
        session.add(Being(entity_id=body.id, tenant_id=tenant_id))
        await session.flush()
        session.add(WritingBiography(entity_id=body.id, tenant_id=tenant_id))
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await result(session, tenant_id, body.id, user, response)


@router.get("/biographies")
async def list_biographies(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> Page[ManuscriptSummary]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
    response.headers["Cache-Control"] = "private, no-store"
    page: Page[ManuscriptSummary] = await apaginate(
        session,
        select(Entity.id, Entity.name)
        .join(WritingBiography, WritingBiography.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant_id, visible_entry_clause(vis, Entity.id))
        .order_by(Entity.name, Entity.id),
        params=params,
    )
    return page
