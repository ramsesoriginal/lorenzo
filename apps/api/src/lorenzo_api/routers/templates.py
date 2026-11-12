"""The templates of a library, and the entries they show - ADR 0451, RFC 0052.

A template is a read-side view as data: ordered slots that say which stats and notes of an entry
a sheet shows, under which labels, and a filter (a kind and an ancestor) that says which entries
it is for. Authoring is the vocabulary's tier, as the game systems' is; reading a template
through an entry is any participant's, and shows only what the caller may read by the rules each
source already has. A template never writes a value.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import cast

from fastapi import APIRouter, Depends, Request, Response
from fastapi_pagination import Page
from fastapi_pagination.ext.sqlalchemy import apaginate
from sqlalchemy import delete, or_, select
from sqlalchemy.orm import joinedload, selectinload

from lorenzo_api.activity_log import record_activity
from lorenzo_api.dependencies import (
    CurrentUser,
    ParamsDep,
    SessionDep,
    get_tenant_admin_context,
    get_tenant_or_404,
    require_tenant_participant,
    set_tenant_rls_context,
)
from lorenzo_api.entry_visibility import require_visible_entry
from lorenzo_api.exceptions import (
    EntityNotFoundError,
    InvalidTemplateError,
    TemplateDoesNotMatchError,
    TemplateNameTakenError,
    TemplateNotFoundError,
)
from lorenzo_api.information_visibility import (
    InformationVisibility,
    resolve_information_visibility,
    visible_information_clause,
)
from lorenzo_api.models import (
    Containment,
    Entity,
    EntityPrototype,
    Information,
    StatDefinition,
    StatGroup,
    System,
    Template,
    TemplateSlot,
    TemplateSlotExclusion,
    TemplateSlotStat,
    VEffectiveStat,
    VItemInstance,
)
from lorenzo_api.routers.entities import (
    _INFORMATION_LOAD_OPTIONS,
    get_entity_detail_or_404,
    kinds_of,
)
from lorenzo_api.routers.item_instances import _owner_predicate_for, caller_reach
from lorenzo_api.routers.items import eager_load_options
from lorenzo_api.routers.stats import _vocabulary_gate
from lorenzo_api.schemas.common import EntitySummary
from lorenzo_api.schemas.entities import EntityStatValueOut, InformationOut, _stats_out
from lorenzo_api.schemas.templates import (
    SlotKind,
    TemplateCellOut,
    TemplateColumnOut,
    TemplateHeldRowOut,
    TemplateIn,
    TemplateOut,
    TemplateSlotIn,
    TemplateStatOut,
    TemplateSummaryOut,
    TemplateViewOut,
    TemplateViewSlotOut,
)
from lorenzo_api.stat_contents import attach_contents
from lorenzo_api.system_filter import SystemFilter, require_system_slug

router = APIRouter(
    prefix="/tenants/{tenant_id}/templates",
    tags=["templates"],
    dependencies=[Depends(_vocabulary_gate)],
)
entry_router = APIRouter(
    prefix="/tenants/{tenant_id}/entities/{entity_id}",
    tags=["templates"],
    dependencies=[Depends(get_tenant_or_404)],
)


# --- authoring ---------------------------------------------------------------------------------


async def _slugs(session: SessionDep, tenant_id: uuid.UUID) -> dict[uuid.UUID, str]:
    rows = await session.execute(
        select(System.id, System.slug).where(System.tenant_id == tenant_id)
    )
    return {system_id: slug for system_id, slug in rows.tuples()}


def _summary(template: Template, slugs: dict[uuid.UUID, str]) -> TemplateSummaryOut:
    return TemplateSummaryOut.model_validate(
        {
            "id": template.id,
            "name": template.name,
            "system_id": template.system_id,
            "system": slugs.get(template.system_id) if template.system_id else None,
            "required_kind": template.required_kind,
            "required_ancestor_entry_id": template.required_ancestor_entry_id,
        }
    )


def _out(template: Template, slugs: dict[uuid.UUID, str]) -> TemplateOut:
    return TemplateOut.model_validate(
        {
            **_summary(template, slugs).model_dump(),
            "slots": [
                {
                    "id": slot.id,
                    "position": slot.position,
                    "kind": slot.kind,
                    "label": slot.label,
                    "stat_group_id": slot.stat_group_id,
                    "stats": [
                        {"stat_definition_id": s.stat_definition_id, "label": s.label}
                        for s in slot.stats
                    ],
                    "exclude": sorted(e.stat_definition_id for e in slot.exclusions),
                    "information_type": slot.information_type,
                    "held_order": slot.held_order,
                }
                for slot in template.slots
            ],
            "created_at": template.created_at,
            "updated_at": template.updated_at,
        }
    )


_SLOT_LOAD = (
    selectinload(Template.slots).selectinload(TemplateSlot.stats),
    selectinload(Template.slots).selectinload(TemplateSlot.exclusions),
)


async def _get_or_404(
    session: SessionDep, tenant_id: uuid.UUID, template_id: uuid.UUID
) -> Template:
    template = (
        await session.execute(
            select(Template)
            .where(Template.id == template_id, Template.tenant_id == tenant_id)
            .options(*_SLOT_LOAD)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if template is None:
        raise TemplateNotFoundError(
            detail=f"No template with id {template_id} in tenant {tenant_id}"
        )
    return template


async def _check_name_free(
    session: SessionDep, tenant_id: uuid.UUID, name: str, *, own_id: uuid.UUID | None = None
) -> None:
    taken = await session.scalar(
        select(Template.id).where(
            Template.tenant_id == tenant_id,
            Template.name == name,
            *([Template.id != own_id] if own_id is not None else []),
        )
    )
    if taken is not None:
        raise TemplateNameTakenError(
            detail=f"Another template in tenant {tenant_id} is already called {name!r}"
        )


async def _validate(session: SessionDep, tenant_id: uuid.UUID, body: TemplateIn) -> None:
    """The system, the ancestor entry, every stat group and every stat a template names are the
    library's, and what a slot leaves out belongs to its group (422)."""
    if body.system_id is not None and not await session.scalar(
        select(System.id).where(System.id == body.system_id, System.tenant_id == tenant_id)
    ):
        raise InvalidTemplateError(detail=f"{body.system_id} is not a system of tenant {tenant_id}")
    if body.required_ancestor_entry_id is not None and not await session.scalar(
        select(Entity.id).where(
            Entity.id == body.required_ancestor_entry_id, Entity.tenant_id == tenant_id
        )
    ):
        raise InvalidTemplateError(
            detail=f"{body.required_ancestor_entry_id} is not an entry of tenant {tenant_id}"
        )
    group_ids = {slot.stat_group_id for slot in body.slots if slot.stat_group_id is not None}
    if group_ids:
        found = set(
            await session.scalars(
                select(StatGroup.id).where(
                    StatGroup.tenant_id == tenant_id, StatGroup.id.in_(group_ids)
                )
            )
        )
        if missing := sorted(group_ids - found):
            raise InvalidTemplateError(detail=f"{missing[0]} is not a stat group of the library")
    definition_ids = {
        *(s.stat_definition_id for slot in body.slots for s in slot.stats),
        *(d for slot in body.slots for d in slot.exclude),
    }
    groups_of: dict[uuid.UUID, uuid.UUID] = {}
    if definition_ids:
        rows = await session.execute(
            select(StatDefinition.id, StatDefinition.stat_group_id).where(
                StatDefinition.tenant_id == tenant_id, StatDefinition.id.in_(definition_ids)
            )
        )
        groups_of = {definition_id: group_id for definition_id, group_id in rows.tuples()}
        if missing := sorted(definition_ids - set(groups_of)):
            raise InvalidTemplateError(detail=f"{missing[0]} is not a stat of the library")
    for position, slot in enumerate(body.slots):
        listed = [s.stat_definition_id for s in slot.stats]
        if len(set(listed)) != len(listed):
            raise InvalidTemplateError(detail=f"Slot {position} lists a stat twice")
        for definition_id in slot.exclude:
            if groups_of[definition_id] != slot.stat_group_id:
                raise InvalidTemplateError(
                    detail=f"Slot {position} leaves out {definition_id}, which is not in its group"
                )


