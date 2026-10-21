import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Header, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.client_ids import insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.description_payloads import write_description
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    AudiencePreconditionRequiredError,
    EntityNotFoundError,
    InformationManagementForbiddenError,
    InvalidAudienceRecipientError,
    MainPictureThroughEntityError,
    PayloadReplayConflictError,
    PlayerNotFoundError,
)
from lorenzo_api.information_bundles import (
    payload_replay,
    replace_payload_order,
    require_bundle_version,
    touch_bundle,
)
from lorenzo_api.information_visibility import resolve_information_visibility
from lorenzo_api.learning import require_no_learning
from lorenzo_api.models import Entity, Information, Knowledge, Payload, Player, StoryEvent, User
from lorenzo_api.picture_payloads import add_picture_payload, read_picture_upload
from lorenzo_api.routers.entities import (
    authorize_information_edit,
    get_information_or_404,
    information_out_or_404,
    lock_entity_information,
    require_information_order_free,
    require_singleton_type_free,
)
from lorenzo_api.schemas.entities import InformationOut, InformationUpdate, KnowerOut
from lorenzo_api.schemas.knowledge import InformationAudience
from lorenzo_api.schemas.payloads import (
    PayloadDescriptionOut,
    PayloadOrderRequest,
    PayloadPictureOut,
    PayloadTextCreate,
    payload_to_schema,
)

# get_tenant_or_404, not get_tenant_context (ADR 0038/RFC 0011, matching
# routers/entities.py's identical revision): GET here is gated by the
# resource's own information_visibility, not tenant-wide Membership, and
# every write below uses self-or-managed authorization plus sight of the
# row (ADR 0101) - none needs a Membership row.
router = APIRouter(
    prefix="/tenants/{tenant_id}/information",
    tags=["information"],
    dependencies=[Depends(get_tenant_or_404)],
)


