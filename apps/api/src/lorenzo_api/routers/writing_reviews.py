"""A manuscript-only review surface, independent of library membership (ADR 0343)."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from lorenzo_api.campaign_access import is_tenant_author
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    EntityNotFoundError,
    EventOrderPreconditionRequiredError,
    InformationManagementForbiddenError,
    PreconditionFailedError,
)
from lorenzo_api.models import (
    Edition,
    Entity,
    Information,
    ManuscriptPlacement,
    Payload,
    SceneTelling,
    Tenant,
    User,
    WritingReviewGrant,
    WritingReviewNote,
)
from lorenzo_api.routers.writing import author, entry

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing/reviews",
    tags=["Writing review"],
    dependencies=[Depends(get_tenant_or_404)],
)


def missing() -> EntityNotFoundError:
    return EntityNotFoundError(detail="This manuscript is not available for review.")


async def scope(
    session: SessionDep,
    tenant_id: uuid.UUID,
    edition_id: uuid.UUID,
    user: CurrentUser,
    *,
    write: bool = False,
) -> tuple[Edition, bool, set[uuid.UUID], list[ManuscriptPlacement]]:
    # Revocation and composition changes cannot overtake an authorized read or note write.
    await session.scalar(
        select(Tenant.id).where(Tenant.id == tenant_id).with_for_update(read=not write)
    )
    edition = await session.scalar(
        select(Edition).where(Edition.entity_id == edition_id, Edition.tenant_id == tenant_id)
    )
    is_author = await is_tenant_author(session, tenant_id=tenant_id, user_id=user.id)
    granted = await session.scalar(
        select(WritingReviewGrant.edition_id).where(
            WritingReviewGrant.tenant_id == tenant_id,
            WritingReviewGrant.edition_id == edition_id,
            WritingReviewGrant.user_id == user.id,
        )
    )
    if edition is None or not (is_author or granted):
        raise missing()
    links = list(
        await session.scalars(
            select(ManuscriptPlacement)
            .where(ManuscriptPlacement.tenant_id == tenant_id)
            .order_by(ManuscriptPlacement.position, ManuscriptPlacement.child_entity_id)
        )
    )
    children: dict[uuid.UUID, list[uuid.UUID]] = {}
    for link in links:
        children.setdefault(link.parent_entity_id, []).append(link.child_entity_id)
    reachable = {edition_id}
    pending = [edition_id]
    while pending:
        for child in children.get(pending.pop(), []):
            if child not in reachable:
                reachable.add(child)
                pending.append(child)
    return (
        edition,
        is_author,
        reachable,
        [link for link in links if link.parent_entity_id in reachable],
    )


class Reviewer(BaseModel):
    user_id: uuid.UUID
    name: str


async def manage(
    session: SessionDep, tenant_id: uuid.UUID, edition_id: uuid.UUID, user: CurrentUser
) -> None:
    await author(session, tenant_id, user)
    await entry(session, tenant_id, edition_id, user)
    if not await session.get(Edition, edition_id):
        raise missing()


@router.get("/{edition_id}/reviewers")
async def reviewers(
    tenant_id: uuid.UUID,
    edition_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> list[Reviewer]:
    await manage(session, tenant_id, edition_id, user)
    response.headers["Cache-Control"] = "private, no-store"
    rows = await session.scalars(
        select(User)
        .join(WritingReviewGrant, WritingReviewGrant.user_id == User.id)
        .where(
            WritingReviewGrant.tenant_id == tenant_id, WritingReviewGrant.edition_id == edition_id
        )
        .order_by(User.id)
    )
    return [
        Reviewer(user_id=u.id, name=u.display_name or u.nickname or u.email or "Reviewer")
        for u in rows
    ]


@router.put("/{edition_id}/reviewers/{reviewer_id}", status_code=204)
async def grant(
    tenant_id: uuid.UUID,
    edition_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    await manage(session, tenant_id, edition_id, user)
    if not await session.get(User, reviewer_id):
        raise missing()
    if not await session.get(WritingReviewGrant, (edition_id, reviewer_id)):
        session.add(
            WritingReviewGrant(tenant_id=tenant_id, edition_id=edition_id, user_id=reviewer_id)
        )
    await session.commit()


@router.delete("/{edition_id}/reviewers/{reviewer_id}", status_code=204)
async def revoke(
    tenant_id: uuid.UUID,
    edition_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    await manage(session, tenant_id, edition_id, user)
    await session.execute(
        delete(WritingReviewGrant).where(
            WritingReviewGrant.tenant_id == tenant_id,
            WritingReviewGrant.edition_id == edition_id,
            WritingReviewGrant.user_id == reviewer_id,
        )
    )
    await session.commit()


class ReviewElement(BaseModel):
    id: uuid.UUID
    kind: Literal["text", "picture", "entry"]
    content: str | None = None
    url: str | None = None


class ReviewEntry(BaseModel):
    id: uuid.UUID
    name: str
    elements: list[ReviewElement]


class ReviewNote(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    entry_id: uuid.UUID
    author_id: uuid.UUID | None
    author_name: str | None = None
    content: str
    version: int


class Review(BaseModel):
    edition_id: uuid.UUID
    book_name: str
    can_manage: bool
    entries: list[ReviewEntry]
    notes: list[ReviewNote]


async def sources(
    session: SessionDep, tenant_id: uuid.UUID, reachable: set[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    result = {id: id for id in reachable}
    tellings = await session.scalars(
        select(SceneTelling).where(
            SceneTelling.tenant_id == tenant_id, SceneTelling.entity_id.in_(reachable)
        )
    )
    for telling in tellings:
        if telling.uses_scene_manuscript:
            result[telling.entity_id] = telling.scene_entity_id
    return result


@router.get("/{edition_id}")
async def read_review(
    tenant_id: uuid.UUID,
    edition_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
) -> Review:
    edition, is_author, reachable, placements = await scope(session, tenant_id, edition_id, user)
    manuscript_sources = await sources(session, tenant_id, reachable)
    entries = list(
        await session.scalars(
            select(Entity)
            .where(Entity.tenant_id == tenant_id, Entity.id.in_(reachable))
            .order_by(Entity.id)
        )
    )
    payloads = list(
        await session.scalars(
            select(Payload)
            .join(Information, Information.id == Payload.information_id)
            .where(
                Payload.tenant_id == tenant_id,
                Information.tenant_id == tenant_id,
                Information.entity_id.in_(set(manuscript_sources.values())),
                Information.type == "manuscript",
            )
            .options(selectinload(Payload.description), selectinload(Payload.information))
            .order_by(Payload.order, Payload.id)
        )
    )
    # Read picture metadata without loading protected bytes into the JSON response.
    from lorenzo_api.models import PayloadPicture

    pictures = set(
        await session.scalars(
            select(PayloadPicture.payload_id).where(
                PayloadPicture.tenant_id == tenant_id,
                PayloadPicture.payload_id.in_([p.id for p in payloads]),
            )
        )
    )
    output = []
    for item in entries:
        elements: list[ReviewElement] = []
        own = [p for p in payloads if p.information.entity_id == manuscript_sources[item.id]]
        links = [p for p in placements if p.parent_entity_id == item.id]
        for p in own:
            elements.extend(
                ReviewElement(id=link.child_entity_id, kind="entry")
                for link in links
                if link.before_payload_id == p.id
            )
            if p.description is not None:
                elements.append(ReviewElement(id=p.id, kind="text", content=p.description.content))
            elif p.id in pictures:
                elements.append(
                    ReviewElement(
                        id=p.id,
                        kind="picture",
                        url=f"/tenants/{tenant_id}/writing/reviews/{edition_id}/pictures/{p.id}",
                    )
                )
        elements.extend(
            ReviewElement(id=link.child_entity_id, kind="entry")
            for link in links
            if link.before_payload_id is None
        )
        output.append(ReviewEntry(id=item.id, name=item.name, elements=elements))
    note_query = select(WritingReviewNote).where(
        WritingReviewNote.tenant_id == tenant_id, WritingReviewNote.edition_id == edition_id
    )
    if not is_author:
        note_query = note_query.where(
            WritingReviewNote.author_id == user.id, WritingReviewNote.entry_id.in_(reachable)
        )
    notes = list(
        await session.scalars(
            note_query.order_by(WritingReviewNote.created_at, WritingReviewNote.id)
        )
    )
    writers = {
        u.id: u.display_name or u.nickname or u.email or "Reviewer"
        for u in await session.scalars(
            select(User).where(User.id.in_({n.author_id for n in notes}))
        )
    }
    book = await session.get(Entity, edition.book_entity_id)
    assert book is not None
    response.headers["Cache-Control"] = "private, no-store"
    return Review(
        edition_id=edition_id,
        book_name=book.name,
        can_manage=is_author,
        entries=output,
        notes=[
            ReviewNote.model_validate(n).model_copy(
                update={
                    "author_name": writers.get(n.author_id) if n.author_id else "Former reviewer"
                }
            )
            for n in notes
        ],
    )


@router.get("/{edition_id}/pictures/{payload_id}")
async def picture(
    tenant_id: uuid.UUID,
    edition_id: uuid.UUID,
    payload_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    _, _, reachable, _ = await scope(session, tenant_id, edition_id, user)
    manuscript_sources = await sources(session, tenant_id, reachable)
    from lorenzo_api.models import PayloadPicture

    image = await session.scalar(
        select(PayloadPicture)
        .join(Payload, Payload.id == PayloadPicture.payload_id)
        .join(Information, Information.id == Payload.information_id)
        .where(
            PayloadPicture.tenant_id == tenant_id,
            Information.tenant_id == tenant_id,
            Payload.id == payload_id,
            Information.entity_id.in_(set(manuscript_sources.values())),
            Information.type == "manuscript",
        )
    )
    if image is None:
        raise missing()
    return Response(
        content=image.data,
        media_type=image.file_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


class NoteInput(BaseModel):
    entry_id: uuid.UUID
    content: str = Field(min_length=1, max_length=100000)


@router.put("/{edition_id}/notes/{note_id}")
async def write_note(
    tenant_id: uuid.UUID,
    edition_id: uuid.UUID,
    note_id: uuid.UUID,
    body: NoteInput,
    session: SessionDep,
    user: CurrentUser,
    response: Response,
    if_match: Annotated[str | None, Header()] = None,
) -> ReviewNote:
    _, is_author, reachable, _ = await scope(session, tenant_id, edition_id, user, write=True)
    if body.entry_id not in reachable:
        raise missing()
    note = await session.get(WritingReviewNote, note_id)
    if note is None:
        # RLS may hide a conflicting client id; reject without disclosing its tenant.
        from lorenzo_api.client_ids import insert_with_client_id

        note = WritingReviewNote(
            id=note_id,
            tenant_id=tenant_id,
            edition_id=edition_id,
            entry_id=body.entry_id,
            author_id=user.id,
            content=body.content,
        )
        await insert_with_client_id(session, note)
        response.status_code = 201
    else:
        if (
            note.tenant_id != tenant_id
            or note.edition_id != edition_id
            or note.entry_id != body.entry_id
        ):
            raise ClientIdUnavailableError(detail="That note id is already in use.")
        if note.author_id != user.id:
            if not is_author:
                raise missing()
            raise InformationManagementForbiddenError(
                detail="Only the note's author may change it."
            )
        if note.content != body.content:
            if if_match is None:
                raise EventOrderPreconditionRequiredError(
                    detail="Read the note before changing it."
                )
            if if_match != str(note.version):
                raise PreconditionFailedError(
                    detail="This note changed. Read it again before saving."
                )
            note.content = body.content
            note.version += 1
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    await session.refresh(note)
    response.headers["Cache-Control"] = "private, no-store"
    return ReviewNote.model_validate(note)
