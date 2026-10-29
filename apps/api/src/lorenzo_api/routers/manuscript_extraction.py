"""Extract complete composition elements without changing their contents (ADR 0345)."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from lorenzo_api.client_ids import existing_in_tenant, insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    EntityNotFoundError,
    ManuscriptMoveConflictError,
)
from lorenzo_api.manuscript_access import require_no_new_readers
from lorenzo_api.models import (
    Chapter,
    Edition,
    Entity,
    EntityAudience,
    EntityKnowledge,
    Information,
    Knowledge,
    ManuscriptExtraction,
    ManuscriptPlacement,
    ManuscriptSceneExtraction,
    Scene,
    SceneTelling,
)
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.manuscript_moves import require_version
from lorenzo_api.routers.story_sessions import create_entry
from lorenzo_api.routers.writing import author, children, entry, manuscript_payloads, result

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class ExtractChapter(BaseModel):
    chapter_id: uuid.UUID
    name: str = Field(min_length=1, max_length=300)
    elements: list[uuid.UUID] = Field(min_length=1)


class ExtractScene(BaseModel):
    scene_id: uuid.UUID
    telling_id: uuid.UUID
    name: str = Field(min_length=1, max_length=300)
    elements: list[uuid.UUID] = Field(min_length=1)


class SceneExtractionAcknowledgement(BaseModel):
    operation_id: uuid.UUID
    source_id: uuid.UUID
    scene_id: uuid.UUID
    telling_id: uuid.UUID


class ExtractionAcknowledgement(BaseModel):
    operation_id: uuid.UUID
    source_id: uuid.UUID
    chapter_id: uuid.UUID


class ExtractionCheckpoint(ExtractionAcknowledgement):
    checkpoint: dict[str, Any]


def place(
    session: SessionDep,
    tenant: uuid.UUID,
    parent: uuid.UUID,
    ids: list[uuid.UUID],
    payload_ids: set[uuid.UUID],
) -> None:
    anchor = None
    for position, child in reversed(list(enumerate(ids))):
        if child in payload_ids:
            anchor = child
        else:
            session.add(
                ManuscriptPlacement(
                    tenant_id=tenant,
                    parent_entity_id=parent,
                    child_entity_id=child,
                    before_payload_id=anchor,
                    position=position,
                )
            )


async def extract_elements(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    operation_id: uuid.UUID,
    body: ExtractChapter | ExtractScene,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ExtractionAcknowledgement | SceneExtractionAcknowledgement:
    await author(session, tenant_id, user)
    source = await entry(session, tenant_id, id, user, lock=True)
    as_scene = isinstance(body, ExtractScene)
    target_id = body.scene_id if isinstance(body, ExtractScene) else body.chapter_id
    placed_id = body.telling_id if isinstance(body, ExtractScene) else target_id
    if id in {target_id, placed_id} or (as_scene and target_id == placed_id):
        raise ManuscriptMoveConflictError(detail="Use new identities for the extracted writing.")

    def acknowledgement() -> ExtractionAcknowledgement | SceneExtractionAcknowledgement:
        if isinstance(body, ExtractScene):
            return SceneExtractionAcknowledgement(
                operation_id=operation_id,
                source_id=id,
                scene_id=body.scene_id,
                telling_id=body.telling_id,
            )
        return ExtractionAcknowledgement(
            operation_id=operation_id, source_id=id, chapter_id=body.chapter_id
        )

    fingerprint = hashlib.sha256(
        json.dumps(
            {"source": str(id), "version": if_match, "body": body.model_dump(mode="json")},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    response.headers["Cache-Control"] = "private, no-store"
    previous = (
        await existing_in_tenant(session, ManuscriptSceneExtraction, operation_id, tenant_id)
        if as_scene
        else await existing_in_tenant(session, ManuscriptExtraction, operation_id, tenant_id)
    )
    if previous:
        if (
            previous.actor_id != user.id
            or previous.source_id != id
            or previous.request_hash != fingerprint
        ):
            raise ClientIdUnavailableError(detail="That extraction id is already in use.")
        await entry(session, tenant_id, target_id, user)
        if as_scene:
            await entry(session, tenant_id, placed_id, user)
        return acknowledgement()
    if not await session.get(Edition, id) and not await session.get(Chapter, id):
        raise ManuscriptMoveConflictError(detail="Extract from an Edition or Chapter outline.")
    info, payloads = await manuscript_payloads(session, tenant_id, id, lock=True)
    if info:
        await authorize_information_edit(session, tenant_id=tenant_id, user=user, information=info)
    current = await result(session, tenant_id, id, user, response)
    require_version(if_match, current.version)
    ids = [el.id for el in current.elements]
    selected = body.elements
    links = await children(session, tenant_id, id)
    if set(ids) != {p.id for p in payloads} | {p.child_entity_id for p in links}:
        raise ManuscriptMoveConflictError(
            detail="The entire outline must be readable to extract writing."
        )
    if selected[0] not in ids or len(selected) != len(set(selected)):
        raise ManuscriptMoveConflictError(detail="Choose a consecutive range from this outline.")
    start = ids.index(selected[0])
    if ids[start : start + len(selected)] != selected:
        raise ManuscriptMoveConflictError(detail="Choose a consecutive range in its current order.")
    for link in links:
        await entry(session, tenant_id, link.child_entity_id, user, lock=True)
    own = {p.id for p in payloads}
    if as_scene and not set(selected) <= own:
        raise ManuscriptMoveConflictError(
            detail="A Scene can hold text and pictures, not Chapters or other tellings."
        )
    for new_id in {target_id, placed_id}:
        if await existing_in_tenant(session, Entity, new_id, tenant_id):
            raise ClientIdUnavailableError(detail="That extraction entry id is already in use.")
    new = await create_entry(session, tenant_id, user, target_id, body.name)
    if as_scene:
        session.add(Scene(entity_id=target_id, tenant_id=tenant_id))
        await session.flush()
        await create_entry(session, tenant_id, user, placed_id, body.name)
        session.add(
            SceneTelling(
                entity_id=placed_id,
                tenant_id=tenant_id,
                scene_entity_id=target_id,
                uses_scene_manuscript=True,
            )
        )
    else:
        session.add(Chapter(entity_id=target_id, tenant_id=tenant_id))
    await session.flush()
    outer = await session.get(EntityAudience, id)
    for new_id in {target_id, placed_id}:
        target_outer = await session.get(EntityAudience, new_id)
        assert target_outer is not None
        target_outer.is_public = outer.is_public if outer else True
        target_outer.shared_with_participants = outer.shared_with_participants if outer else False
        if outer:
            for grant in await session.scalars(
                select(EntityKnowledge).where(EntityKnowledge.entity_id == id)
            ):
                session.add(
                    EntityKnowledge(
                        tenant_id=tenant_id,
                        entity_id=new_id,
                        knower_entity_id=grant.knower_entity_id,
                        knower_player_id=grant.knower_player_id,
                    )
                )
    taken = set(selected) & own
    if taken:
        assert info is not None
        target_info = Information(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entity_id=target_id,
            type="manuscript",
            title=info.title,
            created_by=info.created_by,
            is_public=info.is_public,
            shared_with_participants=info.shared_with_participants,
        )
        session.add(target_info)
        await session.flush()
        for knowledge in info.knowledge_links:
            session.add(
                Knowledge(
                    tenant_id=tenant_id,
                    information_id=target_info.id,
                    knower_entity_id=knowledge.knower_entity_id,
                    knower_player_id=knowledge.knower_player_id,
                )
            )
        if as_scene:
            await session.flush()
            await session.refresh(target_info, ["knowledge_links"])
            await require_no_new_readers(session, tenant_id, id, target_id, info, target_info)
            await require_no_new_readers(session, tenant_id, id, placed_id, None, None)
        # Stage order changes BEFORE reassignment: the existing trigger snapshots the old bundle.
        # A disjoint range also avoids unique (information_id, order) collisions during compaction.
        floor = min((p.order for p in payloads), default=0) - len(payloads) - 1
        for n, payload in enumerate(payloads):
            payload.order = floor + n
        await session.flush()
        remaining_order = extracted_order = 0
        for payload in payloads:
            if payload.id in taken:
                payload.information_id = target_info.id
                payload.order = extracted_order
                extracted_order += 1
            else:
                payload.order = remaining_order
                remaining_order += 1
            payload.updated_at = datetime.now(UTC)
        info.updated_at = datetime.now(UTC)
    after = ids[:start] + [placed_id] + ids[start + len(selected) :]
    await session.execute(
        delete(ManuscriptPlacement).where(
            ManuscriptPlacement.tenant_id == tenant_id, ManuscriptPlacement.parent_entity_id == id
        )
    )
    place(session, tenant_id, id, after, own - taken)
    if not as_scene:
        place(session, tenant_id, target_id, selected, taken)
    for row in (source, new):
        row.updated_at = datetime.now(UTC)
        row.updated_by = user.id
    checkpoint_data = {
        "before": {str(id): [str(x) for x in ids]},
        "after": {str(id): [str(x) for x in after], str(target_id): [str(x) for x in selected]},
    }
    if isinstance(body, ExtractScene):
        receipt = ManuscriptSceneExtraction(
            id=operation_id,
            tenant_id=tenant_id,
            source_id=id,
            scene_id=target_id,
            telling_id=placed_id,
            actor_id=user.id,
            request_hash=fingerprint,
            checkpoint=checkpoint_data,
        )
        await insert_with_client_id(session, receipt)
    else:
        await insert_with_client_id(
            session,
            ManuscriptExtraction(
                id=operation_id,
                tenant_id=tenant_id,
                source_id=id,
                chapter_id=target_id,
                actor_id=user.id,
                request_hash=fingerprint,
                checkpoint=checkpoint_data,
            ),
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    del response.headers["ETag"]
    return acknowledgement()


@router.post("/entries/{id}/extractions/{operation_id}")
async def extract(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    operation_id: uuid.UUID,
    body: ExtractChapter,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> ExtractionAcknowledgement:
    answer = await extract_elements(
        tenant_id, id, operation_id, body, response, session, user, if_match
    )
    assert isinstance(answer, ExtractionAcknowledgement)
    return answer


@router.post("/entries/{id}/scene-extractions/{operation_id}")
async def extract_scene(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    operation_id: uuid.UUID,
    body: ExtractScene,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SceneExtractionAcknowledgement:
    answer = await extract_elements(
        tenant_id, id, operation_id, body, response, session, user, if_match
    )
    assert isinstance(answer, SceneExtractionAcknowledgement)
    return answer


@router.get("/entries/{id}/extractions/{operation_id}")
async def checkpoint(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    operation_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> ExtractionCheckpoint:
    await author(session, tenant_id, user)
    await entry(session, tenant_id, id, user)
    receipt = await existing_in_tenant(session, ManuscriptExtraction, operation_id, tenant_id)
    if receipt is None or receipt.source_id != id:
        raise EntityNotFoundError(detail="No such extraction checkpoint.")
    await entry(session, tenant_id, receipt.chapter_id, user)
    response.headers["Cache-Control"] = "private, no-store"
    return ExtractionCheckpoint(
        operation_id=operation_id,
        source_id=id,
        chapter_id=receipt.chapter_id,
        checkpoint=receipt.checkpoint,
    )