@router.get("/{information_id}", name="get_information")
async def get_information(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> InformationOut:
    information = await information_out_or_404(
        tenant_id, information_id, request, session, user=user
    )
    response.headers["ETag"] = etag_for(information.updated_at)
    return information


async def locked_information(
    session: SessionDep, information_id: uuid.UUID, tenant_id: uuid.UUID
) -> Information:
    # Use the same entity-before-information lock order as reordering/picture writes.
    entity_id = (
        await session.execute(
            select(Information.entity_id).where(
                Information.id == information_id, Information.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if entity_id is not None:
        await lock_entity_information(session, entity_id=entity_id, tenant_id=tenant_id)
    # Load the version and grants only after acquiring the locks.
    await session.execute(
        select(Information.id)
        .where(Information.id == information_id, Information.tenant_id == tenant_id)
        .with_for_update()
    )
    return await get_information_or_404(session, information_id, tenant_id)


@router.patch("/{information_id}")
async def update_information(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    body: InformationUpdate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> InformationOut:
    """Edits title/type/is_public/order - ADR 0101/RFC 0015. Check order:
    sight of the row (404), standing over its entity (403), If-Match
    (412), then - under the entity's row lock - a singleton `type` the
    entity already holds and a taken `order` (both 409).

    Only a visibility change is logged (ADR 0084: it changes who can see
    the row); title/type/order edits are descriptive content.
    """
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    from lorenzo_api.event_fact_access import is_event_fact, manages_events
    from lorenzo_api.session_access import manages_planning_entry, planning_entry

    if (
        (
            await planning_entry(session, tenant_id, information.entity_id)
            or await is_event_fact(session, tenant_id=tenant_id, entity_id=information.entity_id)
        )
        and not (
            await manages_planning_entry(session, tenant_id, information.entity_id, user.id)
            if await planning_entry(session, tenant_id, information.entity_id)
            else await manages_events(session, tenant_id=tenant_id, user_id=user.id)
        )
        and (body.order is not None or (body.type is not None and body.type != "note"))
    ):
        raise InformationManagementForbiddenError(
            detail="Readers edit their own note without changing its kind or position"
        )

    check_if_match(if_match, updated_at=information.updated_at)

    update = body.model_dump(exclude_unset=True)
    if update.get("type") is not None and update["type"] != information.type:
        await lock_entity_information(session, entity_id=information.entity_id, tenant_id=tenant_id)
        await require_singleton_type_free(
            session,
            entity_id=information.entity_id,
            tenant_id=tenant_id,
            type_=update["type"],
            exclude_information_id=information.id,
        )
    if update.get("order") is not None and update["order"] != information.order:
        await lock_entity_information(session, entity_id=information.entity_id, tenant_id=tenant_id)
        await require_information_order_free(
            session,
            entity_id=information.entity_id,
            tenant_id=tenant_id,
            order=update["order"],
        )

    visibility_changed = (
        update.get("is_public") is not None and update["is_public"] != information.is_public
    )
    for field in ("title", "type", "is_public", "order"):
        # An explicit null on a non-nullable field means "leave it" rather
        # than a 500 from the NOT NULL constraint.
        if update.get(field) is not None:
            setattr(information, field, update[field])
    if visibility_changed:
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="information.visibility_changed",
            target_type="information",
            target_id=information_id,
            detail=f"visibility={'public' if information.is_public else 'restricted'}",
        )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    out = await information_out_or_404(
        tenant_id, information_id, request, session, user=user, require_visible=False
    )
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.delete("/{information_id}", status_code=204)
async def delete_information(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Removes the row with its payloads and knowledge links (cascade) -
    ADR 0101/RFC 0015. Same gate as update_information. Logged (ADR 0084:
    it changes what exists), entity id only - never title or content.
    """
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    check_if_match(if_match, updated_at=information.updated_at)

    await require_no_learning(session, tenant_id, information_id=information.id)
    await session.delete(information)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="information.deleted",
        target_type="information",
        target_id=information_id,
        detail=f"entity={information.entity_id}",
    )
    await session.commit()


@router.post("/{information_id}/payloads", status_code=201)
async def add_information_picture(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
    file: UploadFile,
    response: Response,
    payload_id: Annotated[uuid.UUID | None, Form()] = None,
    if_match: Annotated[str | None, Header()] = None,
) -> PayloadPictureOut:
    """Adds a picture to the information, as one more payload after the ones it has (ADR 0237,
    K8 of RFC 0041). A multipart upload of a PNG, JPEG, WebP or GIF of at most
    `picture_max_bytes` (422 otherwise). Check order: sight of the row (404), standing over its
    entry (403), then the upload. The entry's `main_picture` is not added to this way (409):
    it is one picture, set with PUT .../entities/{id}/picture. Logged, with the information's id
    only (ADR 0084).
    """
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    if information.type == "main_picture":
        raise MainPictureThroughEntityError(
            detail="The main picture is one picture: set it with PUT .../entities/{id}/picture"
        )
    data, file_type = await read_picture_upload(file)

    replay = await payload_replay(
        session, tenant_id=tenant_id, information_id=information_id, payload_id=payload_id
    )
    if replay is not None:
        if (
            replay.picture is None
            or replay.picture.data != data
            or replay.picture.file_type != file_type
        ):
            raise PayloadReplayConflictError(
                detail="Choose a new payload id for different content."
            )
        response.status_code = 200
        response.headers["ETag"] = etag_for(information.updated_at)
        out = payload_to_schema(replay, request)
        assert isinstance(out, PayloadPictureOut)
        return out
    check_if_match(if_match, updated_at=information.updated_at)
    payload = await add_picture_payload(
        session,
        tenant_id=tenant_id,
        information_id=information_id,
        data=data,
        file_type=file_type,
        payload_id=payload_id,
    )
    touch_bundle(information)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="payload.picture_added",
        target_type="payload",
        target_id=payload.id,
        detail=f"information={information_id}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    stmt = (
        select(Payload)
        .where(Payload.id == payload.id)
        .options(
            selectinload(Payload.description),
            selectinload(Payload.number),
            selectinload(Payload.picture),
            selectinload(Payload.document),
        )
        .execution_options(populate_existing=True)
    )
    stored = (await session.execute(stmt)).scalar_one()
    out = payload_to_schema(stored, request)
    assert isinstance(out, PayloadPictureOut)
    response.headers["ETag"] = etag_for(information.updated_at)
    return out


async def _require_knower_entity_exists(
    session: SessionDep, knower_entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """Validates knower_entity_id is a real Entity in this tenant - RFC
    0001's own three knower cases (character, group, player) both use a
    plain entity_id for the first two, disambiguated only by whether a
    Being row also exists (Knowledge's own docstring) - no stricter check
    than "this is some entity in this tenant" is enforced here, matching
    that same looseness. Player-knowers are out of scope for this slice
    (see ADR 0038) - only entity-knowers (character or group) are
    supported.
    """
    stmt = select(Entity.id).where(Entity.id == knower_entity_id, Entity.tenant_id == tenant_id)
    if (await session.execute(stmt)).first() is None:
        raise EntityNotFoundError(
            detail=f"No entity with id {knower_entity_id} in tenant {tenant_id}"
        )


async def _get_knowledge_link(
    session: SessionDep,
    *,
    knower_entity_id: uuid.UUID,
    information_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> Knowledge | None:
    stmt = select(Knowledge).where(
        Knowledge.knower_entity_id == knower_entity_id,
        Knowledge.information_id == information_id,
        Knowledge.tenant_id == tenant_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


@router.put("/{information_id}/knowers/{knower_entity_id}")
async def add_information_knower(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    knower_entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> InformationOut:
    """Attaches a knower (a character or group entity) to an existing
    Information row - see ADR 0038/RFC 0011. Idempotent, mirroring
    grant_campaign_gm/set_item_instance_owner's own "no row means no
    relation, PUT creates it" shape. Authorized against the *information's
    own entity_id* (the thing the information describes), not the knower -
    granting knowledge about entity X needs the same standing as authoring
    information about X in the first place, not standing over whichever
    character/group is being granted it.

    Also requires sight of the row, or authorship (ADR 0101,
    routers/entities.authorize_information_edit): standing over an entity
    alone must not let a player grant their own character a GM secret
    about it.
    """
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    await _require_knower_entity_exists(session, knower_entity_id, tenant_id)

    existing = await _get_knowledge_link(
        session,
        knower_entity_id=knower_entity_id,
        information_id=information_id,
        tenant_id=tenant_id,
    )
    if existing is None:
        session.add(
            Knowledge(
                tenant_id=tenant_id,
                knower_entity_id=knower_entity_id,
                information_id=information_id,
            )
        )
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="information.knower_added",
            target_type="information",
            target_id=information_id,
            detail=f"knower={knower_entity_id}",
        )
        information.updated_at = datetime.now(UTC)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await information_out_or_404(
        tenant_id, information_id, request, session, user=user, require_visible=False
    )


@router.delete("/{information_id}/knowers/{knower_entity_id}")
async def remove_information_knower(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    knower_entity_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> InformationOut:
    """200 + the parent Information, not 204 - removing one knower leaves
    the information itself intact (ADR 0032/RFC 0005's own singular
    sub-resource shape, reused here for a genuinely n:m relation the same
    way routers/characters.py's roster-link endpoints already do).
    """
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )

    existing = await _get_knowledge_link(
        session,
        knower_entity_id=knower_entity_id,
        information_id=information_id,
        tenant_id=tenant_id,
    )
    if existing is not None:
        await session.delete(existing)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="information.knower_removed",
            target_type="information",
            target_id=information_id,
            detail=f"knower={knower_entity_id}",
        )
        information.updated_at = datetime.now(UTC)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await information_out_or_404(
        tenant_id, information_id, request, session, user=user, require_visible=False
    )


async def _require_player_exists(
    session: SessionDep, player_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """player_id must be a Player seat in this tenant - ADR 0109. Its
    campaign isn't checked against the entity: the same looseness the
    entity-knower route has for characters (ADR 0028's addendum)."""
    stmt = select(Player.id).where(Player.id == player_id, Player.tenant_id == tenant_id)
    if (await session.execute(stmt)).first() is None:
        raise PlayerNotFoundError(detail=f"No player with id {player_id} in tenant {tenant_id}")


async def _get_player_knowledge_link(
    session: SessionDep, *, player_id: uuid.UUID, information_id: uuid.UUID, tenant_id: uuid.UUID
) -> Knowledge | None:
    stmt = select(Knowledge).where(
        Knowledge.knower_player_id == player_id,
        Knowledge.information_id == information_id,
        Knowledge.tenant_id == tenant_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


@router.put("/{information_id}/player-knowers/{player_id}")
async def add_information_player_knower(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    player_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> InformationOut:
    """Tells a player - the person's seat, not one of their characters -
    about an Information row: the write side of player knowledge ADR 0028's
    read side already honours. See ADR 0109. Identical in shape and gate to
    add_information_knower: idempotent, ADR 0101's edit gate, 200 +
    InformationOut, logged with ids only.
    """
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    await _require_player_exists(session, player_id, tenant_id)

    existing = await _get_player_knowledge_link(
        session, player_id=player_id, information_id=information_id, tenant_id=tenant_id
    )
    if existing is None:
        session.add(
            Knowledge(
                tenant_id=tenant_id, knower_player_id=player_id, information_id=information_id
            )
        )
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="information.knower_added",
            target_type="information",
            target_id=information_id,
            detail=f"player={player_id}",
        )
        information.updated_at = datetime.now(UTC)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await information_out_or_404(
        tenant_id, information_id, request, session, user=user, require_visible=False
    )


@router.delete("/{information_id}/player-knowers/{player_id}")
async def remove_information_player_knower(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    player_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> InformationOut:
    """Un-tells a player - see ADR 0109 and remove_information_knower,
    which this mirrors. Idempotent; 200 + the parent InformationOut."""
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )

    existing = await _get_player_knowledge_link(
        session, player_id=player_id, information_id=information_id, tenant_id=tenant_id
    )
    if existing is not None:
        await session.delete(existing)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="information.knower_removed",
            target_type="information",
            target_id=information_id,
            detail=f"player={player_id}",
        )
        information.updated_at = datetime.now(UTC)
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    return await information_out_or_404(
        tenant_id, information_id, request, session, user=user, require_visible=False
    )


@router.get("/{information_id}/knowers")
async def list_information_knowers(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> list[KnowerOut]:
    """Who has been told this: every knower of both kinds, oldest grant
    first - see ADR 0109. Gated like editing (ADR 0101), not like reading:
    who else knows a secret is itself a secret, so only callers who could
    grant it may list its knowers. Unpaginated - bounded by one row's
    grants.
    """
    information = await get_information_or_404(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    stmt = (
        select(
            Knowledge.knower_entity_id,
            Knowledge.knower_player_id,
            Knowledge.created_at,
            Entity.name.label("entity_name"),
            User.display_name,
            User.nickname,
        )
        .outerjoin(Entity, Entity.id == Knowledge.knower_entity_id)
        .outerjoin(Player, Player.id == Knowledge.knower_player_id)
        .outerjoin(User, User.id == Player.user_id)
        .where(Knowledge.information_id == information_id, Knowledge.tenant_id == tenant_id)
        .order_by(Knowledge.created_at, Knowledge.id)
    )
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    knowers: list[KnowerOut] = []
    for row in (await session.execute(stmt)).all():
        if row.knower_player_id is not None:
            knowers.append(
                KnowerOut(
                    kind="player",
                    player_id=row.knower_player_id,
                    name=row.display_name or row.nickname,
                    granted_at=row.created_at,
                )
            )
        else:
            knowers.append(
                KnowerOut(
                    kind="entity",
                    knower_entity_id=row.knower_entity_id,
                    name=row.entity_name
                    if visibility.can_see_entry(row.knower_entity_id)
                    else None,
                    granted_at=row.created_at,
                )
            )
    return knowers


async def audience_of(session: SessionDep, information: Information) -> InformationAudience:
    pairs = (
        await session.execute(
            select(Knowledge.knower_entity_id, Knowledge.knower_player_id).where(
                Knowledge.information_id == information.id,
                Knowledge.tenant_id == information.tenant_id,
            )
        )
    ).all()
    return InformationAudience(
        is_public=information.is_public,
        shared_with_participants=information.shared_with_participants,
        entity_ids=sorted((e for e, _ in pairs if e is not None), key=str),
        player_ids=sorted((p for _, p in pairs if p is not None), key=str),
    )


@router.get("/{information_id}/audience")
async def get_information_audience(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> InformationAudience:
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    response.headers["ETag"] = etag_for(information.updated_at)
    return await audience_of(session, information)


@router.put("/{information_id}/audience")
async def replace_information_audience(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    body: InformationAudience,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> InformationAudience:
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    if if_match is None:
        raise AudiencePreconditionRequiredError(
            detail="Read the audience and send its ETag as If-Match."
        )
    check_if_match(if_match, updated_at=information.updated_at)
    entities, players = set(body.entity_ids), set(body.player_ids)
    for model, wanted in ((Entity, entities), (Player, players)):
        if wanted:
            found = set(
                (
                    await session.execute(
                        select(model.id).where(model.tenant_id == tenant_id, model.id.in_(wanted))
                    )
                ).scalars()
            )
            if found != wanted:
                raise InvalidAudienceRecipientError(detail="Choose recipients from this library.")
    previous = await audience_of(session, information)
    shared = (
        body.shared_with_participants
        if "shared_with_participants" in body.model_fields_set
        else previous.shared_with_participants
    )
    if shared and await session.get(StoryEvent, information.entity_id) is None:
        raise InvalidAudienceRecipientError(
            detail="Only Event Information has a participant audience"
        )
    if (
        information.is_public != body.is_public
        or previous.shared_with_participants != shared
        or set(previous.entity_ids) != entities
        or set(previous.player_ids) != players
    ):
        links = (
            (
                await session.execute(
                    select(Knowledge).where(
                        Knowledge.tenant_id == tenant_id, Knowledge.information_id == information_id
                    )
                )
            )
            .scalars()
            .all()
        )
        for link in links:
            if (
                link.knower_entity_id is not None
                and link.knower_entity_id not in entities
                or link.knower_player_id is not None
                and link.knower_player_id not in players
            ):
                await session.delete(link)
        for recipient in entities - set(previous.entity_ids):
            session.add(
                Knowledge(
                    tenant_id=tenant_id, information_id=information_id, knower_entity_id=recipient
                )
            )
        for recipient in players - set(previous.player_ids):
            session.add(
                Knowledge(
                    tenant_id=tenant_id, information_id=information_id, knower_player_id=recipient
                )
            )
        information.is_public = body.is_public
        information.shared_with_participants = shared
        information.updated_at = datetime.now(UTC)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="information.visibility_changed",
            target_type="information",
            target_id=information_id,
            detail=f"public={body.is_public}; entities={len(entities)}; players={len(players)}",
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
        await session.refresh(information, ["updated_at", "is_public"])
    response.headers["ETag"] = etag_for(information.updated_at)
    return await audience_of(session, information)


@router.post("/{information_id}/texts", status_code=201)
async def append_information_text(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    body: PayloadTextCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> PayloadDescriptionOut:
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    if information.type == "main_picture":
        raise MainPictureThroughEntityError(
            detail="The main picture has its own single-picture editor."
        )
    replay = await payload_replay(
        session, tenant_id=tenant_id, information_id=information_id, payload_id=body.id
    )
    if replay is not None:
        if (
            replay.description is None
            or replay.description.content != body.content
            or replay.description.locale != body.locale
        ):
            raise PayloadReplayConflictError(
                detail="Choose a new payload id for different content."
            )
        response.status_code = 200
        response.headers["ETag"] = etag_for(information.updated_at)
        out = payload_to_schema(replay, request)
        assert isinstance(out, PayloadDescriptionOut)
        return out
    require_bundle_version(information, if_match)
    payload = Payload(tenant_id=tenant_id, information_id=information_id)
    if body.id is not None:
        payload.id = body.id
    await write_description(session, payload=payload, content=body.content, locale=body.locale)
    if body.id is not None:
        await insert_with_client_id(session, payload)
    else:
        await session.flush()
    touch_bundle(information)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    stored = await payload_replay(
        session, tenant_id=tenant_id, information_id=information_id, payload_id=payload.id
    )
    assert stored is not None
    response.headers["ETag"] = etag_for(information.updated_at)
    out = payload_to_schema(stored, request)
    assert isinstance(out, PayloadDescriptionOut)
    return out


@router.put("/{information_id}/payloads/order")
async def reorder_information_payloads(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    body: PayloadOrderRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> InformationOut:
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    if information.type == "main_picture":
        raise MainPictureThroughEntityError(
            detail="The main picture has its own single-picture editor."
        )
    require_bundle_version(information, if_match)
    if await replace_payload_order(session, information=information, wanted=body.payload_ids):
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    out = await information_out_or_404(
        tenant_id, information_id, request, session, user=user, require_visible=False
    )
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.get("/{information_id}/editor")
async def get_information_editor_snapshot(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> InformationOut:
    """The current bundle for an authorized editor, including a new private note awaiting grants.
    Ordinary GET retains its reader gate; this has exactly the existing edit/authorship gate.
    """
    information = await locked_information(session, information_id, tenant_id)
    await authorize_information_edit(
        session, tenant_id=tenant_id, user=user, information=information
    )
    response.headers["ETag"] = etag_for(information.updated_at)
    return InformationOut.from_information(information, request)
