"""SocialWebs: saved views of relationships (ADR 0406).

A web shows exactly the entries that have a row. It says what it shows, not what is true, and it
gives no access to anything it names. A reader sees a member only if they may see the entry; a row
of a hidden entry leaves no mark, gap or count, and the layout is computed by the client over what
that reader sees, so a hidden member moves no one."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import Select, delete, exists, or_, select
from sqlalchemy.orm import aliased

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_or_404,
    set_tenant_rls_context,
)
from lorenzo_api.entity_access import controlled_holder_entity_ids, prototype_descendants_cte
from lorenzo_api.entity_kinds import create_entry
from lorenzo_api.entry_visibility import visible_entry_clause
from lorenzo_api.etag import check_if_match, etag_for
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InvalidSocialWebError,
    MapPreconditionRequiredError,
    RelationshipReadAsForbiddenError,
)
from lorenzo_api.information_visibility import InformationVisibility
from lorenzo_api.models import (
    Entity,
    EntityAudience,
    Relationship,
    SocialWeb,
    SocialWebEntry,
    SocialWebType,
    StatDefinition,
    StoryEvent,
)
from lorenzo_api.relationships import touch_relationship
from lorenzo_api.routers.connections import EntryStub, _visible_entry, entry_stubs
from lorenzo_api.routers.locations import manages, require_manager, standing
from lorenzo_api.routers.relationships import (
    RelationshipEntryOut,
    _being_view,
    _states_as_of,
    build_rows,
    visible_event_ids,
)
from lorenzo_api.schemas.common import Slug
from lorenzo_api.social_webs import (
    MAX_BULK_ROWS,
    MAX_EDGES,
    MAX_TYPES,
    MAX_VIEW_BYTES,
    Layout,
    holds_no_entry_id,
    require_member_room,
)

router = APIRouter(
    prefix="/tenants/{tenant_id}",
    tags=["social webs"],
    dependencies=[Depends(get_tenant_or_404)],
)

_NOT_FOUND = "No such social web in this library"

Finite = Annotated[float, Field(allow_inf_nan=False)]
ThemeHint = Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,39}$")]


class SocialWebSettings(BaseModel):
    """What a web saves about how it looks and what it reads (ADR 0406)."""

    model_config = ConfigDict(extra="forbid")
    layout: Layout = "circle"
    layout_seed: Annotated[int, Field(ge=0, le=2_147_483_647)] = 1
    theme_hint: ThemeHint | None = None
    # Visual-only switches (labels, hulls). Never an entry id, never a value the server reads.
    view: dict[str, Any] | None = None
    # The standing the matrix reads and the date lens, when saved with the view.
    standing_stat_id: uuid.UUID | None = None
    as_of_event: uuid.UUID | None = None

    @field_validator("view")
    @classmethod
    def _plain_view(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        if value is None:
            return value
        if len(str(value)) > MAX_VIEW_BYTES:
            raise ValueError("The view is a few switches, not data")
        if not holds_no_entry_id(value):
            raise ValueError("The view holds no entry id")
        return value


class SocialWebCreate(SocialWebSettings):
    id: uuid.UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None
    is_public: bool = False


class SocialWebOut(EntryStub):
    layout: str
    layout_seed: int
    theme_hint: str | None
    view: dict[str, Any] | None
    standing_stat_id: uuid.UUID | None
    # Named only when the reader may see that Event.
    as_of_event: EntryStub | None
    updated_at: datetime
    can_manage: bool
    # Only for those who may manage relationships: whether everyone may see it.
    is_public: bool | None = None


class SocialWebMemberOut(BaseModel):
    entry: EntryStub
    x: float | None
    y: float | None


class SocialWebDetail(SocialWebOut):
    """The web as one reader sees it: the members and types they may see, and nothing else."""

    members: list[SocialWebMemberOut]
    types: list[EntryStub]


class SocialWebGraph(BaseModel):
    web: SocialWebOut
    members: list[SocialWebMemberOut]
    # The visible relationships between visible members, of the web's types if it names any.
    edges: list[RelationshipEntryOut]
    truncated: bool


class SocialWebPlacement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_id: uuid.UUID
    x: Finite | None = None
    y: Finite | None = None

    @model_validator(mode="after")
    def _both_or_none(self) -> SocialWebPlacement:
        if (self.x is None) != (self.y is None):
            raise ValueError("A hand placement has both x and y, or neither")
        return self


class SocialWebMembersWrite(BaseModel):
    """Adds or moves members (`set`) and drops them (`remove`), at most a hundred rows in all."""

    model_config = ConfigDict(extra="forbid")
    set: list[SocialWebPlacement] = Field(default_factory=list)
    remove: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _bounded(self) -> SocialWebMembersWrite:
        rows = [p.entry_id for p in self.set] + self.remove
        if not rows or len(rows) > MAX_BULK_ROWS:
            raise ValueError(f"A write takes between 1 and {MAX_BULK_ROWS} rows")
        if len(set(rows)) != len(rows):
            raise ValueError("An entry appears once in a write")
        return self


class SocialWebTypesPut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type_ids: list[uuid.UUID] = Field(max_length=MAX_TYPES)


async def _commit(session: SessionDep, tenant: uuid.UUID) -> None:
    await session.commit()
    await set_tenant_rls_context(session, tenant)


async def _read(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, identity: uuid.UUID
) -> tuple[Entity, SocialWeb]:
    """A web the reader may see; a hidden one and a missing one are the same 404."""
    found = (
        await session.execute(
            select(Entity, SocialWeb)
            .join(SocialWeb, SocialWeb.entity_id == Entity.id)
            .where(
                Entity.tenant_id == tenant,
                Entity.id == identity,
                visible_entry_clause(vis, Entity.id),
            )
            .execution_options(populate_existing=True)
        )
    ).first()
    if found is None:
        raise EntityNotFoundError(detail=_NOT_FOUND)
    return found[0], found[1]


async def _out(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    entity: Entity,
    web: SocialWeb,
) -> SocialWebOut:
    manage = manages(vis)
    is_public = None
    if manage:
        audience = await session.get(EntityAudience, entity.id)
        is_public = True if audience is None else audience.is_public
    seen = await visible_event_ids(
        session, vis, tenant, {web.as_of_event} if web.as_of_event else set()
    )
    stubs = await entry_stubs(session, tenant, {entity.id, *seen})
    return SocialWebOut(
        **stubs[entity.id].model_dump(),
        layout=web.layout,
        layout_seed=web.layout_seed,
        theme_hint=web.theme_hint,
        view=web.view,
        standing_stat_id=web.standing_stat_id,
        as_of_event=stubs.get(web.as_of_event) if web.as_of_event in seen else None,
        updated_at=entity.updated_at,
        can_manage=manage,
        is_public=is_public if manage else None,
    )


async def _members(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, web_id: uuid.UUID
) -> list[SocialWebMemberOut]:
    """The members the reader may see, by name then id. A hidden member is simply absent."""
    rows = (
        await session.execute(
            select(SocialWebEntry.entry_entity_id, SocialWebEntry.x, SocialWebEntry.y)
            .join(Entity, Entity.id == SocialWebEntry.entry_entity_id)
            .where(
                SocialWebEntry.tenant_id == tenant,
                SocialWebEntry.web_entity_id == web_id,
                visible_entry_clause(vis, Entity.id),
            )
            .order_by(Entity.name, Entity.id)
        )
    ).all()
    stubs = await entry_stubs(session, tenant, {row[0] for row in rows})
    return [SocialWebMemberOut(entry=stubs[row[0]], x=row[1], y=row[2]) for row in rows]


async def _types(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, web_id: uuid.UUID
) -> list[EntryStub]:
    rows = (
        await session.execute(
            select(SocialWebType.type_entity_id)
            .join(Entity, Entity.id == SocialWebType.type_entity_id)
            .where(
                SocialWebType.tenant_id == tenant,
                SocialWebType.web_entity_id == web_id,
                visible_entry_clause(vis, Entity.id),
            )
            .order_by(Entity.name, Entity.id)
        )
    ).all()
    stubs = await entry_stubs(session, tenant, {row[0] for row in rows})
    return [stubs[row[0]] for row in rows]


async def _detail(
    session: SessionDep, vis: InformationVisibility, tenant: uuid.UUID, identity: uuid.UUID
) -> SocialWebDetail:
    entity, web = await _read(session, vis, tenant, identity)
    out = await _out(session, vis, tenant, entity, web)
    return SocialWebDetail(
        **out.model_dump(),
        members=await _members(session, vis, tenant, identity),
        types=await _types(session, vis, tenant, identity),
    )


async def _check_settings(
    session: SessionDep,
    user: CurrentUser,
    tenant: uuid.UUID,
    settings: SocialWebSettings,
) -> None:
    if settings.standing_stat_id is not None:
        found = await session.scalar(
            select(StatDefinition.id).where(
                StatDefinition.id == settings.standing_stat_id, StatDefinition.tenant_id == tenant
            )
        )
        if found is None:
            raise InvalidSocialWebError(detail="The standing is a stat definition of this library.")
    if settings.as_of_event is not None:
        await _visible_entry(session, user, tenant, settings.as_of_event)
        if await session.get(StoryEvent, settings.as_of_event) is None:
            raise InvalidSocialWebError(detail="The date lens is an Event.")


async def _check_member(
    session: SessionDep, user: CurrentUser, tenant: uuid.UUID, entry: uuid.UUID
) -> None:
    """A member is an entry the writer sees, and not a relationship (those are the edges) or a
    web (a web of webs is not built)."""
    await _visible_entry(session, user, tenant, entry)
    if await session.scalar(
        select(
            exists().where(Relationship.entity_id == entry)
            | exists().where(SocialWeb.entity_id == entry)
        )
    ):
        raise InvalidSocialWebError(detail="A web shows entries, not relationships or webs.")


@router.post("/social-webs", status_code=201)
async def create_social_web(
    tenant_id: uuid.UUID,
    body: SocialWebCreate,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SocialWebDetail:
    """A new web, restricted unless `is_public`, with no members yet."""
    vis = await require_manager(session, user, tenant_id)
    await _check_settings(session, user, tenant_id, body)
    entity = await create_entry(
        session,
        tenant_id=tenant_id,
        user_id=user.id,
        name=body.name,
        slug=body.slug,
        kinds=[],
        parents=[],
        in_public_catalog=False,
        entity_id=body.id,
    )
    session.add(
        SocialWeb(
            entity_id=entity.id,
            tenant_id=tenant_id,
            layout=body.layout,
            layout_seed=body.layout_seed,
            theme_hint=body.theme_hint,
            view=body.view,
            standing_stat_id=body.standing_stat_id,
            as_of_event=body.as_of_event,
        )
    )
    session.add(EntityAudience(entity_id=entity.id, tenant_id=tenant_id, is_public=body.is_public))
    await session.flush()
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="social_web.created",
        target_type="entity",
        target_id=entity.id,
    )
    await _commit(session, tenant_id)
    # Read again: the writer's reach is worked out per request, before the web existed.
    vis = await standing(session, user, tenant_id)
    detail = await _detail(session, vis, tenant_id, entity.id)
    response.headers["ETag"] = etag_for(detail.updated_at)
    return detail


@router.get("/social-webs")
async def list_social_webs(
    tenant_id: uuid.UUID,
    params: ParamsDep,
    session: SessionDep,
    user: CurrentUser,
    q: Annotated[
        str | None, Query(description="Case-insensitive substring match against the name.")
    ] = None,
) -> Page[SocialWebOut]:
    """The webs the reader may see, by name then id."""
    vis = await standing(session, user, tenant_id)
    own = aliased(EntityAudience)
    stmt: Select[Any] = (
        select(Entity, SocialWeb, own.is_public)
        .join(SocialWeb, SocialWeb.entity_id == Entity.id)
        .outerjoin(own, own.entity_id == Entity.id)
        .where(Entity.tenant_id == tenant_id, visible_entry_clause(vis, Entity.id))
        .order_by(Entity.name, Entity.id)
    )
    if q is not None:
        stmt = stmt.where(Entity.name.icontains(q, autoescape=True))

    async def rows(found: Any) -> list[SocialWebOut]:
        manage = manages(vis)
        events = {row[1].as_of_event for row in found if row[1].as_of_event}
        seen = await visible_event_ids(session, vis, tenant_id, events)
        stubs = await entry_stubs(session, tenant_id, {row[0].id for row in found} | seen)
        return [
            SocialWebOut(
                **stubs[entity.id].model_dump(),
                layout=web.layout,
                layout_seed=web.layout_seed,
                theme_hint=web.theme_hint,
                view=web.view,
                standing_stat_id=web.standing_stat_id,
                as_of_event=stubs.get(web.as_of_event) if web.as_of_event in seen else None,
                updated_at=entity.updated_at,
                can_manage=manage,
                is_public=(True if is_public is None else is_public) if manage else None,
            )
            for entity, web, is_public in found
        ]

    page: Page[SocialWebOut] = await apaginate(session, stmt, params, transformer=rows)
    return page


@router.get("/social-webs/{web_id}")
async def get_social_web(
    tenant_id: uuid.UUID,
    web_id: uuid.UUID,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> SocialWebDetail:
    vis = await standing(session, user, tenant_id)
    detail = await _detail(session, vis, tenant_id, web_id)
    response.headers["ETag"] = etag_for(detail.updated_at)
    return detail


async def _written(
    session: SessionDep,
    vis: InformationVisibility,
    tenant: uuid.UUID,
    user: CurrentUser,
    web_id: uuid.UUID,
    response: Response,
) -> SocialWebDetail:
    """Touches the web (its version moves), commits, and answers with it as the writer reads it."""
    await touch_relationship(session, tenant_id=tenant, relationship_id=web_id, user_id=user.id)
    await record_activity(
        session,
        tenant_id=tenant,
        actor_id=user.id,
        action="social_web.updated",
        target_type="entity",
        target_id=web_id,
    )
    await _commit(session, tenant)
    detail = await _detail(session, vis, tenant, web_id)
    response.headers["ETag"] = etag_for(detail.updated_at)
    return detail


async def _writable(
    session: SessionDep,
    user: CurrentUser,
    tenant: uuid.UUID,
    web_id: uuid.UUID,
    if_match: str | None,
) -> tuple[InformationVisibility, Entity, SocialWeb]:
    vis = await require_manager(session, user, tenant)
    entity, web = await _read(session, vis, tenant, web_id)
    if if_match is None:
        raise MapPreconditionRequiredError(detail="Send the web's ETag as If-Match.")
    check_if_match(if_match, updated_at=entity.updated_at)
    return vis, entity, web


@router.put("/social-webs/{web_id}")
async def put_social_web(
    tenant_id: uuid.UUID,
    web_id: uuid.UUID,
    body: SocialWebSettings,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SocialWebDetail:
    """Replaces the settings under `If-Match`: layout, seed, theme, view, standing and date lens."""
    vis, _, web = await _writable(session, user, tenant_id, web_id, if_match)
    await _check_settings(session, user, tenant_id, body)
    web.layout = body.layout
    web.layout_seed = body.layout_seed
    web.theme_hint = body.theme_hint
    web.view = body.view
    web.standing_stat_id = body.standing_stat_id
    web.as_of_event = body.as_of_event
    await session.flush()
    return await _written(session, vis, tenant_id, user, web_id, response)


@router.post("/social-webs/{web_id}/members/bulk")
async def write_members(
    tenant_id: uuid.UUID,
    web_id: uuid.UUID,
    body: SocialWebMembersWrite,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SocialWebDetail:
    """Adds, places and drops members in one transaction, at most a hundred rows (ADR 0406). Any
    refused row refuses the request and nothing is written."""
    vis, _, _ = await _writable(session, user, tenant_id, web_id, if_match)
    wanted = [p.entry_id for p in body.set]
    existing = set(
        await session.scalars(
            select(SocialWebEntry.entry_entity_id).where(
                SocialWebEntry.tenant_id == tenant_id,
                SocialWebEntry.web_entity_id == web_id,
                SocialWebEntry.entry_entity_id.in_(wanted),
            )
        )
        if wanted
        else []
    )
    for placement in body.set:
        await _check_member(session, user, tenant_id, placement.entry_id)
    await require_member_room(
        session, web_id=web_id, tenant_id=tenant_id, adding=len(set(wanted) - existing)
    )
    for placement in body.set:
        if placement.entry_id in existing:
            row = await session.get(SocialWebEntry, (web_id, placement.entry_id))
            assert row is not None
            row.x, row.y = placement.x, placement.y
        else:
            session.add(
                SocialWebEntry(
                    web_entity_id=web_id,
                    entry_entity_id=placement.entry_id,
                    tenant_id=tenant_id,
                    x=placement.x,
                    y=placement.y,
                )
            )
    if body.remove:
        await session.execute(
            delete(SocialWebEntry).where(
                SocialWebEntry.tenant_id == tenant_id,
                SocialWebEntry.web_entity_id == web_id,
                SocialWebEntry.entry_entity_id.in_(body.remove),
            )
        )
    await session.flush()
    return await _written(session, vis, tenant_id, user, web_id, response)


@router.put("/social-webs/{web_id}/types")
async def put_social_web_types(
    tenant_id: uuid.UUID,
    web_id: uuid.UUID,
    body: SocialWebTypesPut,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
    if_match: Annotated[str | None, Header()] = None,
) -> SocialWebDetail:
    """Replaces the types the web limits its edges to; none means every type."""
    vis, _, _ = await _writable(session, user, tenant_id, web_id, if_match)
    wanted = list(dict.fromkeys(body.type_ids))
    for type_id in wanted:
        await _visible_entry(session, user, tenant_id, type_id)
    await session.execute(
        delete(SocialWebType).where(
            SocialWebType.tenant_id == tenant_id, SocialWebType.web_entity_id == web_id
        )
    )
    for type_id in wanted:
        session.add(
            SocialWebType(web_entity_id=web_id, type_entity_id=type_id, tenant_id=tenant_id)
        )
    await session.flush()
    return await _written(session, vis, tenant_id, user, web_id, response)


@router.get("/social-webs/{web_id}/graph")
async def get_social_web_graph(
    tenant_id: uuid.UUID,
    web_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    as_of: Annotated[
        uuid.UUID | None,
        Query(description="An Event: each edge says where it stands then (ADR 0405)."),
    ] = None,
    as_seen_by: Annotated[
        uuid.UUID | None,
        Query(description="A being: only what it may read through its own grants and groups."),
    ] = None,
) -> SocialWebGraph:
    """What the reader draws: the members they may see and the relationships they may see between
    them, limited to the web's types when it names any. An edge to a hidden member is absent."""
    vis = await standing(session, user, tenant_id)
    entity, web = await _read(session, vis, tenant_id, web_id)
    members = await _members(session, vis, tenant_id, web_id)
    ids = [m.entry.id for m in members]
    edges: list[RelationshipEntryOut] = []
    truncated = False
    if len(ids) >= 2:
        own = aliased(EntityAudience)
        stmt: Select[Any] = (
            select(
                Entity.id,
                Relationship.end_a,
                Relationship.end_b,
                Relationship.one_way,
                Entity.updated_at,
                own.is_public,
                Relationship.starts_at,
                Relationship.ends_at,
            )
            .join(Relationship, Relationship.entity_id == Entity.id)
            .outerjoin(own, own.entity_id == Entity.id)
            .where(
                Entity.tenant_id == tenant_id,
                visible_entry_clause(vis, Entity.id),
                Relationship.end_a.in_(ids),
                Relationship.end_b.in_(ids),
            )
            .order_by(Entity.name, Entity.id)
            .limit(MAX_EDGES + 1)
        )
        type_ids = list(
            await session.scalars(
                select(SocialWebType.type_entity_id).where(
                    SocialWebType.tenant_id == tenant_id, SocialWebType.web_entity_id == web_id
                )
            )
        )
        if type_ids:
            stmt = stmt.where(
                or_(
                    *(
                        Entity.id.in_(
                            select(prototype_descendants_cte(t, tenant_id).c.descendant_id)
                        )
                        for t in type_ids
                    )
                )
            )
        if as_seen_by is not None:
            await _visible_entry(session, user, tenant_id, as_seen_by)
            if not manages(vis) and as_seen_by not in await controlled_holder_entity_ids(
                session, user_id=user.id, tenant_id=tenant_id
            ):
                raise RelationshipReadAsForbiddenError()
            # What the being may read, and never more than the reader may.
            stmt = stmt.where(
                visible_entry_clause(await _being_view(session, tenant_id, as_seen_by), Entity.id)
            )
        states = (
            await _states_as_of(session, vis, tenant_id, stmt, as_of) if as_of is not None else None
        )
        found = (await session.execute(stmt)).all()
        truncated = len(found) > MAX_EDGES
        edges = await build_rows(session, vis, tenant_id, found[:MAX_EDGES], states=states)
    return SocialWebGraph(
        web=await _out(session, vis, tenant_id, entity, web),
        members=members,
        edges=edges,
        truncated=truncated,
    )
