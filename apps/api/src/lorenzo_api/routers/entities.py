import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Form, Header, Query, Request, Response, UploadFile
from fastapi_pagination import Page, paginate
from fastapi_pagination.ext.sqlalchemy import apaginate
from fastapi_problem.error import ForbiddenProblem
from pydantic import BaseModel
from sqlalchemy import delete, exists, func, literal, or_, select, union_all
from sqlalchemy.orm import joinedload, selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.author_guards import author_may_delete, author_may_touch, author_may_use_kinds
from lorenzo_api.campaign_access import (
    campaign_ids_for_character,
    can_author_entry,
    can_manage_any_campaign_in_tenant,
    can_manage_any_of_campaigns,
)
from lorenzo_api.client_ids import existing_in_tenant, insert_with_client_id
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_entity_or_404,
    get_tenant_context,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.description_payloads import write_description
from lorenzo_api.entity_access import (
    can_self_manage_entity,
    entity_id_among,
    prototype_descendants_cte,
)
from lorenzo_api.entity_kinds import (
    Kind,
    add_kind,
    create_entry,
    remove_kind,
    require_deletable,
)
from lorenzo_api.entity_parents import replace_parents
from lorenzo_api.entry_visibility import require_visible_entry, visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.event_fact_access import edits_event_fact, is_event_fact, manages_events
from lorenzo_api.exceptions import (
    AudiencePreconditionRequiredError,
    ClientIdUnavailableError,
    EntityNotFoundError,
    EntitySlugConflictError,
    EntitySlugManagementForbiddenError,
    EntitySlugNotFoundError,
    InformationAlreadyExistsError,
    InformationManagementForbiddenError,
    InformationNotFoundError,
    InformationOrderConflictError,
    InformationOrderListError,
    InvalidAudienceRecipientError,
    InvalidKindRequestError,
    InventoryItemParentsError,
)
from lorenzo_api.information_visibility import (
    InformationReader,
    InformationVisibility,
    resolve_information_reader,
    resolve_information_visibility,
    visible_information_clause,
)
from lorenzo_api.learning import require_no_learning
from lorenzo_api.models import (
    Being,
    Calendar,
    CalendarObservance,
    CalendarPeriod,
    Character,
    Clock,
    Containment,
    ContentReference,
    Entity,
    EntityAudience,
    EntityKnowledge,
    EntityPrototype,
    EntitySlug,
    Fact,
    FactAbout,
    Information,
    InformationType,
    Item,
    ItemInstance,
    Location,
    Map,
    Ownership,
    Payload,
    Player,
    StatDefinition,
    StoryEvent,
    User,
    VEffectiveStat,
    formula_load_options,
)
from lorenzo_api.models.story_session import Scene, SceneAppearance, StorySession
from lorenzo_api.my_links import (
    MY_HINT,
    MY_PREFIX,
    anchors_of,
    item_ancestor_slugs,
    pick_for_anchor,
)
from lorenzo_api.picture_payloads import add_picture_payload, read_picture_upload
from lorenzo_api.routers.item_instances import caller_reach
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import (
    BacklinkOut,
    EntityCreate,
    EntityDetailOut,
    EntityKind,
    EntityKindPut,
    EntityListOut,
    EntityParentsRequest,
    EntitySlugOut,
    EntitySlugUpdate,
    EntryKnowerOut,
    FactUpdate,
    InformationCreate,
    InformationOrderRequest,
    InformationOut,
    ResolvedSlugOut,
)
from lorenzo_api.schemas.knowledge import InformationAudience
from lorenzo_api.stat_contents import attach_contents

# get_tenant_or_404 here, not get_tenant_context (ADR 0038/RFC 0011,
# mirroring routers/item_instances.py's identical ADR 0032/RFC 0005
# precedent): a plain player authoring information about their own
# character's own item needs no tenant-wide Membership row (ADR 0022), so
# gating the whole router on one would lock them out of self-service
# entirely. The two pre-existing GET routes each re-add their own explicit
# require_tenant_participant check instead, preserving their original ADR
# 0020 behavior - only tenant participants (broader than Membership) reach
# them, same as routers/item_instances.py's identical revision. The new
# POST route uses self-or-managed authorization, narrower still.
router = APIRouter(
    prefix="/tenants/{tenant_id}/entities",
    tags=["entities"],
    dependencies=[Depends(get_tenant_or_404)],
)


# What an entry is: the marker rows it has (ADR 0012), in this order.
_KINDS: tuple[
    tuple[
        EntityKind,
        type[
            Item
            | ItemInstance
            | Being
            | Character
            | Fact
            | Calendar
            | Clock
            | Location
            | Map
            | CalendarPeriod
            | StoryEvent
            | CalendarObservance
            | Scene
            | SceneAppearance
            | StorySession
        ],
    ],
    ...,
] = (
    ("item", Item),
    ("item_instance", ItemInstance),
    ("being", Being),
    ("character", Character),
    ("fact", Fact),
    ("calendar", Calendar),
    ("clock", Clock),
    ("calendar_period", CalendarPeriod),
    ("event", StoryEvent),
    ("observance", CalendarObservance),
    ("scene", Scene),
    ("scene_appearance", SceneAppearance),
    ("session", StorySession),
    ("location", Location),
    ("map", Map),
)


