"""Atomic Chapter joins with guarded source identities (ADRs 0348, 0374)."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel
from sqlalchemy import delete, select, union, update

from lorenzo_api.client_ids import existing_in_tenant, insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.exceptions import (
    ClientIdUnavailableError,
    ManuscriptMoveConflictError,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.models import (
    CampaignGm,
    Chapter,
    Edition,
    EntityAudience,
    EntityKnowledge,
    Information,
    Knowledge,
    ManuscriptJoin,
    ManuscriptPlacement,
    ManuscriptRedirect,
    Membership,
    Player,
)
from lorenzo_api.routers.entities import authorize_information_edit
from lorenzo_api.routers.manuscript_extraction import place
from lorenzo_api.routers.manuscript_moves import require_version
from lorenzo_api.routers.writing import author, children, entry, manuscript_payloads, result

router = APIRouter(
    prefix="/tenants/{tenant_id}/writing",
    tags=["Writing"],
    dependencies=[Depends(get_tenant_or_404)],
)


class JoinChapters(BaseModel):
    mode: Literal["previous", "parent"] = "previous"
    destination_id: uuid.UUID
    parent_id: uuid.UUID
    destination_version: str
    parent_version: str


class JoinAcknowledgement(BaseModel):
    operation_id: uuid.UUID
    source_id: uuid.UUID
    destination_id: uuid.UUID


async def same_outer(session: SessionDep, left: uuid.UUID, right: uuid.UUID) -> bool:
    async def audience(id: uuid.UUID) -> tuple[Any, ...]:
        row = await session.get(EntityAudience, id)
        grants = frozenset(
            (e, p)
            for e, p in await session.execute(
                select(EntityKnowledge.knower_entity_id, EntityKnowledge.knower_player_id).where(
                    EntityKnowledge.entity_id == id
                )
            )
        )
        return (
            row.is_public if row else True,
            row.shared_with_participants if row else False,
            grants,
        )

    return await audience(left) == await audience(right)


def same_inner(left: Information, right: Information) -> bool:
    def audience(info: Information) -> tuple[Any, ...]:
        return (
            info.is_public,
            info.shared_with_participants,
            info.created_by,
            frozenset((k.knower_entity_id, k.knower_player_id) for k in info.knowledge_links),
        )

    return audience(left) == audience(right)


async def require_no_new_readers(
    session: SessionDep,
    tenant: uuid.UUID,
    source: uuid.UUID,
    destination: uuid.UUID,
    source_info: Information | None,
    destination_info: Information | None,
) -> None:
    # Equal authored audiences need not mean equal access: GMs can have contextual
    # reach to one Chapter. Use the existing resolver for every current participant.
    people = await session.scalars(
        union(
            select(Membership.user_id).where(Membership.tenant_id == tenant),
            select(Player.user_id).where(Player.tenant_id == tenant),
            select(CampaignGm.user_id).where(CampaignGm.tenant_id == tenant),
        )
    )
    for person in people:
        vis = await resolve_information_visibility(session, tenant_id=tenant, user_id=person)
        wider = vis.can_see_entry(destination) and not vis.can_see_entry(source)
        if source_info and not vis.can_see(source_info):
            if destination_info:
                wider |= vis.can_see(destination_info)
            else:
                # A newly created bundle keeps source grants/flags/authorship. Only
                # the new entry's contextual bypass can add access to those fields.
                wider |= vis.can_see_entry(destination) and (
                    destination in vis.gm_reachable_entity_ids
                    or destination in vis.author_entry_ids
                )
        if wider:
            raise ManuscriptMoveConflictError(
                detail="This join would add readers through campaign access. Review sharing first."
            )


@router.post("/entries/{id}/joins/{operation_id}")
async def join(
    tenant_id: uuid.UUID,
    id: uuid.UUID,
    operation_id: uuid.UUID,
    body: JoinChapters,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> JoinAcknowledgement:
    await author(session, tenant_id, user)
    into_parent = body.mode == "parent"
    if (into_parent and (id == body.parent_id or body.destination_id != body.parent_id)) or (
        not into_parent and len({id, body.destination_id, body.parent_id}) != 3
    ):
        raise ManuscriptMoveConflictError(detail="Choose a Chapter and its join destination.")
    rows = {
        key: await entry(session, tenant_id, key, user, lock=True)
        for key in sorted({id, body.destination_id, body.parent_id})
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "source": str(id),
                "version": if_match,
                "body": body.model_dump(mode="json", exclude_defaults=True),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    response.headers["Cache-Control"] = "private, no-store"
    previous = await existing_in_tenant(session, ManuscriptJoin, operation_id, tenant_id)
    if previous:
        if (
            previous.actor_id != user.id
            or previous.source_id != id
            or previous.destination_id != body.destination_id
            or previous.request_hash != fingerprint
        ):
            raise ClientIdUnavailableError(detail="That join id is already in use.")
        for key in (id, body.destination_id):
            info, _ = await manuscript_payloads(session, tenant_id, key)
            if info:
                await authorize_information_edit(
                    session, tenant_id=tenant_id, user=user, information=info, history_read=True
                )
        return JoinAcknowledgement(
            operation_id=operation_id, source_id=id, destination_id=body.destination_id
        )
    for key in (id, body.destination_id):
        if into_parent and key == body.destination_id:
            if not await session.get(Chapter, key) and not await session.get(Edition, key):
                raise ManuscriptMoveConflictError(detail="Join into a parent Chapter or Edition.")
            continue
        if not await session.get(Chapter, key):
            raise ManuscriptMoveConflictError(detail="Join two adjacent Chapters.")
        placement = await session.get(ManuscriptPlacement, key)
        if not placement or placement.parent_entity_id != body.parent_id:
            raise ManuscriptMoveConflictError(detail="These Chapters no longer share this outline.")
    bundles = {}
    outlines = {}
    links = {}
    for key in sorted(rows):
        info, payloads = await manuscript_payloads(session, tenant_id, key, lock=True)
        if info:
            await authorize_information_edit(
                session, tenant_id=tenant_id, user=user, information=info
            )
        bundles[key] = (info, payloads)
        outline = await result(session, tenant_id, key, user, response)
        require_version(
            if_match
            if key == id
            else body.destination_version
            if key == body.destination_id
            else body.parent_version,
            outline.version,
        )
        if into_parent and key == body.parent_id:
            require_version(body.parent_version, outline.version)
        outlines[key] = [el.id for el in outline.elements]
        links[key] = await children(session, tenant_id, key)
        if set(outlines[key]) != {p.id for p in payloads} | {p.child_entity_id for p in links[key]}:
            raise ManuscriptMoveConflictError(
                detail="Read the complete Chapters and parent outline before joining."
            )
    parent_order = outlines[body.parent_id]
    at = parent_order.index(id)
    if not into_parent and (at == 0 or parent_order[at - 1] != body.destination_id):
        raise ManuscriptMoveConflictError(
            detail="Join a Chapter with the Chapter immediately before it."
        )
    source_ids, destination_ids = outlines[id], outlines[body.destination_id]
    if not source_ids:
        raise ManuscriptMoveConflictError(
            detail="This Chapter is empty. You can remove it from the outline instead."
        )
    if not await same_outer(session, id, body.destination_id):
        raise ManuscriptMoveConflictError(
            detail="These Chapters have different sharing. Review their audiences before joining."
        )
    source_info, source_payloads = bundles[id]
    destination_info, destination_payloads = bundles[body.destination_id]
    if (
        source_payloads
        and destination_info
        and source_info
        and not same_inner(source_info, destination_info)
    ):
        raise ManuscriptMoveConflictError(
            detail="These manuscripts have different sharing or authorship. Review them first."
        )
    await require_no_new_readers(
        session,
        tenant_id,
        id,
        body.destination_id,
        source_info if source_payloads else None,
        destination_info,
    )
    if source_payloads and destination_info is None:
        assert source_info is not None
        destination_info = Information(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            entity_id=body.destination_id,
            title=source_info.title,
            type="manuscript",
            created_by=source_info.created_by,
            is_public=source_info.is_public,
            shared_with_participants=source_info.shared_with_participants,
        )
        session.add(destination_info)
        await session.flush()
        for grant in source_info.knowledge_links:
            session.add(
                Knowledge(
                    tenant_id=tenant_id,
                    information_id=destination_info.id,
                    knower_entity_id=grant.knower_entity_id,
                    knower_player_id=grant.knower_player_id,
                )
            )
    combined = (
        parent_order[:at] + source_ids + parent_order[at + 1 :]
        if into_parent
        else destination_ids + source_ids
    )
    parent_after = combined if into_parent else [el for el in parent_order if el != id]
    # Checkpoint old content before reassignment and avoid unique order collisions.
    for payloads in (source_payloads, destination_payloads):
        floor = min((p.order for p in payloads), default=0) - len(payloads) - 1
        for n, payload in enumerate(payloads):
            payload.order = floor + n
    await session.flush()
    if destination_info:
        by_id = {p.id: p for p in [*destination_payloads, *source_payloads]}
        for n, payload in enumerate(by_id[key] for key in combined if key in by_id):
            payload.information_id = destination_info.id
            payload.order = n
            payload.updated_at = datetime.now(UTC)
        destination_info.updated_at = datetime.now(UTC)
    if source_info:
        source_info.updated_at = datetime.now(UTC)
    await session.execute(
        delete(ManuscriptPlacement).where(
            ManuscriptPlacement.tenant_id == tenant_id,
            ManuscriptPlacement.parent_entity_id.in_(rows),
        )
    )
    if not into_parent:
        place(
            session,
            tenant_id,
            body.parent_id,
            parent_after,
            {p.id for p in bundles[body.parent_id][1]},
        )
    place(
        session,
        tenant_id,
        body.destination_id,
        combined,
        {p.id for p in [*destination_payloads, *source_payloads]},
    )
    anchor = source_ids[0]
    own = {p.id for p in source_payloads}
    await session.execute(
        update(ManuscriptRedirect)
        .where(ManuscriptRedirect.tenant_id == tenant_id, ManuscriptRedirect.destination_id == id)
        .values(destination_id=body.destination_id)
    )
    session.add(
        ManuscriptRedirect(
            source_id=id,
            tenant_id=tenant_id,
            destination_id=body.destination_id,
            payload_id=anchor if anchor in own else None,
            child_id=anchor if anchor not in own else None,
        )
    )
    for row in rows.values():
        row.updated_at = datetime.now(UTC)
        row.updated_by = user.id
    await insert_with_client_id(
        session,
        ManuscriptJoin(
            id=operation_id,
            tenant_id=tenant_id,
            source_id=id,
            destination_id=body.destination_id,
            actor_id=user.id,
            request_hash=fingerprint,
            checkpoint={
                "before": {str(k): [str(v) for v in values] for k, values in outlines.items()},
                "after": {
                    str(id): [],
                    str(body.destination_id): [str(v) for v in combined],
                    str(body.parent_id): [str(v) for v in parent_after],
                },
            },
        ),
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    del response.headers["ETag"]
    return JoinAcknowledgement(
        operation_id=operation_id, source_id=id, destination_id=body.destination_id
    )