async def _replace_slots(
    session: SessionDep, tenant_id: uuid.UUID, template_id: uuid.UUID, slots: list[TemplateSlotIn]
) -> None:
    await session.execute(
        delete(TemplateSlot)
        .where(TemplateSlot.template_id == template_id, TemplateSlot.tenant_id == tenant_id)
        .execution_options(synchronize_session=False)
    )
    for position, slot in enumerate(slots):
        row = TemplateSlot(
            tenant_id=tenant_id,
            template_id=template_id,
            position=position,
            kind=slot.kind,
            label=slot.label,
            stat_group_id=slot.stat_group_id,
            information_type=slot.information_type,
            held_order=slot.held_order,
        )
        session.add(row)
        await session.flush()
        for index, stat in enumerate(slot.stats):
            session.add(
                TemplateSlotStat(
                    slot_id=row.id,
                    position=index,
                    tenant_id=tenant_id,
                    stat_definition_id=stat.stat_definition_id,
                    label=stat.label,
                )
            )
        for definition_id in dict.fromkeys(slot.exclude):
            session.add(
                TemplateSlotExclusion(
                    slot_id=row.id, stat_definition_id=definition_id, tenant_id=tenant_id
                )
            )
    await session.flush()


@router.post("", status_code=201)
async def create_template(
    tenant_id: uuid.UUID,
    body: TemplateIn,
    request: Request,
    response: Response,
    session: SessionDep,
    user: CurrentUser,
) -> TemplateOut:
    """Makes a template with its slots (409 for a name the library has, 422 for a slot that does
    not fit its kind or a system, entry, stat group or stat that is not the library's)."""
    await _check_name_free(session, tenant_id, body.name)
    await _validate(session, tenant_id, body)
    template = Template(
        tenant_id=tenant_id,
        name=body.name,
        system_id=body.system_id,
        required_kind=body.required_kind,
        required_ancestor_entry_id=body.required_ancestor_entry_id,
    )
    session.add(template)
    await session.flush()
    await _replace_slots(session, tenant_id, template.id, body.slots)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="template.created",
        target_type="template",
        target_id=template.id,
        detail=f"slots={len(body.slots)}",
    )
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    response.headers["Location"] = str(
        request.url_for("get_template", tenant_id=tenant_id, template_id=template.id)
    )
    return _out(
        await _get_or_404(session, tenant_id, template.id), await _slugs(session, tenant_id)
    )