async def parents_of(
    session: SessionDep,
    entity_ids: Sequence[uuid.UUID],
    visibility: InformationVisibility | None = None,
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """The direct parents of each of entity_ids, in their order (ADR 0266, ties by id), one query
    for all of them (ADR 0229): an entry with none has an empty list."""
    found: dict[uuid.UUID, list[uuid.UUID]] = {entity_id: [] for entity_id in entity_ids}
    if entity_ids:
        edges = (
            select(EntityPrototype.entity_id, EntityPrototype.prototype_id)
            .where(entity_id_among(EntityPrototype.entity_id, entity_ids))
            .order_by(
                EntityPrototype.entity_id,
                EntityPrototype.position,
                EntityPrototype.prototype_id,
            )
        )
        for entity_id, parent_id in (await session.execute(edges)).tuples():
            if visibility is None or visibility.can_see_entry(parent_id):
                found[entity_id].append(parent_id)
    return found


async def kinds_of(
    session: SessionDep, entity_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[EntityKind]]:
    """The kinds of each of entity_ids, in the order of `_KINDS`, one query for all of them: an
    entry that is none of them is a bare entry and has an empty list (ADR 0215)."""
    found: dict[uuid.UUID, set[EntityKind]] = {entity_id: set() for entity_id in entity_ids}
    if entity_ids:
        marked = union_all(
            *(
                select(model.entity_id.label("entity_id"), literal(kind).label("kind")).where(
                    entity_id_among(model.entity_id, entity_ids)
                )
                for kind, model in _KINDS
            )
        )
        for entity_id, kind in (await session.execute(marked)).tuples():
            found[entity_id].add(kind)
    return {
        entity_id: [kind for kind, _ in _KINDS if kind in has] for entity_id, has in found.items()
    }


@router.get("")
async def list_entities(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    q: Annotated[
        str | None,
        Query(description="Case-insensitive substring match against the entry's name."),
    ] = None,
    kind: Annotated[
        list[EntityKind] | None,
        Query(description="Only entries of these kinds (repeatable): any of them, not all."),
    ] = None,
    parent_id: Annotated[
        uuid.UUID | None,
        Query(description="Only entries that have this entry as a parent."),
    ] = None,
    recursive: Annotated[
        bool,
        Query(
            description=(
                "With parent_id, also include entries that inherit from it transitively, "
                "not just directly."
            )
        ),
    ] = False,
) -> Page[EntityListOut]:
    """Every entry of the tenant by name, then id, with what each is (`kinds`), narrowed by any
    of q, kind and parent_id (ADR 0215, RFC 0041 §5). EntityListOut rather than EntityDetailOut,
    to avoid an N+1-heavy response when listing many entities.

    q is a substring of the name, case-insensitive, with `%` and `_` meaning themselves. kind is
    repeatable and matches an entry that is any of the kinds given. parent_id lists the entries
    that name this one as a parent, and with recursive every descendant, as `prototype_id` and
    `recursive` do on GET /items (an unknown id, or one of another tenant, is a 404).
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    stmt = (
        select(Entity)
        .where(Entity.tenant_id == tenant_id, visible_entry_clause(visibility, Entity.id))
        .order_by(Entity.name, Entity.id)
    )
    if q is not None:
        stmt = stmt.where(Entity.name.icontains(q, autoescape=True))
    if kind:
        wanted = set(kind)
        stmt = stmt.where(
            or_(
                *(
                    exists().where(model.entity_id == Entity.id)
                    for k, model in _KINDS
                    if k in wanted
                )
            )
        )
    if parent_id is not None:
        await get_entity_or_404(session, parent_id, tenant_id)
        if recursive:
            descendants = prototype_descendants_cte(parent_id, tenant_id)
            stmt = stmt.where(Entity.id.in_(select(descendants.c.descendant_id)))
        else:
            stmt = stmt.where(
                exists().where(
                    EntityPrototype.entity_id == Entity.id,
                    EntityPrototype.prototype_id == parent_id,
                    EntityPrototype.tenant_id == tenant_id,
                )
            )

    async def _rows(entities: Sequence[Entity]) -> list[EntityListOut]:
        ids = [entity.id for entity in entities]
        kinds = await kinds_of(session, ids)
        parents = await parents_of(session, ids, visibility)
        return [
            EntityListOut(
                id=entity.id,
                name=entity.name,
                kinds=kinds[entity.id],
                parent_ids=parents[entity.id],
            )
            for entity in entities
        ]

    page: Page[EntityListOut] = await apaginate(session, stmt, params, transformer=_rows)
    return page


@router.post("", status_code=201)
async def create_entity(
    tenant_id: uuid.UUID,
    body: EntityCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> EntityDetailOut:
    """Makes an entry whatever it is (ADR 0217, RFC 0041 section 2): the entry, its link name, its
    kinds (`item`, `being`, both, or none for a bare entry) and its parents, in one transaction.
    The gate is the one `POST /items` has, a member of the library. `409` for a link name already
    taken, `422` for a parent that is not an entry of the library. An inventory item and a
    character are not made here: an inventory item is made from a catalog item, a being becomes a
    character through `PUT /characters/{id}`.

    A body with an `id` makes the entry under that id (ADR 0222): if the library already has an
    entry with it, the create was already done, and that entry is returned with `200` and nothing
    is written; an id that is taken by something the caller cannot see is a generic `409`.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    if (
        body.id is not None
        and (await existing_in_tenant(session, Entity, body.id, tenant_id)) is not None
    ):
        try:
            out = await entity_detail_out(
                session, request, tenant_id=tenant_id, entity_id=body.id, user=user
            )
        except EntityNotFoundError:
            raise ClientIdUnavailableError(detail="That id is not available.") from None
        response.status_code = 200
        response.headers["Location"] = str(
            request.url_for("get_entity", tenant_id=tenant_id, entity_id=body.id)
        )
        response.headers["ETag"] = etag_for(out.updated_at)
        return out
    kinds = sorted(set(body.kinds))
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    if not kinds or not set(kinds) <= {"event", "fact"}:
        await get_tenant_context(tenant_id, session, user)
    await author_may_use_kinds(session, tenant_id=tenant_id, user_id=user.id, kinds=kinds)
    entity = await create_entry(
        session,
        tenant_id=tenant_id,
        user_id=user.id,
        name=body.name,
        slug=body.slug,
        kinds=kinds,
        parents=body.parents,
        in_public_catalog=bool(body.in_public_catalog),
        entity_id=body.id,
    )
    if body.visibility is not None:
        audience = await session.get(EntityAudience, entity.id)
        assert audience is not None
        audience.is_public = body.visibility == "library"
        audience.shared_with_participants = body.visibility == "participants"
        await session.flush()
    if "fact" in kinds or "event" in kinds:
        try:
            await require_visible_entry(
                session, entity_id=entity.id, tenant_id=tenant_id, user_id=user.id
            )
        except EntityNotFoundError:
            raise InformationManagementForbiddenError(
                detail="A new fact starts restricted; your current roles do not let you read it."
            ) from None
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="entity.created",
        target_type="entity",
        target_id=entity.id,
        detail=f"kinds={'+'.join(kinds) or 'none'},parents={len(set(body.parents))}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    out = await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity.id, user=user
    )
    response.headers["Location"] = str(
        request.url_for("get_entity", tenant_id=tenant_id, entity_id=entity.id)
    )
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.put("/{entity_id}/kinds/{kind}", dependencies=[Depends(get_tenant_context)])
async def add_entity_kind(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    kind: Kind,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    body: EntityKindPut | None = None,
    if_match: Annotated[str | None, Header()] = None,
) -> EntityDetailOut:
    """Gives the entry a kind (ADR 0217): `201` the first time, `200` when it already had it, as
    `PUT /characters/{id}` does. `item` may carry its own column, `in_public_catalog`. An
    inventory item never takes `item` (`409`); it may take `being`. Touches the entry, so its
    ETag moves, and is one activity entry. Both honour `If-Match`.
    """
    entity = await get_entity_or_404(session, entity_id, tenant_id)
    await author_may_touch(session, tenant_id=tenant_id, user_id=user.id, entity_id=entity_id)
    await author_may_use_kinds(session, tenant_id=tenant_id, user_id=user.id, kinds=[kind])
    check_if_match(if_match, updated_at=entity.updated_at)
    in_public_catalog = body.in_public_catalog if body is not None else None
    if in_public_catalog is not None and kind != "item":
        raise InvalidKindRequestError(detail=f"in_public_catalog is a column of item, not {kind}")
    system = body.system if body is not None else None
    if system is not None and kind != "map":
        raise InvalidKindRequestError(detail=f"system is a column of map, not {kind}")
    result = await add_kind(
        session,
        tenant_id=tenant_id,
        entity=entity,
        kind=kind,
        user_id=user.id,
        in_public_catalog=in_public_catalog,
        system=system,
    )
    if result != "unchanged":
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="entity.kind_added",
            target_type="entity",
            target_id=entity_id,
            detail=f"kind={kind}",
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    out = await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity_id, user=user
    )
    response.status_code = 201 if result == "created" else 200
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.delete("/{entity_id}/kinds/{kind}", dependencies=[Depends(get_tenant_context)])
async def remove_entity_kind(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    kind: Kind,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntityDetailOut:
    """Takes a kind away from the entry and answers `200` with the entry, which survives
    (ADR 0217), whether or not it had the kind. `409` for `item` while an inventory item inherits
    from the entry directly, and for `being` while the entry is a character: demote it first.
    Honours `If-Match`, touches the entry and is one activity entry.
    """
    entity = await get_entity_or_404(session, entity_id, tenant_id)
    await author_may_touch(session, tenant_id=tenant_id, user_id=user.id, entity_id=entity_id)
    await author_may_use_kinds(session, tenant_id=tenant_id, user_id=user.id, kinds=[kind])
    check_if_match(if_match, updated_at=entity.updated_at)
    removed = await remove_kind(
        session, tenant_id=tenant_id, entity=entity, kind=kind, user_id=user.id
    )
    if removed:
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="entity.kind_removed",
            target_type="entity",
            target_id=entity_id,
            detail=f"kind={kind}",
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    out = await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity_id, user=user
    )
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.delete("/{entity_id}", status_code=204, dependencies=[Depends(get_tenant_context)])
async def delete_entity(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> None:
    """Deletes the entry, with the guards of every kind it has composed (ADR 0217, RFC 0041
    section 2): `409` for an inventory item (its own route moves what it holds back out), a
    character (demote it first), a campaign's own entry, and a catalog item an inventory item
    inherits from. An entry that is also a being goes with its being; the kind-specific deletes
    keep working and delete the whole entry as they do now. Nothing a library copied is touched:
    it sees the entry as removed upstream.
    """
    entity = await get_entity_or_404(session, entity_id, tenant_id)
    await author_may_delete(session, tenant_id=tenant_id, user_id=user.id, entity_id=entity_id)
    check_if_match(if_match, updated_at=entity.updated_at)
    kinds = await require_deletable(session, tenant_id=tenant_id, entity_id=entity_id)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="entity.deleted",
        target_type="entity",
        target_id=entity_id,
        detail=f"kinds={'+'.join(sorted(kinds)) or 'none'}",
    )
    await session.delete(entity)
    await session.commit()


