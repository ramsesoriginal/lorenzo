"""Book creation and conditional manuscript composition (ADR 0341)."""

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from lorenzo_api.campaign_access import is_tenant_author
from lorenzo_api.client_ids import existing_in_tenant
from lorenzo_api.dependencies import (
    CurrentUser,
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
from lorenzo_api.models import (
    Book,
    Chapter,
    Edition,
    Entity,
    Information,
    ManuscriptPlacement,
    Payload,
    PayloadDescription,
    PayloadDocument,
    PayloadNumber,
    PayloadPicture,
    Tenant,
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
    kind: Literal["payload", "chapter"]
    name: str | None = None


class ManuscriptSummary(BaseModel):
    id: uuid.UUID
    name: str


class WritingEntry(BaseModel):
    id: uuid.UUID
    name: str
    kind: Literal["book", "edition", "chapter"]
    book_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
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
    stmt = select(Information).where(
        Information.tenant_id == tenant_id,
        Information.entity_id == id,
        Information.type == "manuscript",
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
            .order_by(ManuscriptPlacement.position, ManuscriptPlacement.chapter_entity_id)
        )
    )


async def result(
    session: SessionDep, tenant_id: uuid.UUID, id: uuid.UUID, user: CurrentUser, response: Response
) -> WritingEntry:
    row = await entry(session, tenant_id, id, user)
    kind: Literal["book", "edition", "chapter"]
    if await session.get(Book, id):
        kind = "book"
    elif await session.get(Edition, id):
        kind = "edition"
    elif await session.get(Chapter, id):
        kind = "chapter"
    else:
        raise EntityNotFoundError(detail="No such Book, Edition or Chapter.")
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
    token = hashlib.sha256(
        repr(
            (
                row.updated_at,
                [(p.id, p.updated_at, p.order) for p in payloads if info and vis.can_see(info)],
                [
                    (p.chapter_entity_id, p.before_payload_id, p.position)
                    for p in links
                    if p.chapter_entity_id in visible
                ],
            )
        ).encode()
    ).hexdigest()
    version = f'W/"{token}"'
    elements: list[Element] = []

    def add_links(anchor: uuid.UUID | None) -> None:
        for link in links:
            if link.before_payload_id == anchor and link.chapter_entity_id in visible:
                elements.append(Element(id=link.chapter_entity_id, kind="chapter"))

    for p in payloads:
        add_links(p.id)
        if info and vis.can_see(info):
            elements.append(Element(id=p.id, kind="payload"))
    add_links(None)
    for el in elements:
        if el.kind == "chapter":
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
    return WritingEntry(
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
        if not await session.get(Chapter, child_id):
            raise InvalidKindRequestError(detail="Only Chapters can be placed here.")
        link = await session.get(ManuscriptPlacement, child_id)
        if link and link.parent_entity_id != id:
            raise InvalidKindRequestError(
                detail="Remove this Chapter from its current outline first."
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
                    chapter_entity_id=child_id,
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
        session.add(
            Edition(entity_id=target, tenant_id=tenant_id, book_entity_id=source.book_entity_id)
            if source_id == body.source_edition_id
            else Chapter(entity_id=target, tenant_id=tenant_id)
        )
        info, payloads = await manuscript_payloads(session, tenant_id, source_id, lock=True)
        if info:
            vis = await resolve_information_visibility(
                session, tenant_id=tenant_id, user_id=user.id
            )
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
                            if c.name not in {"payload_id", "tenant_id"}
                        }
                        session.add(model(payload_id=new_id, tenant_id=tenant_id, **values))
        links = await children(session, tenant_id, source_id)
        placements.extend(links)
        for link in links:
            mapping[link.chapter_entity_id] = uuid.uuid4()
            pending.append(link.chapter_entity_id)
        await session.flush()
    for link in placements:
        session.add(
            ManuscriptPlacement(
                chapter_entity_id=mapping[link.chapter_entity_id],
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