@router.get("")
async def list_templates(
    tenant_id: uuid.UUID, session: SessionDep, params: ParamsDep, system: SystemFilter = None
) -> Page[TemplateSummaryOut]:
    """The library's templates by name; with `system`, those of no game system and of that one
    (an unknown slug is a 404)."""
    await require_system_slug(session, tenant_id, system)
    slugs = await _slugs(session, tenant_id)
    stmt = select(Template).where(Template.tenant_id == tenant_id)
    if system is not None:
        stmt = stmt.where(
            or_(
                Template.system_id.is_(None),
                Template.system_id.in_(
                    select(System.id).where(System.tenant_id == tenant_id, System.slug == system)
                ),
            )
        )
    page: Page[TemplateSummaryOut] = await apaginate(
        session,
        stmt.order_by(Template.name, Template.id),
        params,
        transformer=lambda rows: [_summary(row, slugs) for row in rows],
    )
    return page


@router.get("/{template_id}")
async def get_template(
    tenant_id: uuid.UUID, template_id: uuid.UUID, session: SessionDep
) -> TemplateOut:
    return _out(
        await _get_or_404(session, tenant_id, template_id), await _slugs(session, tenant_id)
    )


@router.put("/{template_id}")
async def replace_template(
    tenant_id: uuid.UUID, template_id: uuid.UUID, body: TemplateIn, session: SessionDep
) -> TemplateOut:
    """Replaces the template: its name, game system, filter and every slot. Not logged: what a
    sheet shows, not structure (ADR 0084)."""
    template = await _get_or_404(session, tenant_id, template_id)
    await _check_name_free(session, tenant_id, body.name, own_id=template_id)
    await _validate(session, tenant_id, body)
    template.name = body.name
    template.system_id = body.system_id
    template.required_kind = body.required_kind
    template.required_ancestor_entry_id = body.required_ancestor_entry_id
    await _replace_slots(session, tenant_id, template_id, body.slots)
    await session.commit()
    await set_tenant_rls_context(session, tenant_id)
    return _out(
        await _get_or_404(session, tenant_id, template_id), await _slugs(session, tenant_id)
    )