async def get_entity_detail_or_404(
    session: SessionDep, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> Entity:
    """The full .options() eager-load chain EntityDetailOut needs - factored
    out of get_entity below so routers/entity_stats.py's stat-write endpoint
    (ADR 0037/RFC 0008) can return this same canonical entity-detail shape
    after a write, rather than keeping a second, drifting copy of this
    seven-relationship chain (mirrors routers/items.py's own
    eager_load_options, reused as-is by routers/item_instances.py).

    Not dependencies.get_entity_or_404 - that helper's plain session.get()
    wouldn't have any of these relationships loaded, so reusing it here
    would just mean a second, redundant round trip for this same row. The
    404 check below covers exactly what that helper covers (missing id, or
    an id that belongs to a different tenant).
    """
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id)
    stmt = (
        select(Entity)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .options(
            # The entity's own rows, so each stat can say whether it's own (ADR 0111).
            selectinload(Entity.stats),
            selectinload(Entity.effective_stats)
            .joinedload(VEffectiveStat.stat_definition)
            .joinedload(StatDefinition.stat_group),
            # Where an inherited value comes from (ADR 0276).
            selectinload(Entity.effective_stats).joinedload(VEffectiveStat.source_entity),
            # A winning formula's parameters, for stat_evaluation (ADR 0104).
            *formula_load_options(
                selectinload(Entity.effective_stats).selectinload(VEffectiveStat.computed_stat)
            ),
            selectinload(Entity.stat_groups),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .joinedload(Payload.description),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .joinedload(Payload.number),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .joinedload(Payload.picture),
            selectinload(Entity.information)
            .selectinload(Information.payloads)
            .joinedload(Payload.document),
            selectinload(Entity.information).selectinload(Information.knowledge_links),
            # Who wrote each (ADR 0277).
            selectinload(Entity.information).joinedload(Information.author),
            selectinload(Entity.prototypes),
            selectinload(Entity.instances),
            # ADR 0041: Entity.containment/contained_links (the Containment
            # association-object relationships), not Entity.parent/children
            # (the bare Entity lists) - only the former carry the per-edge
            # quantity column EntityDetailOut.parent/quantity/children now
            # need.
            joinedload(Entity.containment).joinedload(Containment.parent),
            selectinload(Entity.contained_links).joinedload(Containment.child),
            joinedload(Entity.slug),
            # What the entry is (ADR 0217).
            joinedload(Entity.scene),
            joinedload(Entity.scene_appearance),
            joinedload(Entity.story_session),
            joinedload(Entity.fact),
            joinedload(Entity.calendar),
            joinedload(Entity.clock),
            joinedload(Entity.location),
            joinedload(Entity.map),
            joinedload(Entity.calendar_period),
            joinedload(Entity.calendar_observance),
            joinedload(Entity.story_event),
            joinedload(Entity.item),
            joinedload(Entity.item_instance),
            joinedload(Entity.being).joinedload(Being.character),
        )
    )
    entity = await session.scalar(stmt)
    if entity is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    # What a contents formula reads (ADR 0127).
    await attach_contents(session, [entity], tenant_id=tenant_id)
    return entity


async def entity_detail_reader(
    session: SessionDep, *, entity: Entity, user_id: uuid.UUID, tenant_id: uuid.UUID
) -> InformationReader:
    related = {
        entity.id,
        *(e.id for e in entity.prototypes),
        *(e.id for e in entity.instances),
        *(link.child_entity_id for link in entity.contained_links),
        *(stat.source_entity_id for stat in entity.effective_stats),
    }
    if entity.containment is not None:
        related.add(entity.containment.parent_entity_id)
    return await resolve_information_reader(
        session,
        user_id=user_id,
        tenant_id=tenant_id,
        information=entity.information,
        entry_ids=related,
    )


async def entity_detail_out(
    session: SessionDep,
    request: Request,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user: CurrentUser,
) -> EntityDetailOut:
    """What GET /{entity_id} and GET /by-slug/{slug} both return, the caller
    already past require_tenant_participant."""
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    entity = await get_entity_detail_or_404(session, entity_id, tenant_id)
    # Who may read the entity's information, as far as `can_see` needs it (ADR 0285).
    reader = await entity_detail_reader(
        session, entity=entity, user_id=user.id, tenant_id=tenant_id
    )
    return EntityDetailOut.from_entity(entity, request, visibility=reader)