@router.delete("/{template_id}", status_code=204, dependencies=[Depends(get_tenant_admin_context)])
async def delete_template(
    tenant_id: uuid.UUID, template_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    template = await _get_or_404(session, tenant_id, template_id)
    await record_activity(
        session,
        tenant_id=tenant_id,
        actor_id=user.id,
        action="template.deleted",
        target_type="template",
        target_id=template_id,
        detail=f"name={template.name}",
    )
    await session.delete(template)
    await session.commit()


# --- reading an entry through a template -------------------------------------------------------


async def _prototype_ancestors(
    session: SessionDep, tenant_id: uuid.UUID, entity_id: uuid.UUID
) -> set[uuid.UUID]:
    """Every entry on the prototype walk above this one (ADR 0037's walk, asked for
    membership): its prototypes, theirs, and so on."""
    up = (
        select(EntityPrototype.prototype_id.label("id"))
        .where(EntityPrototype.entity_id == entity_id, EntityPrototype.tenant_id == tenant_id)
        .cte("up", recursive=True)
    )
    up = up.union(
        select(EntityPrototype.prototype_id).where(
            EntityPrototype.entity_id == up.c.id, EntityPrototype.tenant_id == tenant_id
        )
    )
    return set(await session.scalars(select(up.c.id)))


def _matches(template: Template, kinds: Sequence[str], ancestors: set[uuid.UUID]) -> bool:
    """The filter: the kind and the ancestor, each applied when set."""
    return (template.required_kind is None or template.required_kind in kinds) and (
        template.required_ancestor_entry_id is None
        or template.required_ancestor_entry_id in ancestors
    )


@entry_router.get("/matching-templates")
async def matching_templates(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    session: SessionDep,
    user: CurrentUser,
    system: SystemFilter = None,
) -> list[TemplateSummaryOut]:
    """The templates whose filter matches this entry, by name; with `system`, those of no game
    system and of that one. Nothing is chosen when several match (ADR 0451)."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    await require_system_slug(session, tenant_id, system)
    await require_visible_entry(session, entity_id=entity_id, tenant_id=tenant_id, user_id=user.id)
    if (
        await session.scalar(
            select(Entity.id).where(Entity.id == entity_id, Entity.tenant_id == tenant_id)
        )
        is None
    ):
        raise EntityNotFoundError(detail=f"No entity with id {entity_id} in tenant {tenant_id}")
    kinds = (await kinds_of(session, [entity_id]))[entity_id]
    ancestors = await _prototype_ancestors(session, tenant_id, entity_id)
    stmt = select(Template).where(Template.tenant_id == tenant_id)
    if system is not None:
        stmt = stmt.where(
            or_(
                Template.system_id.is_(None),
                Template.system_id.in_(
                    select(System.id).where(System.tenant_id == tenant_id, System.slug == system)
                ),
            )
        )
    slugs = await _slugs(session, tenant_id)
    templates = (await session.scalars(stmt.order_by(Template.name, Template.id))).all()
    return [_summary(t, slugs) for t in templates if _matches(t, kinds, ancestors)]


def _unit_of(by_id: dict[uuid.UUID, StatDefinition], stat: EntityStatValueOut) -> str | None:
    definition = by_id.get(stat.stat_definition_id)
    return definition.unit if definition is not None else None


def _stat_out(stat: EntityStatValueOut, label: str | None, unit: str | None) -> TemplateStatOut:
    return TemplateStatOut(**stat.model_dump(), label=label or stat.name, unit=unit)


async def _held_rows(
    session: SessionDep,
    *,
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    user: CurrentUser,
    visibility: InformationVisibility,
    columns: Sequence[uuid.UUID],
    order: str,
) -> list[TemplateHeldRowOut]:
    """The item instances the entry holds directly, as the datasheet's weapons are (ADR 0281):
    what the caller may see of them is ADR 0040's. A cell is the thing's effective value of the
    column's stat, null when it has none."""
    reach = await caller_reach(session, tenant_id=tenant_id, user=user, visibility=visibility)
    views = (
        (
            await session.execute(
                select(VItemInstance)
                .join(Entity, Entity.id == VItemInstance.entity_id)
                .where(
                    VItemInstance.tenant_id == tenant_id,
                    VItemInstance.entity_id.in_(
                        select(Containment.child_entity_id).where(
                            Containment.parent_entity_id == entity_id,
                            Containment.tenant_id == tenant_id,
                        )
                    ),
                    _owner_predicate_for(reach),
                )
                .options(
                    *eager_load_options(VItemInstance.entity),
                    joinedload(VItemInstance.entity)
                    .selectinload(Entity.effective_stats)
                    .joinedload(VEffectiveStat.source_entity),
                )
                .order_by(Entity.name, VItemInstance.entity_id)
            )
        )
        .scalars()
        .all()
    )
    await attach_contents(session, [view.entity for view in views], tenant_id=tenant_id)
    if order == "prototype":
        names: dict[uuid.UUID, str] = {}
        rows = await session.execute(
            select(EntityPrototype.entity_id, Entity.name)
            .join(Entity, Entity.id == EntityPrototype.prototype_id)
            .where(
                EntityPrototype.tenant_id == tenant_id,
                EntityPrototype.entity_id.in_([view.entity_id for view in views]),
            )
        )
        for held_id, prototype_name in rows.tuples():
            names[held_id] = min(prototype_name, names.get(held_id, prototype_name))
        views = sorted(
            views, key=lambda v: (names.get(v.entity_id, ""), v.entity.name, str(v.entity_id))
        )
    out: list[TemplateHeldRowOut] = []
    for view in views:
        values = {s.stat_definition_id: s.value for s in _stats_out(view.entity, visibility)}
        out.append(
            TemplateHeldRowOut(
                entity=EntitySummary.from_entity(view.entity),
                quantity=view.quantity,
                cells=[TemplateCellOut(stat_definition_id=c, value=values.get(c)) for c in columns],
            )
        )
    return out


@entry_router.get("/templates/{template_id}")
async def read_through_template(
    tenant_id: uuid.UUID,
    entity_id: uuid.UUID,
    template_id: uuid.UUID,
    request: Request,
    session: SessionDep,
    user: CurrentUser,
) -> TemplateViewOut:
    """The entry as the template shows it: an ordered array of slots with the resolved values,
    labels and units (ADR 0451). The entry must be one the template is for (409 otherwise): the
    API does not pick another. Each slot is read by the rules of what it reads: stat values as
    the entry's own read gives them, notes through the information visibility check, held things
    through ADR 0040's reach; nothing the caller may not read is in it."""
    await require_tenant_participant(session, tenant_id=tenant_id, user=user)
    template = await _get_or_404(session, tenant_id, template_id)
    entity = await get_entity_detail_or_404(session, entity_id, tenant_id)
    kinds = (await kinds_of(session, [entity_id]))[entity_id]
    if not _matches(template, kinds, await _prototype_ancestors(session, tenant_id, entity_id)):
        raise TemplateDoesNotMatchError(
            detail=f"Template {template.name!r} is not for entry {entity_id}"
        )
    visibility = await resolve_information_visibility(session, user_id=user.id, tenant_id=tenant_id)
    stats = _stats_out(entity, visibility)

    # The definitions the slots show: those they list, and every one of the groups they show.
    group_ids = {s.stat_group_id for s in template.slots if s.stat_group_id is not None}
    listed = {x.stat_definition_id for s in template.slots for x in s.stats}
    definitions = (
        (
            await session.scalars(
                select(StatDefinition)
                .where(
                    StatDefinition.tenant_id == tenant_id,
                    or_(
                        StatDefinition.id.in_(listed),
                        StatDefinition.stat_group_id.in_(group_ids),
                    ),
                )
                .order_by(StatDefinition.position, StatDefinition.name, StatDefinition.id)
            )
        ).all()
        if listed or group_ids
        else []
    )
    by_id = {d.id: d for d in definitions}
    summary = _summary(template, await _slugs(session, tenant_id))

    slots: list[TemplateViewSlotOut] = []
    for slot in template.slots:
        view = TemplateViewSlotOut(
            position=slot.position, kind=cast(SlotKind, slot.kind), label=slot.label
        )
        left_out = {e.stat_definition_id for e in slot.exclusions}
        labels = {x.stat_definition_id: x.label for x in slot.stats}
        if slot.kind == "stats":
            if slot.stat_group_id is not None:
                shown = [
                    s
                    for s in stats
                    if s.group_id == slot.stat_group_id and s.stat_definition_id not in left_out
                ]
            else:
                by_value = {s.stat_definition_id: s for s in stats}
                shown = [
                    by_value[x.stat_definition_id]
                    for x in slot.stats
                    if x.stat_definition_id in by_value
                ]
            view.stats = [
                _stat_out(s, labels.get(s.stat_definition_id), _unit_of(by_id, s)) for s in shown
            ]
        elif slot.kind == "tags":
            view.tags = [
                _stat_out(s, None, _unit_of(by_id, s))
                for s in stats
                if s.value is True
                and (slot.stat_group_id is None or s.group_id == slot.stat_group_id)
            ]
        elif slot.kind == "information":
            rows = (
                await session.scalars(
                    select(Information)
                    .where(
                        Information.entity_id == entity_id,
                        Information.tenant_id == tenant_id,
                        Information.type == slot.information_type,
                        visible_information_clause(visibility),
                    )
                    .options(*_INFORMATION_LOAD_OPTIONS)
                    .order_by(Information.order, Information.id)
                )
            ).all()
            view.information = [InformationOut.from_information(row, request) for row in rows]
        else:  # held
            if slot.stat_group_id is not None:
                column_ids = [
                    d.id
                    for d in definitions
                    if d.stat_group_id == slot.stat_group_id and d.id not in left_out
                ]
            else:
                column_ids = [x.stat_definition_id for x in slot.stats]
            view.columns = [
                TemplateColumnOut(
                    stat_definition_id=c,
                    name=by_id[c].name,
                    label=labels.get(c) or by_id[c].name,
                    unit=by_id[c].unit,
                )
                for c in column_ids
            ]
            view.rows = await _held_rows(
                session,
                tenant_id=tenant_id,
                entity_id=entity_id,
                user=user,
                visibility=visibility,
                columns=column_ids,
                order=slot.held_order or "name",
            )
        slots.append(view)
    return TemplateViewOut(template=summary, entity=EntitySummary.from_entity(entity), slots=slots)