# Registered before /{entity_id}: that route's path would otherwise match
# "resolve" and "by-slug" as an entity id (ADR 0043's routing-order note).
@router.get("/resolve")
async def resolve_slugs(
    tenant_id: uuid.UUID,
    slug: Annotated[list[str], Query(min_length=1, max_length=100)],
    session: SessionDep,
    user: CurrentUser,
    home: Annotated[
        uuid.UUID | None,
        Query(
            alias="from",
            description=(
                "The entity the text belongs to. `my/SLUG` slugs resolve against the being "
                "it belongs to (ADR 0240); without it they are absent."
            ),
        ),
    ] = None,
) -> list[ResolvedSlugOut]:
    """Every slug a LorenzoScript text names, in one request (ADR 0107, RFC
    0027 §7). Same gate as GET /{entity_id}, so a slug resolves for exactly
    the readers who could open its entity. Slugs that don't resolve are
    simply absent: a missing entity and a hidden one look alike.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    asked = list(dict.fromkeys(slug))
    mine = [name for name in asked if name.startswith(MY_PREFIX)]
    # What each asked name stands for: the entity holding the slug, or for a
    # `my/` name, the entity it means for the being the text belongs to.
    stands_for: dict[str, uuid.UUID] = {}
    by_slug = {
        name: entity_id
        for name, entity_id in (
            await session.execute(
                select(EntitySlug.slug, EntitySlug.entity_id).where(
                    EntitySlug.tenant_id == tenant_id,
                    EntitySlug.slug.in_(
                        [n for n in asked if n not in mine] + [n[len(MY_PREFIX) :] for n in mine]
                    ),
                )
            )
        ).tuples()
    }
    stands_for.update({n: by_slug[n] for n in asked if n not in mine and n in by_slug})
    if mine and home is not None:
        anchor = (await anchors_of(session, tenant_id=tenant_id, home_ids=[home]))[home]
        if anchor is not None:
            visibility = await resolve_information_visibility(
                session, user_id=user.id, tenant_id=tenant_id
            )
            picks = await pick_for_anchor(
                session,
                tenant_id=tenant_id,
                anchor_id=anchor,
                targets=[
                    by_slug[n[len(MY_PREFIX) :]] for n in mine if n[len(MY_PREFIX) :] in by_slug
                ],
                reach=await caller_reach(
                    session, tenant_id=tenant_id, user=user, visibility=visibility
                ),
            )
            for n in mine:
                target = by_slug.get(n[len(MY_PREFIX) :])
                if target is not None and target in picks:
                    stands_for[n] = picks[target]
    if not stands_for:
        return []
    kinds = [exists().where(model.entity_id == Entity.id).label(kind) for kind, model in _KINDS]
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    stmt = select(Entity.id, Entity.name, *kinds).where(
        Entity.tenant_id == tenant_id,
        Entity.id.in_(set(stands_for.values())),
        visible_entry_clause(visibility, Entity.id),
    )
    found = {row["id"]: row for row in (await session.execute(stmt)).mappings()}
    return [
        ResolvedSlugOut(
            slug=name,
            entity_id=entity_id,
            name=found[entity_id]["name"],
            kinds=[kind for kind, _ in _KINDS if found[entity_id][kind]],
        )
        for name in asked
        if (entity_id := stands_for.get(name)) is not None and entity_id in found
    ]


@router.get("/by-slug/{slug}")
async def get_entity_by_slug(
    tenant_id: uuid.UUID,
    slug: str,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> EntityDetailOut:
    """GET /{entity_id}, addressed by slug (ADR 0107)."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    entity_id = await session.scalar(
        select(EntitySlug.entity_id).where(
            EntitySlug.tenant_id == tenant_id, EntitySlug.slug == slug
        )
    )
    if entity_id is None:
        raise EntitySlugNotFoundError(detail=f"No entity with slug {slug!r} in tenant {tenant_id}")
    out = await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity_id, user=user
    )
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.get("/{entity_id}")
async def get_entity(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> EntityDetailOut:
    """The full detail shape, with every relationship eager-loaded up front."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    out = await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity_id, user=user
    )
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


async def _my_backlinks(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    slug: str | None,
    user: CurrentUser,
    visibility: InformationVisibility,
) -> set[uuid.UUID]:
    """The information whose `my/` links mean this item instance (ADR 0240):
    a `my/SLUG` where SLUG is the instance's own slug or that of an item it
    derives from, in a text whose being picks this instance for it. Only an
    instance can be meant, and a catalog item is not mentioned by it.
    """
    if not await session.scalar(select(exists().where(ItemInstance.entity_id == entity_id))):
        return set()
    names = await item_ancestor_slugs(session, tenant_id=tenant_id, entity_id=entity_id)
    by_slug = {name: item_id for item_id, name in names.items()}
    if slug is not None:
        by_slug[slug] = entity_id
    rows = (
        await session.execute(
            select(Payload.information_id, Information.entity_id, ContentReference.target)
            .join(ContentReference, ContentReference.payload_id == Payload.id)
            .join(Information, Information.id == Payload.information_id)
            .where(
                ContentReference.tenant_id == tenant_id,
                ContentReference.kind.in_(("entity", "image")),
                ContentReference.hint == MY_HINT,
                ContentReference.target.in_(list(by_slug)),
                Information.entity_id != entity_id,
            )
        )
    ).tuples()
    texts = list(rows)
    if not texts:
        return set()
    anchors = await anchors_of(
        session, tenant_id=tenant_id, home_ids={home for _, home, _ in texts}
    )
    reach = await caller_reach(session, tenant_id=tenant_id, user=user, visibility=visibility)
    picked: dict[tuple[uuid.UUID, str], uuid.UUID | None] = {}
    for _, home, target in texts:
        anchor = anchors[home]
        if anchor is None or (anchor, target) in picked:
            continue
        picks = await pick_for_anchor(
            session, tenant_id=tenant_id, anchor_id=anchor, targets=[by_slug[target]], reach=reach
        )
        picked[(anchor, target)] = picks.get(by_slug[target])
    return {
        information_id
        for information_id, home, target in texts
        if (anchor := anchors[home]) is not None and picked[(anchor, target)] == entity_id
    }


@router.get("/{entity_id}/backlinks")
async def list_backlinks(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    params: ParamsDep,
) -> Page[BacklinkOut]:
    """What links here (ADR 0110): each piece of information whose
    description names this entity's slug, in a link or a picture. Same gate
    as GET /{entity_id}, then only information the caller can see - filtered
    before paging, so pages are full and `total` counts nothing hidden. The
    entity's own information isn't listed.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await get_entity_or_404(session, entity_id, tenant_id)
    slug = await session.scalar(
        select(EntitySlug.slug).where(
            EntitySlug.tenant_id == tenant_id, EntitySlug.entity_id == entity_id
        )
    )
    backlinks: list[BacklinkOut] = []
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    linking: set[uuid.UUID] = set()
    if slug is not None:
        linking.update(
            (
                await session.execute(
                    select(Payload.information_id)
                    .join(ContentReference, ContentReference.payload_id == Payload.id)
                    .where(
                        ContentReference.tenant_id == tenant_id,
                        ContentReference.kind.in_(("entity", "image")),
                        ContentReference.target == slug,
                        ContentReference.hint != MY_HINT,
                    )
                )
            ).scalars()
        )
    linking.update(
        await _my_backlinks(
            session,
            tenant_id=tenant_id,
            entity_id=entity_id,
            slug=slug,
            user=user,
            visibility=visibility,
        )
    )
    if linking:
        kinds = [exists().where(model.entity_id == Entity.id).label(kind) for kind, model in _KINDS]
        stmt = (
            select(Information, Entity.name, *kinds)
            .join(Entity, Entity.id == Information.entity_id)
            .where(Information.id.in_(linking), Information.entity_id != entity_id)
            .options(selectinload(Information.knowledge_links))
            .order_by(Entity.name, Information.order, Information.id)
        )
        for info, name, *flags in (await session.execute(stmt)).tuples():
            if visibility.can_see(info):
                backlinks.append(
                    BacklinkOut(
                        entity_id=info.entity_id,
                        name=name,
                        kinds=[kind for (kind, _), flag in zip(_KINDS, flags, strict=True) if flag],
                        information_id=info.id,
                        title=info.title,
                        type=info.type,
                    )
                )
    # paginate is typed to return Any (fastapi_pagination's own signature).
    return cast(Page[BacklinkOut], paginate(backlinks, params))


@router.put("/{entity_id}/parents", dependencies=[Depends(get_tenant_context)])
async def replace_entity_parents(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: EntityParentsRequest,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntityDetailOut:
    """Replaces the entry's own direct parents (ADR 0216, RFC 0041 §3): the list becomes the
    complete set, an empty list clears it, as PUT /items/{id}/prototypes does for an item, whose
    route runs the same code. Works for an item, a being, a character and a bare entry. A change
    touches the entry (`updated_by`, so its ETag) and is one activity entry; the same set again
    changes and logs nothing.

    The gate is the one the item route has: a member of the library. 404 for an unknown entry, 412
    for a stale If-Match, 409 for an inventory item (its one parent changes through PATCH
    /item-instances/{id}, ADR 0192), 422 for itself, an id that is not an entry of the library, or
    a loop. Nothing inherited is stored, so nothing else changes: stats and descriptions resolve
    through the new parents the next time they are read (ADR 0037, 0111).
    """
    entity = await get_entity_or_404(session, entity_id, tenant_id)
    await author_may_touch(session, tenant_id=tenant_id, user_id=user.id, entity_id=entity_id)
    check_if_match(if_match, updated_at=entity.updated_at)
    if await session.get(ItemInstance, entity_id) is not None:
        raise InventoryItemParentsError(
            detail=(
                f"Entry {entity_id} is an inventory item: change its parent with "
                f"PATCH /tenants/{tenant_id}/item-instances/{entity_id}"
            )
        )
    changed = await replace_parents(
        session,
        tenant_id=tenant_id,
        entity=entity,
        parent_ids=body.parent_ids,
        user_id=user.id,
    )
    if changed:
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="entity.parents_replaced",
            target_type="entity",
            target_id=entity_id,
            detail=f"parents={len(set(body.parent_ids))}",
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    out = await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity_id, user=user
    )
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.put("/{entity_id}/slug")
async def set_entity_slug(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: EntitySlugUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> EntitySlugOut:
    """Sets or replaces the entity's one slug (ADR 0107). 404 for an unknown
    entity, then the same self-or-managed tier as authoring its information
    (403), then 409 if another entity in the tenant already has the slug.
    Setting the entity's current slug again changes nothing.
    """
    await get_entity_or_404(session, entity_id, tenant_id)
    await authorize_entity_write(
        session,
        tenant_id=tenant_id,
        user=user,
        entity_id=entity_id,
        forbidden=EntitySlugManagementForbiddenError(
            detail=f"Not authorized to manage the slug of entity {entity_id}"
        ),
    )
    holder = await session.scalar(
        select(EntitySlug.entity_id).where(
            EntitySlug.tenant_id == tenant_id, EntitySlug.slug == body.slug
        )
    )
    if holder is not None and holder != entity_id:
        raise EntitySlugConflictError(
            detail=f"Slug {body.slug!r} is already in use in tenant {tenant_id}"
        )
    current = await session.get(EntitySlug, entity_id)
    if current is None:
        session.add(EntitySlug(entity_id=entity_id, tenant_id=tenant_id, slug=body.slug))
    else:
        current.slug = body.slug
    await session.commit()
    return EntitySlugOut(entity_id=entity_id, slug=body.slug)


@router.delete("/{entity_id}/slug", status_code=204)
async def clear_entity_slug(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    """Clears the entity's slug, if it has one (ADR 0107): 204 either way,
    like this API's other idempotent sub-resource DELETEs (ADR 0064)."""
    await get_entity_or_404(session, entity_id, tenant_id)
    await authorize_entity_write(
        session,
        tenant_id=tenant_id,
        user=user,
        entity_id=entity_id,
        forbidden=EntitySlugManagementForbiddenError(
            detail=f"Not authorized to manage the slug of entity {entity_id}"
        ),
    )
    await session.execute(
        delete(EntitySlug).where(
            EntitySlug.entity_id == entity_id, EntitySlug.tenant_id == tenant_id
        )
    )
    await session.commit()


# A to-one relationship is joined into the query of what has it (ADR 0285).
_INFORMATION_LOAD_OPTIONS = (
    selectinload(Information.payloads).joinedload(Payload.description),
    selectinload(Information.payloads).joinedload(Payload.number),
    selectinload(Information.payloads).joinedload(Payload.picture),
    selectinload(Information.payloads).joinedload(Payload.document),
    selectinload(Information.knowledge_links),
    # Who wrote it (ADR 0277).
    joinedload(Information.author),
)


@router.get("/{entity_id}/information")
async def list_entity_information(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    type_: Annotated[
        list[str] | None,
        Query(alias="type", description="Only these Information.type values (repeatable)."),
    ] = None,
    category: Annotated[
        Literal["technical", "gm_authored"] | None,
        Query(
            description=(
                "technical: types with an information_type row; "
                "gm_authored: free-form types, which never have one."
            )
        ),
    ] = None,
) -> Page[InformationOut]:
    """An entity's information, paged, in `order` - see ADR 0109/RFC 0015.
    Reachable by the same callers as GET /entities/{id} (tenant
    participants), filtered to what the caller can see - in SQL, before
    pagination (information_visibility.visible_information_clause), so a
    page is never short and its total never counts rows the caller can't
    see.
    """
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    entity_stmt = select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    if (await session.execute(entity_stmt)).first() is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)

    stmt = (
        select(Information)
        .where(
            Information.entity_id == entity_id,
            Information.tenant_id == tenant_id,
            visible_information_clause(visibility),
        )
        .options(*_INFORMATION_LOAD_OPTIONS)
        .order_by(Information.order, Information.id)
    )
    if type_:
        stmt = stmt.where(Information.type.in_(type_))
    if category is not None:
        catalogued = (
            select(InformationType.name).where(InformationType.name == Information.type).exists()
        )
        stmt = stmt.where(catalogued if category == "technical" else ~catalogued)

    page: Page[InformationOut] = await apaginate(
        session,
        stmt,
        params,
        transformer=lambda rows: [InformationOut.from_information(row, request) for row in rows],
    )
    return page


async def authorize_entity_write(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    user: CurrentUser,
    entity_id: uuid.UUID,
    forbidden: ForbiddenProblem | None = None,
) -> None:
    """RFC 0011/ADR 0038's self-or-managed tier for authoring Information/
    Payload on an entity, and for granting/revoking a Knowledge row about
    one (routers/information.py, which imports this directly rather than
    keeping a second copy) - the identical shape routers/entity_stats.py's
    own _authorize_entity_stat_write already established for RFC 0008/ADR
    0037 (self-service if reachable from the caller's own characters;
    otherwise the current Ownership-owner's own campaign(s) need
    can_manage_campaign; an unowned entity falls back to
    can_manage_any_campaign_in_tenant). Duplicated here rather than
    extracted into entity_access.py - this is now the third copy of this
    exact shape (item_instances.py, entity_stats.py, here), a reasonable
    candidate for a future shared `entity_access.can_manage_entity`
    helper, not done speculatively as part of this ADR. Not private (no
    leading underscore), unlike this router's other single-file-scoped
    helpers - matching entity_access.recursive_descendants_cte's own
    precedent for a name genuinely meant to be imported elsewhere.

    `forbidden` is what to raise instead of InformationManagementForbiddenError,
    for a write that isn't about information (an entity's slug, ADR 0107).
    """
    from lorenzo_api.session_access import manages_planning_entry, planning_entry

    if await planning_entry(session, tenant_id, entity_id):
        if await manages_planning_entry(session, tenant_id, entity_id, user.id):
            return
        raise forbidden or InformationManagementForbiddenError(
            detail="Only this Session's GMs can edit its preparation"
        )
    if await is_event_fact(session, tenant_id=tenant_id, entity_id=entity_id):
        if await edits_event_fact(
            session, tenant_id=tenant_id, user_id=user.id, entity_id=entity_id
        ):
            return
        raise forbidden or InformationManagementForbiddenError(
            detail="Only an Event/Fact manager or its creator can edit this entry"
        )
    if await can_self_manage_entity(
        session, entity_id=entity_id, user_id=user.id, tenant_id=tenant_id
    ):
        return
    owner_stmt = select(Ownership.owner_character_id).where(
        Ownership.owned_entity_id == entity_id, Ownership.tenant_id == tenant_id
    )
    current_owner_id = (await session.execute(owner_stmt)).scalar_one_or_none()
    if current_owner_id is not None:
        campaign_ids = await campaign_ids_for_character(
            session, character_entity_id=current_owner_id, tenant_id=tenant_id
        )
        if campaign_ids and await can_manage_any_of_campaigns(
            session, user_id=user.id, campaign_ids=campaign_ids, tenant_id=tenant_id
        ):
            return
    elif await can_manage_any_campaign_in_tenant(
        session, user_id=user.id, tenant_id=tenant_id
    ) or await can_author_entry(session, user_id=user.id, tenant_id=tenant_id, entity_id=entity_id):
        return
    raise forbidden or InformationManagementForbiddenError(
        detail=f"Not authorized to manage information on entity {entity_id}"
    )


async def lock_entity_information(
    session: SessionDep, *, entity_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    """Row-locks the entity (SELECT ... FOR UPDATE) for the rest of the
    transaction - ADR 0101. Every singleton-type check and `order`
    assignment on an entity's information runs under this lock, so two
    concurrent writers can't both pass a pre-check and then collide on the
    unique index/constraint (a 500 instead of a 409).
    """
    await session.execute(
        select(Entity.id)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .with_for_update()
    )


async def require_singleton_type_free(
    session: SessionDep,
    *,
    entity_id: uuid.UUID,
    tenant_id: uuid.UUID,
    type_: str,
    exclude_information_id: uuid.UUID | None = None,
) -> None:
    """409 if `type_` is a singleton type (information_type.is_singleton,
    ADR 0101) the entity already holds - other types repeat freely.
    `exclude_information_id` is the row being PATCHed, which may keep its
    own type.
    """
    is_singleton = await session.scalar(
        select(InformationType.is_singleton).where(InformationType.name == type_)
    )
    if not is_singleton:
        return
    stmt = select(Information.id).where(
        Information.entity_id == entity_id,
        Information.type == type_,
        Information.tenant_id == tenant_id,
    )
    if exclude_information_id is not None:
        stmt = stmt.where(Information.id != exclude_information_id)
    if (await session.execute(stmt)).first() is not None:
        raise InformationAlreadyExistsError(
            detail=f"Entity {entity_id} already has information of type {type_!r}"
        )


async def require_information_order_free(
    session: SessionDep, *, entity_id: uuid.UUID, tenant_id: uuid.UUID, order: int
) -> None:
    stmt = select(Information.id).where(
        Information.entity_id == entity_id,
        Information.order == order,
        Information.tenant_id == tenant_id,
    )
    if (await session.execute(stmt)).first() is not None:
        raise InformationOrderConflictError(
            detail=f"Entity {entity_id} already has information at position {order}"
        )


@router.post("/{entity_id}/information", status_code=201)
async def create_information(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: InformationCreate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> InformationOut:
    """One transaction creates Information + Payload + PayloadDescription -
    see ADR 0038/RFC 0011. `entity_id` existence is checked first (404,
    non-enumerable), then self-or-managed authorization (403 - the caller
    already knows the entity exists, they just lack a specific write
    permission over it), then - under the entity's row lock (ADR 0101) - a
    duplicate *singleton* `type` (409) and a taken explicit `order` (409),
    pre-checked explicitly rather than relying on the constraint violation
    to surface, matching MembershipAlreadyExistsError/
    PlayerAlreadyExistsError's own established precedent (ADR 0036), then
    the write itself. The description text goes through
    description_payloads.write_description, the one write path for it.
    """
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    entity_stmt = select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    if (await session.execute(entity_stmt)).first() is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")

    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    from lorenzo_api.session_access import manages_planning_entry, planning_entry

    session_note = await planning_entry(session, tenant_id, entity_id)
    collaborative = session_note or await is_event_fact(
        session, tenant_id=tenant_id, entity_id=entity_id
    )
    if collaborative:
        if not (
            await manages_planning_entry(session, tenant_id, entity_id, user.id)
            if session_note
            else await manages_events(session, tenant_id=tenant_id, user_id=user.id)
        ) and (body.type != "note" or body.order is not None):
            raise InformationManagementForbiddenError(detail="Readers can append their own notes")
    else:
        await authorize_entity_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    if body.id is not None:
        # An id the client chose (ADR 0222): already made on this entry means the create was
        # done; the same id on another entry, or one the caller cannot see, is a generic 409.
        known = await existing_in_tenant(session, Information, body.id, tenant_id)
        if known is not None:
            if known.entity_id != entity_id or (collaborative and known.created_by != user.id):
                raise ClientIdUnavailableError(detail="That id is not available.")
            response.status_code = 200
            response.headers["Location"] = str(
                request.url_for("get_information", tenant_id=tenant_id, information_id=body.id)
            )
            return await information_out_or_404(
                tenant_id, body.id, request, session, user=user, require_visible=False
            )

    await lock_entity_information(session, entity_id=entity_id, tenant_id=tenant_id)
    await require_singleton_type_free(
        session, entity_id=entity_id, tenant_id=tenant_id, type_=body.type
    )
    if body.order is not None:
        await require_information_order_free(
            session, entity_id=entity_id, tenant_id=tenant_id, order=body.order
        )

    information = Information(
        tenant_id=tenant_id,
        entity_id=entity_id,
        title=body.title,
        type=body.type,
        is_public=body.is_public,
        created_by=user.id,
    )
    # Left unset, the database's BEFORE INSERT trigger appends it after the
    # entity's last row (ADR 0101), serialized by the lock taken above. Not
    # passed as order=None: an explicit None would be sent as NULL and not
    # read back from the INSERT's RETURNING.
    if body.order is not None:
        information.order = body.order
    if body.id is None:
        session.add(information)
        await session.flush()
    else:
        information.id = body.id
        await insert_with_client_id(session, information)
    payload = Payload(tenant_id=tenant_id, information_id=information.id)
    await write_description(session, payload=payload, content=body.content, locale=body.locale)
    # Entity and visibility tier only - never the title, type, or content,
    # since a GM-only secret must not be readable from the activity log
    # (ADR 0084).
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="information.created",
        target_type="information",
        target_id=information.id,
        detail=f"entity={entity_id}, visibility={'public' if body.is_public else 'restricted'}",
    )

    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_information", tenant_id=tenant_id, information_id=information.id)
    )
    return await information_out_or_404(
        tenant_id, information.id, request, session, user=user, require_visible=False
    )


@router.put("/{entity_id}/information/order")
async def reorder_entity_information(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: InformationOrderRequest,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> list[InformationOut]:
    """Puts the entry's information in a new order in one request (ADR 0237, K8 of RFC 0041; the
    reorder ADR 0101 and RFC 0015 left open). The body lists every piece of information the
    caller can see on the entry, each once, in the order wanted; anything else is a 409 (a note
    added meanwhile, one removed, one named twice), and the caller reads the entry again. There
    is no `If-Match`: naming every row is the check. Information the caller cannot see keeps its
    own position, so a player reorders only their view and a GM everything.

    The positions the visible rows held are handed out again in the new order, in two steps
    under the entry's lock, since `order` is unique and each row is checked as it is written.
    Same gate as creating information (404 for an unknown entry, 403). Not logged: order is
    descriptive (ADR 0084).
    """
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    entity_stmt = select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    if (await session.execute(entity_stmt)).first() is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    await authorize_entity_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    await lock_entity_information(session, entity_id=entity_id, tenant_id=tenant_id)
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    stmt = (
        select(Information)
        .where(
            Information.entity_id == entity_id,
            Information.tenant_id == tenant_id,
            visible_information_clause(visibility),
        )
        .options(*_INFORMATION_LOAD_OPTIONS)
        .order_by(Information.order, Information.id)
        .execution_options(populate_existing=True)
    )
    rows = list((await session.execute(stmt)).scalars())
    wanted = body.information_ids
    if len(set(wanted)) != len(wanted) or set(wanted) != {row.id for row in rows}:
        raise InformationOrderListError(
            detail=(
                "The list must name each piece of information you can see on the entry, once: "
                f"expected {len(rows)}, got {len(wanted)}"
            )
        )

    slots = [row.order for row in rows]
    if [row.id for row in rows] != wanted:
        by_id = {row.id: row for row in rows}
        highest = (
            await session.scalar(
                select(func.max(Information.order)).where(
                    Information.entity_id == entity_id, Information.tenant_id == tenant_id
                )
            )
        ) or 0
        # Out of the way first (past every position there is), then into the slots.
        offset = highest + len(rows) + 1
        for row in rows:
            row.order += offset
        await session.flush()
        for slot, information_id in zip(slots, wanted, strict=True):
            by_id[information_id].order = slot
        await session.flush()
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
        rows = list((await session.execute(stmt)).scalars())
    return [InformationOut.from_information(row, request) for row in rows]


@router.put("/{entity_id}/picture")
async def set_entity_picture(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    file: UploadFile,
    is_public: Annotated[bool | None, Form()] = None,
) -> InformationOut:
    """Sets the entry's one main picture (ADR 0237, K8 of RFC 0041): writes the singleton
    `main_picture` information and its one picture payload, and answers with the information:
    `201` the first time, `200` when it replaces the picture it had. A multipart upload (PNG,
    JPEG, WebP or GIF, at most `picture_max_bytes`, 422 otherwise). `is_public` is a form field;
    left out, a new picture is not public (as every new information is) and a replaced one keeps
    what it was. Same gate as creating information (404, 403). Logged with the entry's id only
    (ADR 0084).
    """
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    entity_stmt = select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    if (await session.execute(entity_stmt)).first() is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    await authorize_entity_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)
    data, file_type = await read_picture_upload(file)

    await lock_entity_information(session, entity_id=entity_id, tenant_id=tenant_id)
    information = (
        await session.execute(
            select(Information)
            .where(
                Information.entity_id == entity_id,
                Information.tenant_id == tenant_id,
                Information.type == "main_picture",
            )
            .options(selectinload(Information.payloads).selectinload(Payload.picture))
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if information is None:
        information = Information(
            tenant_id=tenant_id,
            entity_id=entity_id,
            title="Main picture",
            type="main_picture",
            is_public=bool(is_public),
            created_by=user.id,
        )
        session.add(information)
        await session.flush()
        await add_picture_payload(
            session,
            tenant_id=tenant_id,
            information_id=information.id,
            data=data,
            file_type=file_type,
        )
        response.status_code = 201
    else:
        held = next((p for p in information.payloads if p.picture is not None), None)
        if held is None or held.picture is None:
            await add_picture_payload(
                session,
                tenant_id=tenant_id,
                information_id=information.id,
                data=data,
                file_type=file_type,
            )
        else:
            held.picture.data, held.picture.file_type = data, file_type
            held.updated_at = func.now()
        if is_public is not None:
            information.is_public = is_public
        information.updated_at = func.now()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="information.picture_set",
        target_type="information",
        target_id=information.id,
        detail=f"entity={entity_id}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return await information_out_or_404(
        tenant_id, information.id, request, session, user=user, require_visible=False
    )


@router.delete("/{entity_id}/picture", status_code=204)
async def clear_entity_picture(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    """Removes the entry's main picture, with its information (ADR 0237, K8 of RFC 0041): `204`
    whether or not it had one. Same gate as setting it. Logged when something was removed.
    """
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    entity_stmt = select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
    if (await session.execute(entity_stmt)).first() is None:
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    await authorize_entity_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)

    await lock_entity_information(session, entity_id=entity_id, tenant_id=tenant_id)
    information = (
        await session.execute(
            select(Information).where(
                Information.entity_id == entity_id,
                Information.tenant_id == tenant_id,
                Information.type == "main_picture",
            )
        )
    ).scalar_one_or_none()
    if information is None:
        return
    information_id = information.id
    await require_no_learning(session, tenant_id, information_id=information.id)
    await session.delete(information)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="information.picture_removed",
        target_type="information",
        target_id=information_id,
        detail=f"entity={entity_id}",
    )
    await session.commit()


async def get_information_or_404(
    session: SessionDep, information_id: uuid.UUID, tenant_id: uuid.UUID
) -> Information:
    """The eager-load chain payload_to_schema/InformationOut.from_information
    need - shared by create_information above and routers/information.py's
    own GET/PUT/DELETE, mirroring routers/items.py's eager_load_options
    being imported as-is by item_instances.py.
    """
    stmt = (
        select(Information)
        .where(Information.id == information_id, Information.tenant_id == tenant_id)
        .options(*_INFORMATION_LOAD_OPTIONS)
        # A re-read after a write in the same session must see the stored
        # row (updated_at is set by the database), not the stale identity-
        # map copy expire_on_commit=False leaves behind.
        .execution_options(populate_existing=True)
    )
    information = (await session.execute(stmt)).scalar_one_or_none()
    if information is None:
        raise InformationNotFoundError(
            detail=f"No information with id {information_id} in tenant {tenant_id}"
        )
    return information


async def information_out_or_404(
    tenant_id: uuid.UUID,
    information_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    *,
    user: CurrentUser,
    require_visible: bool = True,
) -> InformationOut:
    """Loads and wraps one Information row as the canonical response shape
    every write route in this ADR returns (ADR 0032's own "a follow-up GET
    would return the same thing" convention). `require_visible=False` for
    create_information's own immediate post-write read: a freshly-authored,
    non-public row has no Knowledge rows yet for anyone but is_public/orga/
    GM-reachable to match against, so information_visibility.can_see would
    otherwise 404 the caller on the very row they just proved self-or-
    managed authorization over. Every other caller (GET, and
    routers/information.py's own knower PUT/DELETE) keeps the real check -
    a caller who isn't the author and isn't otherwise allowed to see this
    row must not be able to determine its content or existence by poking
    these routes either.
    """
    information = await get_information_or_404(session, information_id, tenant_id)
    try:
        await require_visible_entry(
            session, entity_id=information.entity_id, tenant_id=tenant_id, user_id=user.id
        )
    except EntityNotFoundError:
        raise InformationNotFoundError(
            detail=f"No information with id {information_id} in tenant {tenant_id}"
        ) from None
    if require_visible:
        reader = await resolve_information_reader(
            session, user_id=user.id, tenant_id=tenant_id, information=[information]
        )
        if not reader.can_see(information):
            raise InformationNotFoundError(
                detail=f"No information with id {information_id} in tenant {tenant_id}"
            )
    return InformationOut.from_information(information, request)


async def authorize_information_edit(
    session: SessionDep, *, tenant_id: uuid.UUID, user: CurrentUser, information: Information
) -> None:
    """ADR 0101's gate for changing an *existing* Information row (PATCH,
    DELETE, its payloads, its knowers). Two parts, in this order:

    1. Sight of the row: information_visibility.can_see, or being its
       `created_by`. Otherwise 404, the same as a missing row - the row's
       existence isn't revealed. Without this, self-or-managed alone would
       let a player publish, delete, or self-grant the GM's secret about
       their own sword. The authorship clause keeps a player able to edit a
       restricted note they wrote, which has no knowers yet.
    2. Standing over the entity it describes: authorize_entity_write, 403.

    `information.knowledge_links` must be loaded (get_information_or_404
    does).
    """
    try:
        await require_visible_entry(
            session, entity_id=information.entity_id, tenant_id=tenant_id, user_id=user.id
        )
    except EntityNotFoundError:
        raise InformationNotFoundError(
            detail=f"No information with id {information.id} in tenant {tenant_id}"
        ) from None
    from lorenzo_api.session_access import manages_planning_entry, planning_entry

    if await planning_entry(session, tenant_id, information.entity_id):
        if await manages_planning_entry(session, tenant_id, information.entity_id, user.id) or (
            information.created_by == user.id and information.type == "note"
        ):
            return
        reader = await resolve_information_reader(
            session, user_id=user.id, tenant_id=tenant_id, information=[information]
        )
        if not reader.can_see(information):
            raise InformationNotFoundError(detail="No such Information in this library")
        raise InformationManagementForbiddenError(detail="Readers edit only their own notes")
    if await is_event_fact(session, tenant_id=tenant_id, entity_id=information.entity_id):
        await require_tenant_participant(session, tenant_id=tenant_id, user=user)
        if await manages_events(session, tenant_id=tenant_id, user_id=user.id):
            return
        if information.created_by == user.id and information.type == "note":
            return
        reader = await resolve_information_reader(
            session, user_id=user.id, tenant_id=tenant_id, information=[information]
        )
        if not reader.can_see(information):
            raise InformationNotFoundError(detail="No such Information in this library")
        raise InformationManagementForbiddenError(detail="Readers edit only their own notes")
    if information.created_by != user.id:
        reader = await resolve_information_reader(
            session, user_id=user.id, tenant_id=tenant_id, information=[information]
        )
        if not reader.can_see(information):
            raise InformationNotFoundError(
                detail=f"No information with id {information.id} in tenant {tenant_id}"
            )
    await authorize_entity_write(
        session, tenant_id=tenant_id, user=user, entity_id=information.entity_id
    )


async def editable_fact_audience(
    session: SessionDep, *, entity_id: uuid.UUID, tenant_id: uuid.UUID, user: CurrentUser
) -> EntityAudience:
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    await get_entity_or_404(session, entity_id, tenant_id)
    await authorize_entity_write(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
    await lock_entity_information(session, entity_id=entity_id, tenant_id=tenant_id)
    if not any(
        [
            await session.get(model, entity_id) is not None
            for model in (
                Fact,
                Calendar,
                Clock,
                Location,
                Map,
                CalendarPeriod,
                StoryEvent,
                CalendarObservance,
                Scene,
            )
        ]
    ):
        raise InvalidKindRequestError(
            detail="An outer audience is available for facts and calendar entries."
        )
    audience = await session.scalar(
        select(EntityAudience)
        .where(EntityAudience.entity_id == entity_id, EntityAudience.tenant_id == tenant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if audience is None and await session.get(Location, entity_id) is not None:
        # A Location made from an existing entry has no outer audience row: that entry
        # was visible as it was, and the first edit says so explicitly (ADR 0330).
        audience = EntityAudience(entity_id=entity_id, tenant_id=tenant_id, is_public=True)
        session.add(audience)
        await session.flush()
    assert audience is not None
    return audience


async def entry_audience_of(session: SessionDep, audience: EntityAudience) -> InformationAudience:
    links = (
        await session.execute(
            select(EntityKnowledge.knower_entity_id, EntityKnowledge.knower_player_id).where(
                EntityKnowledge.entity_id == audience.entity_id,
                EntityKnowledge.tenant_id == audience.tenant_id,
            )
        )
    ).all()
    return InformationAudience(
        is_public=audience.is_public,
        shared_with_participants=audience.shared_with_participants,
        entity_ids=sorted((e for e, _ in links if e is not None), key=str),
        player_ids=sorted((p for _, p in links if p is not None), key=str),
    )


@router.patch("/{entity_id}")
async def update_fact(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: FactUpdate,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> EntityDetailOut:
    """Rename a fact (ADR 0305); physical kinds retain their existing write routes."""
    await editable_fact_audience(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
    entity = await session.scalar(
        select(Entity)
        .where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        .execution_options(populate_existing=True)
    )
    assert entity is not None
    check_if_match(if_match, updated_at=entity.updated_at)
    if entity.name != body.name:
        entity.name = body.name
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="entity.renamed",
            target_type="entity",
            target_id=entity_id,
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
    out = await entity_detail_out(
        session, request, tenant_id=tenant_id, entity_id=entity_id, user=user
    )
    response.headers["ETag"] = etag_for(out.updated_at)
    return out


@router.get("/{entity_id}/knowers")
async def list_entry_knowers(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> list[EntryKnowerOut]:
    """Outer recipients are visible only to an editor, just like inner recipients."""
    await editable_fact_audience(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
    rows = (
        await session.execute(
            select(
                EntityKnowledge.knower_entity_id,
                EntityKnowledge.knower_player_id,
                Entity.name.label("entity_name"),
                User.display_name,
                User.nickname,
            )
            .outerjoin(Entity, Entity.id == EntityKnowledge.knower_entity_id)
            .outerjoin(Player, Player.id == EntityKnowledge.knower_player_id)
            .outerjoin(User, User.id == Player.user_id)
            .where(EntityKnowledge.entity_id == entity_id, EntityKnowledge.tenant_id == tenant_id)
            .order_by(EntityKnowledge.knower_entity_id, EntityKnowledge.knower_player_id)
        )
    ).all()
    reader = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    return [
        EntryKnowerOut(
            kind="player" if row.knower_player_id is not None else "entity",
            knower_entity_id=row.knower_entity_id,
            player_id=row.knower_player_id,
            name=(row.display_name or row.nickname)
            if row.knower_player_id is not None
            else row.entity_name
            if reader.can_see_entry(row.knower_entity_id)
            else None,
        )
        for row in rows
    ]


@router.get("/{entity_id}/audience")
async def get_entry_audience(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> InformationAudience:
    audience = await editable_fact_audience(
        session, entity_id=entity_id, tenant_id=tenant_id, user=user
    )
    response.headers["ETag"] = etag_for(audience.updated_at)
    return await entry_audience_of(session, audience)


@router.put("/{entity_id}/audience")
async def replace_entry_audience(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    body: InformationAudience,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> InformationAudience:
    audience = await editable_fact_audience(
        session, entity_id=entity_id, tenant_id=tenant_id, user=user
    )
    if if_match is None:
        raise AudiencePreconditionRequiredError(
            detail="Read the audience and send its ETag as If-Match."
        )
    check_if_match(if_match, updated_at=audience.updated_at)
    entities, players = set(body.entity_ids), set(body.player_ids)
    for model, wanted in ((Entity, entities), (Player, players)):
        if wanted:
            found = set(
                await session.scalars(
                    select(model.id).where(model.tenant_id == tenant_id, model.id.in_(wanted))
                )
            )
            if found != wanted:
                raise InvalidAudienceRecipientError(detail="Choose recipients from this library.")
    previous = await entry_audience_of(session, audience)
    shared = (
        body.shared_with_participants
        if "shared_with_participants" in body.model_fields_set
        else previous.shared_with_participants
    )
    if shared and await session.get(StoryEvent, entity_id) is None:
        raise InvalidAudienceRecipientError(detail="Only Events have a participant audience")
    if (
        previous.is_public != body.is_public
        or previous.shared_with_participants != shared
        or set(previous.entity_ids) != entities
        or set(previous.player_ids) != players
    ):
        await session.execute(
            delete(EntityKnowledge).where(
                EntityKnowledge.entity_id == entity_id, EntityKnowledge.tenant_id == tenant_id
            )
        )
        for recipient in entities:
            session.add(
                EntityKnowledge(
                    tenant_id=tenant_id, entity_id=entity_id, knower_entity_id=recipient
                )
            )
        for recipient in players:
            session.add(
                EntityKnowledge(
                    tenant_id=tenant_id, entity_id=entity_id, knower_player_id=recipient
                )
            )
        session.info.pop("visible_entry_checks", None)
        audience.is_public = body.is_public
        audience.shared_with_participants = shared
        audience.updated_at = datetime.now(UTC)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="entity.visibility_changed",
            target_type="entity",
            target_id=entity_id,
            detail=f"public={body.is_public}; entities={len(entities)}; players={len(players)}",
        )
        await session.commit()
        await set_tenant_rls_context(session, tenant_id)
        await session.refresh(audience)
    response.headers["ETag"] = etag_for(audience.updated_at)
    return await entry_audience_of(session, audience)


@router.get("/{entity_id}/about")
async def list_fact_subjects(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> list[EntitySummary]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    if await session.get(Fact, entity_id) is None:
        raise EntityNotFoundError(detail=f"No fact with id {entity_id} in tenant {tenant_id}")
    vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
    rows = await session.scalars(
        select(Entity)
        .join(FactAbout, FactAbout.subject_entity_id == Entity.id)
        .where(
            FactAbout.fact_entity_id == entity_id,
            FactAbout.tenant_id == tenant_id,
            visible_entry_clause(vis, Entity.id),
        )
        .order_by(Entity.name, Entity.id)
    )
    return [EntitySummary(id=row.id, name=row.name) for row in rows]


@router.put("/{entity_id}/about/{subject_id}", status_code=204)
async def add_fact_subject(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    subject_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    if await session.get(Fact, entity_id) is None:
        raise EntityNotFoundError(detail="No fact with that id in this library")
    await editable_fact_audience(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=subject_id, tenant_id=tenant_id, user_id=user.id)
    await get_entity_or_404(session, subject_id, tenant_id)
    if await session.get(FactAbout, (entity_id, subject_id)) is None:
        session.add(
            FactAbout(tenant_id=tenant_id, fact_entity_id=entity_id, subject_entity_id=subject_id)
        )
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="fact.subject_added",
            target_type="entity",
            target_id=entity_id,
            detail=f"subject={subject_id}",
        )
        await session.commit()


@router.delete("/{entity_id}/about/{subject_id}", status_code=204)
async def remove_fact_subject(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    subject_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
) -> None:
    if await session.get(Fact, entity_id) is None:
        raise EntityNotFoundError(detail="No fact with that id in this library")
    await editable_fact_audience(session, entity_id=entity_id, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=subject_id, tenant_id=tenant_id, user_id=user.id)
    await get_entity_or_404(session, subject_id, tenant_id)
    edge = await session.get(FactAbout, (entity_id, subject_id))
    if edge is not None:
        await session.delete(edge)
        await record_activity(
            session,
            tenant_id=tenant_id,
            actor_id=user.id,
            action="fact.subject_removed",
            target_type="entity",
            target_id=entity_id,
            detail=f"subject={subject_id}",
        )
        await session.commit()


@router.get("/{entity_id}/facts")
async def list_facts_about(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
) -> Page[EntityListOut]:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    await get_entity_or_404(session, entity_id, tenant_id)
    vis = await resolve_information_visibility(session, tenant_id=tenant_id, user_id=user.id)
    stmt = (
        select(Entity)
        .join(FactAbout, FactAbout.fact_entity_id == Entity.id)
        .where(
            FactAbout.subject_entity_id == entity_id,
            FactAbout.tenant_id == tenant_id,
            visible_entry_clause(vis, Entity.id),
        )
        .order_by(Entity.name, Entity.id)
    )

    async def rows(entries: Sequence[Entity]) -> list[EntityListOut]:
        ids = [e.id for e in entries]
        kinds = await kinds_of(session, ids)
        parents = await parents_of(session, ids, vis)
        return [
            EntityListOut(id=e.id, name=e.name, kinds=kinds[e.id], parent_ids=parents[e.id])
            for e in entries
        ]

    return cast(Page[EntityListOut], await apaginate(session, stmt, params, transformer=rows))


class EntryCollaborationAccess(BaseModel):
    can_edit: bool
    can_add_notes: bool
    editable_information_ids: list[uuid.UUID]


@router.get("/{entity_id}/access")
async def entry_collaboration_access(
    tenant_id: uuid.UUID, entity_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> EntryCollaborationAccess:
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await get_entity_or_404(session, entity_id, tenant_id)
    from lorenzo_api.session_access import planning_entry

    collaborative = await planning_entry(session, tenant_id, entity_id) or await is_event_fact(
        session, tenant_id=tenant_id, entity_id=entity_id
    )
    editable = False
    try:
        await authorize_entity_write(session, tenant_id=tenant_id, user=user, entity_id=entity_id)
        editable = True
    except InformationManagementForbiddenError:
        pass
    editable_ids = []
    infos = await session.scalars(
        select(Information)
        .options(selectinload(Information.knowledge_links))
        .where(Information.tenant_id == tenant_id, Information.entity_id == entity_id)
    )
    for info in infos:
        try:
            await authorize_information_edit(
                session, tenant_id=tenant_id, user=user, information=info
            )
            editable_ids.append(info.id)
        except InformationManagementForbiddenError, InformationNotFoundError:
            pass
    return EntryCollaborationAccess(
        can_edit=editable,
        can_add_notes=collaborative or editable,
        editable_information_ids=editable_ids,
    )
